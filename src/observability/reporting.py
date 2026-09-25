from __future__ import annotations

from pathlib import Path
from typing import Any

from core.utils import read_json, write_text


UNKNOWN_ANSWER_PREFIX = "I don't know"
METRIC_ROWS = (
    ("retrieval_hit_rate", "Retrieval Hit Rate", "pct"),
    ("mean_token_f1", "Mean Token F1", "pct"),
    ("judge_accuracy", "Judge Accuracy", "pct"),
    ("mean_judge_score", "Mean Judge Score (thang 1-5)", "score"),
)


def _pct(value: Any) -> str:
    return f"{float(value) * 100:.1f}%"


def _metric(metrics: dict[str, Any], key: str, kind: str) -> str:
    if key not in metrics:
        return "—"
    return _pct(metrics[key]) if kind == "pct" else f"{float(metrics[key]):.2f}"


def _gate(quality: dict[str, Any] | None) -> str:
    if not quality:
        return "—"
    status = "PASSED" if quality.get("success") else "FAILED"
    if "evaluated_expectations" in quality:
        return f"{status} ({quality.get('successful_expectations', 0)}/{quality['evaluated_expectations']})"
    return status


def _freshness(freshness: dict[str, Any] | None) -> str:
    if not freshness:
        return "—"
    status = "FRESH" if freshness.get("is_fresh") else "STALE"
    return f"{status} ({_pct(freshness.get('stale_ratio', 0))} quá hạn)"


def _judge_mode(metrics: dict[str, Any]) -> str:
    samples = int(metrics.get("samples", 0))
    fallbacks = metrics.get("judge_fallbacks")
    if fallbacks is None:
        return "không rõ"
    return f"LLM {samples - int(fallbacks)}/{samples}, heuristic {int(fallbacks)}/{samples}"


def _failed_expectations(quality: dict[str, Any] | None) -> list[str]:
    """Read the GX validation result written by run_data_quality_checks."""
    path = (quality or {}).get("output_path")
    if not path or not Path(path).exists():
        return []
    failed = []
    for result in read_json(Path(path)).get("results", []):
        if not result.get("success"):
            config = result.get("expectation_config", {})
            column = config.get("kwargs", {}).get("column")
            failed.append(f"`{config.get('type')}`" + (f" trên cột `{column}`" if column else ""))
    return failed


