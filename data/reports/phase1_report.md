# Báo Cáo Phase 1 — Baseline Pipeline & Observability

## 1. Nguồn dữ liệu
- **Nguồn:** Crossref REST API — snapshot offline `data/raw/crossref_records.json`
- **Số bản ghi raw:** 24
- **Số bản ghi sau làm sạch:** 24 (`paper_id` duy nhất: 24)
- **Thời điểm chạy (UTC):** 2026-09-25T09:53:20.298023+00:00

## 2. Data Quality Gate (Great Expectations 1.x) & Freshness SLA
- **Quality gate:** `PASSED (6/6)`
- **Freshness SLA:** `FRESH` — 1/24 bản ghi có `age_days > 180` (4.2%); SLA cho phép tối đa 25%.
- **Bản ghi mới nhất / cũ nhất:** 2026-07-22 / 2026-03-28

## 3. Baseline metrics
Đánh giá trên 10 câu hỏi của `data/eval/test_set.json`, top-k = 4, collection `papers-baseline`.

| Chỉ số | Giá trị |
| :--- | :---: |
| **Retrieval Hit Rate** | 100.0% |
| **Mean Token F1** | 100.0% |
| **Judge Accuracy** | 100.0% |
| **Mean Judge Score (thang 1-5)** | 5.00 |

- **Judge:** `gemini` / `gemini-2.5-flash` — LLM 0/10, heuristic 10/10 câu. Câu dùng heuristic được chấm theo token F1 khi không gọi được LLM, nên với các câu đó `judge_accuracy` không độc lập với `mean_token_f1`.

## 4. Nhận định
- Dữ liệu baseline qua quality gate và đạt freshness SLA, nên được index vào collection phục vụ chính.
- 10/10 câu truy xuất đúng tài liệu ground-truth trong top-k; token F1 trung bình 100.0%. Đây là mốc để so sánh với trạng thái corrupted và repaired.
