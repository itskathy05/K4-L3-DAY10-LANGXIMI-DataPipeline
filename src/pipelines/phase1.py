from __future__ import annotations

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.agent import build_agent, run_agent_question
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    settings = load_settings()

    records = fetch_source_records(settings)
    df = build_clean_dataframe(records, now_utc())
    write_csv(df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, df.to_dict(orient="records"))

    index = LocalEmbeddingIndex.build(df, settings)

    if settings.paths.eval_testset.exists() and not settings.refresh_test_set:
        test_set = read_json(settings.paths.eval_testset)
    else:
        test_set = build_test_set(df, settings.paths.eval_testset)

    bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )

    quality = run_data_quality_checks(df, settings, "baseline")
    freshness = build_freshness_report(df, settings, settings.paths.freshness_report)

    generate_phase1_report(
        settings.paths.baseline_report,
        source_summary={
            "document_count": len(df),
            "collection_name": index.collection_name,
        },
        metrics=bundle.summary,
        quality=quality,
        freshness=freshness,
    )

    try:
        agent = build_agent(settings, index)
        demo_questions = [item["question"] for item in test_set[:2]]
        demo_answers = [
            {"question": q, "answer": run_agent_question(agent, q)} for q in demo_questions
        ]
    except Exception as exc:  # pragma: no cover - agent demo is best-effort
        demo_answers = [{"error": f"Agent demo unavailable: {exc}"}]
    write_json(settings.paths.demo_answers, demo_answers)

    print(f"Tín hiệu hoàn thành: Đã tải {len(records)} bài báo")
    print(f"Tín hiệu hoàn thành: Clean thành công {len(df)} dòng")
    print(f"Tín hiệu hoàn thành: Sinh được {len(test_set)} câu hỏi test")
    print(f"Tín hiệu hoàn thành: Quality check status = {quality['success']}")
    print(
        f"Baseline retrieval_hit_rate={bundle.summary['retrieval_hit_rate']:.3f} "
        f"mean_token_f1={bundle.summary['mean_token_f1']:.3f}"
    )


if __name__ == "__main__":
    main()
