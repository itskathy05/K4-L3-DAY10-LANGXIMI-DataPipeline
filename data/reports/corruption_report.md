# Báo Cáo Đối Chiếu 3 Trạng Thái — Baseline vs Corrupted vs Repaired

## 1. Bảng đối chiếu
| Chỉ số | Baseline | Corrupted | Repaired |
| :--- | :---: | :---: | :---: |
| **Retrieval Hit Rate** | 100.0% | 60.0% | 100.0% |
| **Mean Token F1** | 100.0% | 50.0% | 100.0% |
| **Judge Accuracy** | 100.0% | 50.0% | 100.0% |
| **Mean Judge Score (thang 1-5)** | 5.00 | 3.00 | 5.00 |
| **Quality gate (GX 1.x)** | PASSED (6/6) | FAILED (4/6) | PASSED (6/6) |
| **Freshness SLA** | FRESH (4.2% quá hạn) | STALE (100.0% quá hạn) | FRESH (4.2% quá hạn) |
| **Judge (LLM / heuristic)** | LLM 0/10, heuristic 10/10 | LLM 0/10, heuristic 10/10 | LLM 0/10, heuristic 10/10 |

Cả ba trạng thái được đánh giá trên cùng `data/eval/test_set.json` (10 câu hỏi).

## 2. Kịch bản tiêm lỗi
Nguồn: `data/results/corruption_log.json` — 24 bản ghi baseline → 22 bản ghi sau khi tiêm lỗi.

| # | Kịch bản | Số bản ghi | Mô tả |
| :-: | :--- | :-: | :--- |
| 1 | `drop_latest_records` | 4 | Dropped ~20% of latest records to simulate stale ingestion & missing documents. |
| 2 | `blank_summary` | 2 | Erased summaries on records to trigger schema length validation failure. |
| 3 | `inject_noise` | 2 | Injected random corruption tokens to degrade retrieval precision and Token F1. |
| 4 | `truncate_title` | 2 | Truncated paper titles to fewer than 8 characters. |
| 5 | `stale_date` | 20 | Shifted publication dates back by 365 days (age_days > 180) to violate Freshness SLA. |
| 6 | `duplicate_rows` | 2 | Appended duplicate rows to cause ghost vectors and unique ID constraint violations. |

## 3. Tác động lên từng câu hỏi (trạng thái corrupted)
- 5/10 câu vẫn trả lời đúng hoàn toàn.
- 5 câu trả lời "I don't know…" vì không còn tìm thấy bài được hỏi hoặc nội dung đã bị xoá.
- 0 câu vẫn đưa ra đáp án nhưng sai (silent failure ở tầng câu trả lời).

| Câu | Loại | Retrieval hit | Token F1 | Câu trả lời | Kịch bản chạm tới tài liệu ground-truth |
| :-- | :-- | :-: | :-: | :-- | :-- |
| eval_002 | summary | có | 0.00 | I don't know from the indexed corpus. | `blank_summary`, `duplicate_rows` |
| eval_004 | authors | không | 0.00 | I don't know from the indexed corpus. | `drop_latest_records` |
| eval_007 | date | không | 0.00 | I don't know from the indexed corpus. | `drop_latest_records` |
| eval_008 | date | không | 0.00 | I don't know from the indexed corpus. | `drop_latest_records` |
| eval_010 | categories | không | 0.00 | I don't know from the indexed corpus. | `truncate_title` |

## 4. Phân tích
- **Quality gate** phát hiện dữ liệu lỗi qua: `expect_column_values_to_be_unique` trên cột `paper_id`, `expect_column_value_lengths_to_be_between` trên cột `summary`.
- **Freshness SLA** trên dữ liệu corrupted: 22/22 bản ghi quá hạn (100.0%) → `STALE`.
- **Silent failure ở tầng pipeline:** ingest, clean và index dữ liệu bẩn đều chạy không có exception nào; các câu sai đều là "I don't know…" (5 câu), nên suy giảm chỉ lộ ra qua quality gate, freshness SLA và metric.
- Kịch bản `inject_noise` không chạm tới tài liệu nào trong test set, nên không làm thay đổi metric.
- `stale_date` áp dụng trên toàn bộ bản ghi còn lại, nhưng không câu hỏi `date` nào còn truy xuất được tài liệu ground-truth, nên metric không đo được tác động của nó; chỉ freshness SLA phát hiện.

## 5. Repair
- Repair dựng lại toàn bộ dữ liệu từ `data/raw/crossref_records.json` qua cùng hàm cleaning của baseline, không vá tay các dòng bị lỗi.
- `data/results/repair_verification.json`: 24/24 bản ghi, `paper_id` khớp: True, `text_for_embedding` giống hệt: 24/24, trùng lặp: 0 → `is_idempotent: true`.
- Metrics sau repair khớp baseline ở cả 4 chỉ số.
