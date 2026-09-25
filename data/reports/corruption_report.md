# Báo Cáo Đối Chiếu 3 Trạng Thái — Silent Failure & Idempotent Repair

## 1. Bảng Đối Chiếu Hiệu Năng RAG 3 Trạng Thái
| Chỉ số đánh giá | Trạng Thái 1: Baseline (Sạch) | Trạng Thái 2: Corrupted (Lỗi) | Trạng Thái 3: Repaired (Phục Hồi) |
| :--- | :---: | :---: | :---: |
| **Retrieval Hit Rate** | **100.0%** | 60.0% | **100.0%** |
| **Mean Token F1** | **100.0%** | 50.0% | **100.0%** |
| **Judge Accuracy** | **100.0%** | 50.0% | **100.0%** |
| **Quality Gate Status (GX 1.x)** | PASSED | **FAILED** | **PASSED** |
| **Freshness SLA** | FRESH | **WARNING** | **FRESH** |

## 2. Phân Tích Hiện Tượng Silent Failure
- Khi tiêm 6 dạng lỗi dữ liệu (xóa summary, cắt title, lùi ngày tháng, trùng lặp, nhiễu văn bản), Agent **không hề throw exception** mà vẫn tự tin đưa ra câu trả lời sai sự thật.
- Chỉ số **Retrieval Hit Rate** và **Token F1** sụt giảm rõ rệt trong trạng thái Corrupted.

## 3. Khả Năng Tự Phục Hồi (Idempotent Repair)
- Hệ thống kích hoạt cơ chế Idempotent Repair bằng cách nạp lại dữ liệu nguyên gốc từ bản lưu trữ thô (`data/raw/crossref_records.json`).
- Sau khi làm sạch và đánh chỉ mục lại, hiệu năng hệ thống đạt lại 100% phong độ ban đầu, chứng minh tính bất biến và an toàn của kiến trúc Data Lineage.
