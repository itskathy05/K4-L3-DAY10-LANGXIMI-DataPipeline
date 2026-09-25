from __future__ import annotations

from typing import Any

from core.utils import write_text


def _metrics_table(metrics: dict[str, Any]) -> str:
    return (
        "| Metric | Value |\n"
        "| --- | --- |\n"
        f"| Samples | {metrics.get('samples')} |\n"
        f"| Retrieval hit rate | {metrics.get('retrieval_hit_rate'):.3f} |\n"
        f"| Mean token F1 | {metrics.get('mean_token_f1'):.3f} |\n"
        f"| Judge accuracy | {metrics.get('judge_accuracy'):.3f} |\n"
        f"| Mean judge score | {metrics.get('mean_judge_score'):.3f} |\n"
    )


def _expectations_table(quality: dict[str, Any]) -> str:
    lines = ["| Expectation | Column | Success |", "| --- | --- | --- |"]
    for item in quality.get("expectations", []):
        lines.append(f"| {item['expectation_type']} | {item.get('column') or '-'} | {item['success']} |")
    return "\n".join(lines)


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Write the baseline phase markdown report."""
    lines = [
        "# Phase 1 — Baseline Pipeline Report",
        "",
        "## Source",
        f"- Documents indexed: {source_summary.get('document_count')}",
        f"- Collection: `{source_summary.get('collection_name')}`",
        "",
        "## Evaluation metrics",
        _metrics_table(metrics),
        "## Data quality gate (Great Expectations 1.x)",
        f"- Overall success: **{quality.get('success')}**",
        _expectations_table(quality),
        "",
        "## Freshness SLA",
        f"- Latest published: {freshness.get('latest_published')}",
        f"- Oldest published: {freshness.get('oldest_published')}",
        f"- Stale rows: {freshness.get('stale_rows')} / {freshness.get('total_rows')} "
        f"({freshness.get('stale_ratio', 0):.1%})",
        f"- Is fresh: **{freshness.get('is_fresh')}**",
        "",
    ]
    write_text(report_path, "\n".join(lines))


def _comparison_table(baseline: dict[str, Any], corrupted: dict[str, Any], repaired: dict[str, Any]) -> str:
    rows = [
        ("Retrieval hit rate", "retrieval_hit_rate"),
        ("Mean token F1", "mean_token_f1"),
        ("Judge accuracy", "judge_accuracy"),
        ("Mean judge score", "mean_judge_score"),
    ]
    lines = ["| Metric | Baseline | Corrupted | Repaired |", "| --- | --- | --- | --- |"]
    for label, key in rows:
        lines.append(
            f"| {label} | {baseline.get(key, 0):.3f} | {corrupted.get(key, 0):.3f} | {repaired.get(key, 0):.3f} |"
        )
    return "\n".join(lines)


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> str:
    """Write the baseline/corrupted/repaired comparison markdown report; return the table for the console."""
    hit_drop = baseline_metrics.get("retrieval_hit_rate", 0) - corrupted_metrics.get("retrieval_hit_rate", 0)
    hit_recovered = repaired_metrics.get("retrieval_hit_rate", 0) >= baseline_metrics.get("retrieval_hit_rate", 0)
    table = _comparison_table(baseline_metrics, corrupted_metrics, repaired_metrics)

    lines = [
        "# Corruption & Repair Comparison Report",
        "",
        "## Three-state metric comparison",
        table,
        "",
        "## Analysis",
        f"- Corruption dropped retrieval hit rate by {hit_drop:.3f} versus baseline.",
        f"- Data quality gate on corrupted data: success = **{corrupted_quality.get('success')}**.",
        f"- Freshness on corrupted data: is_fresh = **{corrupted_freshness.get('is_fresh')}** "
        f"(stale_ratio={corrupted_freshness.get('stale_ratio', 0):.1%}).",
        f"- After idempotent repair from raw records, data quality gate success = **{repaired_quality.get('success')}**, "
        f"freshness is_fresh = **{repaired_freshness.get('is_fresh')}**.",
        f"- Retrieval hit rate recovered to baseline level: **{hit_recovered}**.",
        "",
    ]
    write_text(report_path, "\n".join(lines))
    return table