def generate_phase1_report(
    report_path: Path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Tạo báo cáo Markdown cho Phase 1 (Baseline Pipeline) từ số liệu thực tế."""
    if source_summary.get("source_mode") == "live-api":
        source_line = (
            f"Crossref live (`query={source_summary.get('source_query')}`, "
            f"`filter={source_summary.get('source_filter')}`), đã lưu lại vào "
            f"`{source_summary.get('raw_records_json')}`"
        )
    else:
        source_line = f"snapshot offline `{source_summary.get('raw_records_json', 'data/raw/crossref_records.json')}`"

    samples = int(metrics.get("samples", 0))
    hits = round(float(metrics.get("retrieval_hit_rate", 0.0)) * samples)
    fallbacks = metrics.get("judge_fallbacks")
    threshold = source_summary.get("freshness_threshold_days", freshness.get("threshold_days", 180))
    failed = _failed_expectations(quality)

    lines = [
        "# Báo Cáo Phase 1 — Baseline Pipeline & Observability",
        "",
        "## 1. Nguồn dữ liệu",
        f"- **Nguồn:** {source_summary.get('source_api', 'Crossref REST API')} — {source_line}",
        f"- **Số bản ghi raw:** {source_summary.get('raw_records', '—')}",
        f"- **Số bản ghi sau làm sạch:** {source_summary.get('clean_rows', '—')} "
        f"(`paper_id` duy nhất: {source_summary.get('unique_paper_ids', '—')})",
        f"- **Thời điểm chạy (UTC):** {source_summary.get('run_timestamp', '—')}",
        "",
        "## 2. Data Quality Gate (Great Expectations 1.x) & Freshness SLA",
        f"- **Quality gate:** `{_gate(quality)}`",
    ]
    if failed:
        lines.append(f"- **Expectation không đạt:** {', '.join(failed)}")
    lines += [
        f"- **Freshness SLA:** `{'FRESH' if freshness.get('is_fresh') else 'STALE'}` — "
        f"{freshness.get('stale_rows', 0)}/{freshness.get('total_rows', 0)} bản ghi có `age_days > {threshold}` "
        f"({_pct(freshness.get('stale_ratio', 0))}); SLA cho phép tối đa 25%.",
        f"- **Bản ghi mới nhất / cũ nhất:** {freshness.get('latest_published', '—')} / {freshness.get('oldest_published', '—')}",
        "",
        "## 3. Baseline metrics",
        f"Đánh giá trên {samples} câu hỏi của `data/eval/test_set.json`, top-k = {source_summary.get('top_k', '—')}, "
        f"collection `{source_summary.get('collection_name', 'papers-baseline')}`.",
        "",
        "| Chỉ số | Giá trị |",
        "| :--- | :---: |",
        *[f"| **{label}** | {_metric(metrics, key, kind)} |" for key, label, kind in METRIC_ROWS],
        "",
    ]
    if fallbacks is not None:
        lines.append(
            f"- **Judge:** `{source_summary.get('llm_provider', '—')}` / `{source_summary.get('llm_model', '—')}` — "
            f"{_judge_mode(metrics)} câu. Câu dùng heuristic được chấm theo token F1 khi không gọi được LLM, "
            "nên với các câu đó `judge_accuracy` không độc lập với `mean_token_f1`."
        )
        lines.append("")

    verdict = (
        "Dữ liệu baseline qua quality gate và đạt freshness SLA, nên được index vào collection phục vụ chính."
        if quality.get("success") and freshness.get("is_fresh")
        else "Dữ liệu baseline chưa đạt đủ quality gate và freshness SLA; cần xem lại trước khi dùng làm mốc so sánh."
    )
    lines += [
        "## 4. Nhận định",
        f"- {verdict}",
        f"- {hits}/{samples} câu truy xuất đúng tài liệu ground-truth trong top-k; token F1 trung bình "
        f"{_metric(metrics, 'mean_token_f1', 'pct')}. Đây là mốc để so sánh với trạng thái corrupted và repaired.",
        "",
    ]
    write_text(Path(report_path), "\n".join(lines))


def generate_corruption_report(
    report_path: Path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
    baseline_quality: dict[str, Any] | None = None,
    baseline_freshness: dict[str, Any] | None = None,
    corruption_log: dict[str, Any] | None = None,
    corrupted_answers: list[dict[str, Any]] | None = None,
    repair_verification: dict[str, Any] | None = None,
) -> None:
    """Tạo báo cáo đối chiếu 3 trạng thái Baseline vs Corrupted vs Repaired từ số liệu thực tế."""
    samples = int(baseline_metrics.get("samples", 0))
    lines = [
        "# Báo Cáo Đối Chiếu 3 Trạng Thái — Baseline vs Corrupted vs Repaired",
        "",
        "## 1. Bảng đối chiếu",
        "| Chỉ số | Baseline | Corrupted | Repaired |",
        "| :--- | :---: | :---: | :---: |",
        *[
            f"| **{label}** | {_metric(baseline_metrics, key, kind)} | {_metric(corrupted_metrics, key, kind)} "
            f"| {_metric(repaired_metrics, key, kind)} |"
            for key, label, kind in METRIC_ROWS
        ],
        f"| **Quality gate (GX 1.x)** | {_gate(baseline_quality)} | {_gate(corrupted_quality)} | {_gate(repaired_quality)} |",
        f"| **Freshness SLA** | {_freshness(baseline_freshness)} | {_freshness(corrupted_freshness)} "
        f"| {_freshness(repaired_freshness)} |",
        f"| **Judge (LLM / heuristic)** | {_judge_mode(baseline_metrics)} | {_judge_mode(corrupted_metrics)} "
        f"| {_judge_mode(repaired_metrics)} |",
        "",
        f"Cả ba trạng thái được đánh giá trên cùng `data/eval/test_set.json` ({samples} câu hỏi).",
        "",
    ]

    scenarios = (corruption_log or {}).get("scenarios", [])
    doc_scenarios: dict[str, list[str]] = {}
    for scenario in scenarios:
        for paper_id in scenario.get("affected_ids", []):
            doc_scenarios.setdefault(paper_id, []).append(scenario["name"])
    if scenarios:
        lines += [
            "## 2. Kịch bản tiêm lỗi",
            f"Nguồn: `data/results/corruption_log.json` — {corruption_log.get('baseline_rows', '—')} bản ghi baseline "
            f"→ {corruption_log.get('corrupted_rows', '—')} bản ghi sau khi tiêm lỗi.",
            "",
            "| # | Kịch bản | Số bản ghi | Mô tả |",
            "| :-: | :--- | :-: | :--- |",
            *[
                f"| {position} | `{scenario['name']}` | {scenario.get('affected_count', '—')} | {scenario.get('description', '')} |"
                for position, scenario in enumerate(scenarios, start=1)
            ],
            "",
        ]

    answers = corrupted_answers or []
    if answers:
        affected = [item for item in answers if not item["retrieval_hit"] or item["token_f1"] < 1.0]
        unknown = [item for item in affected if str(item["answer"]).startswith(UNKNOWN_ANSWER_PREFIX)]
        confident_wrong = [item for item in affected if item not in unknown]
        lines += [
            "## 3. Tác động lên từng câu hỏi (trạng thái corrupted)",
            f"- {len(answers) - len(affected)}/{len(answers)} câu vẫn trả lời đúng hoàn toàn.",
            f"- {len(unknown)} câu trả lời \"I don't know…\" vì không còn tìm thấy bài được hỏi hoặc nội dung đã bị xoá.",
            f"- {len(confident_wrong)} câu vẫn đưa ra đáp án nhưng sai (silent failure ở tầng câu trả lời).",
            "",
        ]
        if affected:
            lines += [
                "| Câu | Loại | Retrieval hit | Token F1 | Câu trả lời | Kịch bản chạm tới tài liệu ground-truth |",
                "| :-- | :-- | :-: | :-: | :-- | :-- |",
            ]
            for item in affected:
                touched = sorted({name for doc in item["ground_truth_doc_ids"] for name in doc_scenarios.get(doc, [])})
                answer = str(item["answer"]).replace("|", "\\|")
                answer = answer if len(answer) <= 60 else answer[:57] + "..."
                lines.append(
                    f"| {item['id']} | {item['question_type']} | {'có' if item['retrieval_hit'] else 'không'} "
                    f"| {item['token_f1']:.2f} | {answer} | {', '.join(f'`{name}`' for name in touched) or '—'} |"
                )
            lines.append("")

    lines += ["## 4. Phân tích"]
    failed = _failed_expectations(corrupted_quality)
    if failed:
        lines.append(f"- **Quality gate** phát hiện dữ liệu lỗi qua: {', '.join(failed)}.")
    elif corrupted_quality and not corrupted_quality.get("success"):
        lines.append("- **Quality gate** báo FAILED trên dữ liệu corrupted.")
    else:
        lines.append("- **Quality gate** không phát hiện được lỗi nào trên dữ liệu corrupted.")
    if corrupted_freshness:
        lines.append(
            f"- **Freshness SLA** trên dữ liệu corrupted: {corrupted_freshness.get('stale_rows', 0)}/"
            f"{corrupted_freshness.get('total_rows', 0)} bản ghi quá hạn ({_pct(corrupted_freshness.get('stale_ratio', 0))}) "
            f"→ `{'FRESH' if corrupted_freshness.get('is_fresh') else 'STALE'}`."
        )
    if answers:
        if confident_wrong:
            lines.append(
                f"- **Silent failure ở tầng câu trả lời:** {len(confident_wrong)} câu vẫn được trả lời một cách tự tin "
                "nhưng sai; chỉ metric mới lộ ra lỗi này."
            )
        else:
            lines.append(
                "- **Silent failure ở tầng pipeline:** ingest, clean và index dữ liệu bẩn đều chạy không có exception nào; "
                f"các câu sai đều là \"I don't know…\" ({len(unknown)} câu), nên suy giảm chỉ lộ ra qua quality gate, "
                "freshness SLA và metric."
            )
        tested_docs = {doc for item in answers for doc in item["ground_truth_doc_ids"]}
        untouched = [
            scenario["name"]
            for scenario in scenarios
            if scenario.get("affected_ids") and not tested_docs & set(scenario["affected_ids"])
        ]
        if untouched:
            lines.append(
                f"- Kịch bản {', '.join(f'`{name}`' for name in untouched)} không chạm tới tài liệu nào trong test set, "
                "nên không làm thay đổi metric."
            )
        unlisted = [scenario["name"] for scenario in scenarios if not scenario.get("affected_ids")]
        date_answered = [
            item for item in answers if item["question_type"] == "date" and item["retrieval_hit"]
        ]
        if "stale_date" in unlisted:
            lines.append(
                "- `stale_date` áp dụng trên toàn bộ bản ghi còn lại, nhưng không câu hỏi `date` nào còn truy xuất được "
                "tài liệu ground-truth, nên metric không đo được tác động của nó; chỉ freshness SLA phát hiện."
                if not date_answered
                else f"- `stale_date` áp dụng trên toàn bộ bản ghi còn lại; metric đo được tác động của nó qua "
                f"{len(date_answered)} câu hỏi `date` còn truy xuất được tài liệu ground-truth."
            )
    lines.append("")

    lines += ["## 5. Repair"]
    lines.append(
        "- Repair dựng lại toàn bộ dữ liệu từ `data/raw/crossref_records.json` qua cùng hàm cleaning của baseline, "
        "không vá tay các dòng bị lỗi."
    )
    if repair_verification:
        lines.append(
            f"- `data/results/repair_verification.json`: {repair_verification.get('repaired_rows')}/"
            f"{repair_verification.get('baseline_rows')} bản ghi, `paper_id` khớp: "
            f"{repair_verification.get('paper_ids_restored')}, `text_for_embedding` giống hệt: "
            f"{repair_verification.get('identical_text_for_embedding')}/{repair_verification.get('baseline_rows')}, "
            f"trùng lặp: {repair_verification.get('duplicate_paper_ids')} → "
            f"`is_idempotent: {str(repair_verification.get('is_idempotent')).lower()}`."
        )
    diffs = [
        label
        for key, label, _ in METRIC_ROWS
        if key in baseline_metrics and repaired_metrics.get(key) != baseline_metrics.get(key)
    ]
    lines.append(
        "- Metrics sau repair khớp baseline ở cả 4 chỉ số."
        if not diffs
        else f"- Metrics sau repair còn khác baseline ở: {', '.join(diffs)}."
    )
    lines.append("")
    write_text(Path(report_path), "\n".join(lines))
