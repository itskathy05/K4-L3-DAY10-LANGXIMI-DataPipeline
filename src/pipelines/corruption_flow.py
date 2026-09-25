from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import now_utc, read_json, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.reporting import generate_corruption_report
from pipelines.phase1 import (
    load_clean_dataset,
    persist_clean_dataset,
    print_metrics,
    run_baseline,
    run_quality_gate,
    validate_clean_schema,
)
from retrieval.index import LocalEmbeddingIndex

COMPARISON_METRICS = (
    ("retrieval_hit_rate", "Retrieval hit rate"),
    ("mean_token_f1", "Mean token F1"),
    ("judge_accuracy", "Judge accuracy"),
    ("mean_judge_score", "Mean judge score"),
)


def ensure_baseline(settings: Settings) -> dict[str, Any]:
    required = (
        settings.paths.clean_json,
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
    )
    if all(path.exists() for path in required):
        print("  baseline artifacts found, reusing them")
        return read_json(settings.paths.baseline_metrics)

    print("  baseline artifacts missing - running phase 1 first")
    return run_baseline(settings).metrics


def evaluate_stage(
    df: pd.DataFrame,
    settings: Settings,
    label: str,
    embeddings_path: Path,
    metrics_path: Path,
    answers_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    validate_clean_schema(df, stage=label)
    quality, freshness = run_quality_gate(df, settings, label)
    index = LocalEmbeddingIndex.build(df, settings, embeddings_path)
    print(f"  collection '{index.collection_name}' indexed {len(index.documents)} documents")
    bundle = evaluate_pipeline(settings, index, settings.paths.eval_testset, metrics_path, answers_path)
    print_metrics(label, bundle.summary)
    return bundle.summary, quality, freshness


def repair_from_raw(settings: Settings) -> pd.DataFrame:
    """Rebuild the serving dataset from the immutable raw snapshot (idempotent)."""
    records = load_raw_records(settings.paths.raw_records_json)
    repaired_df = build_clean_dataframe(records, now_utc())
    validate_clean_schema(repaired_df, stage="repaired")
    persist_clean_dataset(repaired_df, settings.paths.repaired_clean_csv, settings.paths.repaired_clean_json)
    persist_clean_dataset(repaired_df, settings.paths.clean_csv, settings.paths.clean_json)
    print(f"  rebuilt {len(repaired_df)} rows from {settings.paths.raw_records_json}")
    return repaired_df


def verify_repair(baseline_df: pd.DataFrame, repaired_df: pd.DataFrame, settings: Settings) -> dict[str, Any]:
    baseline_ids = set(baseline_df["paper_id"])
    repaired_ids = set(repaired_df["paper_id"])
    baseline_text = dict(zip(baseline_df["paper_id"], baseline_df["text_for_embedding"], strict=False))
    repaired_text = dict(zip(repaired_df["paper_id"], repaired_df["text_for_embedding"], strict=False))
    identical_text = sorted(
        paper_id for paper_id in baseline_ids & repaired_ids if baseline_text[paper_id] == repaired_text[paper_id]
    )

    payload = {
        "baseline_rows": int(len(baseline_df)),
        "repaired_rows": int(len(repaired_df)),
        "row_count_restored": len(baseline_df) == len(repaired_df),
        "paper_ids_restored": baseline_ids == repaired_ids,
        "missing_after_repair": sorted(baseline_ids - repaired_ids),
        "unexpected_after_repair": sorted(repaired_ids - baseline_ids),
        "identical_text_for_embedding": len(identical_text),
        "duplicate_paper_ids": int(len(repaired_df) - repaired_df["paper_id"].nunique()),
    }
    payload["is_idempotent"] = (
        payload["row_count_restored"]
        and payload["paper_ids_restored"]
        and payload["identical_text_for_embedding"] == payload["baseline_rows"]
        and payload["duplicate_paper_ids"] == 0
    )
    write_json(settings.paths.corruption_log.with_name("repair_verification.json"), payload)
    print(f"  idempotent repair verified: {payload['is_idempotent']}")
    return payload


def format_comparison_table(
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    baseline_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
    baseline_freshness: dict[str, Any],
) -> str:
    rows = [("Metric", "Baseline", "Corrupted", "Repaired")]
    for key, label in COMPARISON_METRICS:
        rows.append(
            (
                label,
                f"{baseline_metrics.get(key, 0.0):.3f}",
                f"{corrupted_metrics.get(key, 0.0):.3f}",
                f"{repaired_metrics.get(key, 0.0):.3f}",
            )
        )
    rows.append(
        (
            "Quality gate success",
            str(bool(baseline_quality.get("success"))),
            str(bool(corrupted_quality.get("success"))),
            str(bool(repaired_quality.get("success"))),
        )
    )
    rows.append(
        (
            "Freshness is_fresh",
            str(bool(baseline_freshness.get("is_fresh"))),
            str(bool(corrupted_freshness.get("is_fresh"))),
            str(bool(repaired_freshness.get("is_fresh"))),
        )
    )

    widths = [max(len(row[column]) for row in rows) for column in range(4)]
    lines = []
    for position, row in enumerate(rows):
        lines.append("  " + " | ".join(value.ljust(widths[column]) for column, value in enumerate(row)))
        if position == 0:
            lines.append("  " + "-+-".join("-" * width for width in widths))
    return "\n".join(lines)


def main() -> None:
    settings = load_settings()
    print("=== PHASE 2: CORRUPTION -> IMPACT -> REPAIR ===")

    print("[1/5] Baseline - loading clean dataset and reference metrics")
    baseline_metrics = ensure_baseline(settings)
    baseline_df = load_clean_dataset(settings.paths.clean_json)
    validate_clean_schema(baseline_df, stage="baseline")
    baseline_quality, baseline_freshness = run_quality_gate(baseline_df, settings, "baseline")
    print_metrics("baseline", baseline_metrics)

    print("[2/5] Corruption - injecting synthetic data failures")
    corrupted_df = corrupt_clean_dataframe(baseline_df.copy(deep=True), settings.paths.corruption_log)
    persist_clean_dataset(corrupted_df, settings.paths.corrupted_clean_csv, settings.paths.corrupted_clean_json)
    corruption_log = read_json(settings.paths.corruption_log) if settings.paths.corruption_log.exists() else {}
    print(f"  {len(baseline_df)} rows -> {len(corrupted_df)} corrupted rows, log -> {settings.paths.corruption_log}")

    print("[3/5] Impact - re-index and re-evaluate on corrupted data")
    corrupted_metrics, corrupted_quality, corrupted_freshness = evaluate_stage(
        corrupted_df,
        settings,
        "corrupted",
        settings.paths.corrupted_embeddings_json,
        settings.paths.corrupted_metrics,
        settings.paths.corrupted_answers,
    )

    print("[4/5] Repair - idempotent rebuild from the raw snapshot")
    repaired_df = repair_from_raw(settings)
    repaired_metrics, repaired_quality, repaired_freshness = evaluate_stage(
        repaired_df,
        settings,
        "repaired",
        settings.paths.repaired_embeddings_json,
        settings.paths.repaired_metrics,
        settings.paths.repaired_answers,
    )
    verification = verify_repair(baseline_df, repaired_df, settings)

    print("[5/5] Reporting - three-state comparison")
    generate_corruption_report(
        settings.paths.comparison_report,
        baseline_metrics,
        corrupted_metrics,
        repaired_metrics,
        corrupted_quality,
        repaired_quality,
        corrupted_freshness,
        repaired_freshness,
        baseline_quality=baseline_quality,
        baseline_freshness=baseline_freshness,
        corruption_log=corruption_log,
        corrupted_answers=read_json(settings.paths.corrupted_answers),
        repair_verification=verification,
    )
    print(f"  report -> {settings.paths.comparison_report}")

    print("\nBaseline vs Corrupted vs Repaired")
    print(
        format_comparison_table(
            baseline_metrics,
            corrupted_metrics,
            repaired_metrics,
            corrupted_quality,
            repaired_quality,
            baseline_quality,
            corrupted_freshness,
            repaired_freshness,
            baseline_freshness,
        )
    )

    print(f"\nCorruption scenarios logged: {len(corruption_log.get('scenarios', []))}")
    print(f"Repair is idempotent: {verification['is_idempotent']}")
    print("\nArtifacts written:")
    for path in (
        settings.paths.corrupted_clean_csv,
        settings.paths.corruption_log,
        settings.paths.corrupted_metrics,
        settings.paths.corrupted_quality_report,
        settings.paths.repaired_clean_csv,
        settings.paths.repaired_metrics,
        settings.paths.comparison_report,
    ):
        marker = "ok" if Path(path).exists() else "MISSING"
        print(f"  [{marker}] {path}")

    if not verification["is_idempotent"]:
        raise SystemExit(
            "Repair verification failed: the repaired corpus does not match the baseline "
            f"(see {settings.paths.corruption_log.with_name('repair_verification.json')})."
        )


if __name__ == "__main__":
    main()
