from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings, load_settings, normalized_provider, require_llm_credentials
from core.utils import dataframe_records, now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import PaperRecord, fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex

REQUIRED_CLEAN_COLUMNS = (
    "paper_id",
    "title",
    "summary",
    "authors_joined",
    "categories_joined",
    "published",
    "age_days",
    "abs_url",
    "pdf_url",
    "text_for_embedding",
)


@dataclass(frozen=True)
class StageArtifacts:
    label: str
    clean_df: pd.DataFrame
    index: LocalEmbeddingIndex
    metrics: dict[str, Any]
    answers: list[dict[str, Any]]
    quality: dict[str, Any]
    freshness: dict[str, Any]
    test_set_path: Path


def validate_clean_schema(df: pd.DataFrame, stage: str = "clean") -> None:
    missing = [column for column in REQUIRED_CLEAN_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(
            f"[{stage}] dataframe is missing required columns {missing}. "
            f"Available columns: {sorted(df.columns)}"
        )
    if df.empty:
        raise ValueError(f"[{stage}] dataframe is empty; the pipeline cannot index an empty corpus.")


def freshness_report_path(settings: Settings, label: str) -> Path:
    base = settings.paths.freshness_report
    if label == "baseline":
        return base
    return base.with_name(f"{base.stem}_{label}{base.suffix}")


def resolve_source_records(settings: Settings) -> tuple[list[PaperRecord], str]:
    raw_path = settings.paths.raw_records_json
    snapshot = load_raw_records(raw_path) if raw_path.exists() else None
    if not settings.refresh_source and snapshot is not None:
        return snapshot, "raw-snapshot"

    try:
        records = fetch_source_records(settings)
    except Exception as exc:
        if snapshot is None:
            raise
        print(f"  ! live fetch failed ({exc}); falling back to the raw snapshot")
        return snapshot, "raw-snapshot"

    if records == snapshot:
        return records, "raw-snapshot"
    write_json(raw_path, [asdict(record) for record in records])
    print(f"  live records saved to {raw_path} so the repair step rebuilds the same corpus")
    return records, "live-api"


def persist_clean_dataset(df: pd.DataFrame, csv_path: Path, json_path: Path) -> None:
    write_csv(df, csv_path)
    write_json(json_path, dataframe_records(df))


def load_clean_dataset(json_path: Path) -> pd.DataFrame:
    return pd.DataFrame(read_json(json_path))


def run_quality_gate(df: pd.DataFrame, settings: Settings, label: str) -> tuple[dict[str, Any], dict[str, Any]]:
    quality = run_data_quality_checks(df, settings, label)
    freshness = build_freshness_report(df, settings, freshness_report_path(settings, label))
    passed = bool(quality.get("success"))
    fresh = bool(freshness.get("is_fresh"))
    print(f"  quality gate: success={passed} | freshness: is_fresh={fresh}")
    if not passed:
        print(f"  ! QUALITY GATE FAILED on '{label}' data - see {settings.paths.quality_dir}")
    if not fresh:
        print(f"  ! FRESHNESS SLA BREACHED on '{label}' data (threshold {settings.freshness_threshold_days} days)")
    return quality, freshness


def ensure_test_set(df: pd.DataFrame, settings: Settings) -> Path:
    path = settings.paths.eval_testset
    reason = None
    if settings.refresh_test_set:
        reason = "REFRESH_TEST_SET is set"
    elif not path.exists():
        reason = "no saved test set"
    else:
        expected = {doc_id for item in read_json(path) for doc_id in item.get("ground_truth_doc_ids", [])}
        missing = expected - set(df["paper_id"])
        if missing:
            reason = f"{len(missing)} ground-truth papers are not in the current corpus"

    if reason:
        build_test_set(df, path)
        print(f"  benchmark test set built ({reason}): {len(read_json(path))} questions -> {path}")
    else:
        print(f"  benchmark test set reused: {len(read_json(path))} questions <- {path}")
    return path


def print_metrics(label: str, metrics: dict[str, Any]) -> None:
    print(
        f"  {label} metrics: hit_rate={metrics.get('retrieval_hit_rate', 0.0):.3f} "
        f"token_f1={metrics.get('mean_token_f1', 0.0):.3f} "
        f"judge_accuracy={metrics.get('judge_accuracy', 0.0):.3f} "
        f"judge_score={metrics.get('mean_judge_score', 0.0):.2f}"
    )


def project_relative(settings: Settings, path: Path) -> str:
    try:
        return path.relative_to(settings.paths.project_dir).as_posix()
    except ValueError:
        return str(path)


def build_source_summary(
    settings: Settings,
    records: list[PaperRecord],
    df: pd.DataFrame,
    source_mode: str,
    run_date,
) -> dict[str, Any]:
    return {
        "run_timestamp": run_date.isoformat(),
        "source_api": settings.source_api,
        "source_mode": source_mode,
        "source_query": settings.source_query,
        "source_filter": settings.source_filter,
        "max_results": settings.max_results,
        "raw_records": len(records),
        "clean_rows": int(len(df)),
        "unique_paper_ids": int(df["paper_id"].nunique()),
        "embedding_model": settings.embedding_model,
        "collection_name": settings.baseline_collection_name,
        "top_k": settings.top_k,
        "freshness_threshold_days": settings.freshness_threshold_days,
        "llm_provider": normalized_provider(settings),
        "llm_model": settings.model_name,
        "raw_api_response": project_relative(settings, settings.paths.raw_api_response),
        "raw_records_json": project_relative(settings, settings.paths.raw_records_json),
        "clean_csv": project_relative(settings, settings.paths.clean_csv),
    }


def run_agent_demo(settings: Settings, index: LocalEmbeddingIndex, test_set_path: Path, limit: int = 2) -> None:
    try:
        require_llm_credentials(settings)
    except RuntimeError as exc:
        print(f"  agent demo skipped: {exc}")
        return

    try:
        from retrieval.agent import build_agent, run_agent_question

        questions = [item["question"] for item in read_json(test_set_path)[:limit]]
        agent = build_agent(settings, index)
        answers = [{"question": question, "answer": run_agent_question(agent, question)} for question in questions]
    except Exception as exc:
        print(f"  agent demo skipped: {type(exc).__name__}: {exc}")
        return

    write_json(settings.paths.demo_answers, answers)
    print(f"  agent demo answered {len(answers)} questions -> {settings.paths.demo_answers}")


def run_baseline(settings: Settings | None = None) -> StageArtifacts:
    settings = settings or load_settings()
    run_date = now_utc()

    print("[1/6] Ingestion - loading source records")
    records, source_mode = resolve_source_records(settings)
    print(f"  {len(records)} records ({source_mode})")

    print("[2/6] Cleaning - normalising schema and computing age_days")
    clean_df = build_clean_dataframe(records, run_date)
    validate_clean_schema(clean_df, stage="baseline")
    persist_clean_dataset(clean_df, settings.paths.clean_csv, settings.paths.clean_json)
    print(f"  {len(clean_df)} clean rows -> {settings.paths.clean_csv}")

    print("[3/6] Quality gate - Great Expectations 1.x + freshness SLA")
    quality, freshness = run_quality_gate(clean_df, settings, "baseline")
    if not quality.get("success"):
        raise RuntimeError(
            "Baseline quality gate failed; refusing to index unvalidated data into "
            f"'{settings.baseline_collection_name}'. See {settings.paths.quality_dir}."
        )

    print("[4/6] Indexing - MiniLM embeddings into ChromaDB")
    index = LocalEmbeddingIndex.build(clean_df, settings, settings.paths.embeddings_json)
    print(f"  collection '{index.collection_name}' indexed {len(index.documents)} documents")

    print("[5/6] Evaluation - benchmark test set")
    test_set_path = ensure_test_set(clean_df, settings)
    bundle = evaluate_pipeline(
        settings,
        index,
        test_set_path,
        settings.paths.baseline_metrics,
        settings.paths.baseline_answers,
    )
    print_metrics("baseline", bundle.summary)

    print("[6/6] Reporting - phase 1 markdown report")
    source_summary = build_source_summary(settings, records, clean_df, source_mode, run_date)
    generate_phase1_report(
        settings.paths.baseline_report,
        source_summary,
        bundle.summary,
        quality,
        freshness,
    )
    print(f"  report -> {settings.paths.baseline_report}")
    run_agent_demo(settings, index, test_set_path)

    return StageArtifacts(
        label="baseline",
        clean_df=clean_df,
        index=index,
        metrics=bundle.summary,
        answers=bundle.answers,
        quality=quality,
        freshness=freshness,
        test_set_path=test_set_path,
    )


def main() -> None:
    settings = load_settings()
    print("=== PHASE 1: BASELINE DATA PIPELINE ===")
    artifacts = run_baseline(settings)

    print("\nArtifacts written:")
    for path in (
        settings.paths.raw_records_json,
        settings.paths.clean_csv,
        settings.paths.clean_json,
        settings.paths.chroma_dir,
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
        settings.paths.baseline_answers,
        settings.paths.baseline_quality_report,
        settings.paths.freshness_report,
        settings.paths.baseline_report,
    ):
        marker = "ok" if Path(path).exists() else "MISSING"
        print(f"  [{marker}] {path}")
    print(f"\nBaseline ready with {len(artifacts.clean_df)} clean rows. Next: python script/run_corruption_flow.py")


if __name__ == "__main__":
    main()
