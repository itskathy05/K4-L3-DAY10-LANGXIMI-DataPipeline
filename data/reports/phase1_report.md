# Báo Cáo Phase 1 — Baseline Pipeline & Observability

## 1. Nguồn Dữ Liệu & Pipeline Ingestion
- **Nguồn:** Crossref REST API
- **Tổng số bản ghi thu thập:** 0
- **Số bản ghi sau làm sạch:** 0

## 2. Kiểm Soát Chất Lượng Dữ Liệu (Data Observability)
- **Great Expectations 1.x:** `PASSED`
- **Số kiểm định đạt:** 6/6
- **Độ tươi mới (Freshness SLA):** `FRESH`
- **Tỉ lệ bản ghi quá hạn (>180 ngày):** 4.2% (1/24)

## 3. Chỉ Số Hiệu Năng RAG (Baseline Metrics)
| Chỉ số | Điểm số |
| :--- | :---: |
| **Retrieval Hit Rate** | 100.0% |
| **Mean Token F1** | 100.0% |
| **LLM Judge Accuracy** | 100.0% |
| **Mean Judge Score (Thang 1-5)** | 5.00 / 5.0 |

> **Nhận định:** Dữ liệu chuẩn sạch cho phép bộ tìm kiếm đạt độ chính xác cao và Agent trả lời chuẩn xác theo ngữ cảnh.
