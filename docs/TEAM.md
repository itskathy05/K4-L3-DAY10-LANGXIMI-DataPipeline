# Danh Sách Thành Viên & Báo Cáo Phân Công Nhóm

- **Tên Nhóm:** `[Điền tên nhóm]`
- **Mã Nhóm / Lớp:** `K4-L3-DAY10`
- **Tên Repository Nộp Bài:** `K4-L3-DAY10-TenNhom-DataPipeline`

---

## # Thành viên

| STT | Họ và tên | MSSV | Email | Vai trò & Phân công công việc | Báo cáo cá nhân |
|---:|---|---|---|---|---|
| 1 | Đàm Quang Trung | 2A202602525 | trungdam1305@gmail.com | Pipeline Lead & Integrator (`core/`, `phase1.py`, `corruption_flow.py`) — CP0: môi trường & `.env`; CP3: baseline `phase1.py`; CP4–CP5: `corruption_flow.py` (corruption → repair → so sánh 3 trạng thái); CP6: điều phối demo & kiểm tra contributor | `report/2A202602525_DamQuangTrung.md` |
| 2 | | | | Data Foundation & Recovery (`crossref.py`, `cleaning.py`, raw data) | `report/<MSSV2>_HoTen.md` |
| 3 | | | | RAG & Vector Index (`retrieval/index.py`, `embeddings.py`, ChromaDB) | `report/<MSSV3>_HoTen.md` |
| 4 | | | | Observability & Evaluation (`quality.py` GX 1.x, `testset.py`, reporting) | `report/<MSSV4>_HoTen.md` |

*(Nếu nhóm có 3 hoặc 5-6 thành viên, xem bảng phân công chi tiết theo vai trò trong file `CHECKPOINTS.md`)*.

---

## # Cá nhân

### ## DamQuangTrung-2A202602525
- **Vai trò:** Pipeline Lead & Integrator — điều phối luồng dữ liệu end-to-end (`core/`, `src/pipelines/`).
- **Công việc chi tiết đã hoàn thành:**
  - CP0: dựng môi trường `.venv` + `pip install -e .`, cấu hình `.env` từ `.env.example` (không commit secret).
  - `core/`: mọi đường dẫn artifact lấy tập trung từ `core/config.py` (không hardcode path); bổ sung `dataframe_records()` trong `core/utils.py` để xuất JSON an toàn kiểu dữ liệu (numpy/NaN/timestamp).
  - CP3 — `src/pipelines/phase1.py`: ingestion (snapshot, hoặc live khi `REFRESH_SOURCE=1`) → cleaning + kiểm tra schema (`validate_clean_schema`) → quality gate GX 1.x + freshness → index ChromaDB `papers-baseline` → test set cố định + evaluate → `phase1_report.md`; demo agent tùy chọn, tự bỏ qua khi thiếu API key.
  - CP4–CP5 — `src/pipelines/corruption_flow.py`: tiêm lỗi → đo suy giảm trên collection riêng `papers-corrupted` → repair idempotent từ `data/raw/crossref_records.json` → `papers-repaired` → kiểm chứng repair (`data/results/repair_verification.json`) → báo cáo và bảng so sánh 3 trạng thái trên console; cả 3 trạng thái dùng chung `data/eval/test_set.json`.
  - Kiểm thử tích hợp với code thật của thành viên 2 (`crossref.py`, `cleaning.py`) và thành viên 3 (`retrieval/`), dùng bản tạm (stub) cho các module còn TODO: cả hai lệnh exit 0, đủ artifact, repair khớp 24/24 bản ghi; 5/5 test của thành viên 2 vẫn pass.
- **Trạng thái / việc còn lại:**
  - Chưa chạy end-to-end thật: còn chờ `quality.py`, `testset.py`, `reporting.py` và `corruption.py`.
  - Chế độ live (`REFRESH_SOURCE=1`) còn lỗi lineage: repair dựng lại từ snapshot cũ và test set cũ bị dùng lại cho corpus mới — cần phối hợp với thành viên 2 để lưu raw khi fetch live.
- **Điều học được / Đóng góp chính:**
  - Repair chỉ thật sự idempotent khi bảo toàn lineage: phải dựng lại từ đúng bản raw đã sinh ra baseline, và cả 3 trạng thái phải đo trên cùng một test set thì phép so sánh mới có ý nghĩa.
  - Tách 3 collection ChromaDB giúp đo tác động của dữ liệu lỗi mà không làm bẩn collection phục vụ chính.

### ## HoVaTen2-MSSV2
- **Vai trò:** Phụ trách Ingestion, Làm sạch & Phục hồi dữ liệu.
- **Công việc chi tiết đã hoàn thành:**
  - Xây dựng module thu thập Crossref API với cơ chế Fallback offline trong `src/ingestion/crossref.py`.
  - Chuẩn hóa schema, tính toán trường `age_days` và `text_for_embedding` trong `src/ingestion/cleaning.py`.
  - Thực thi cơ chế Idempotent Repair phục hồi dữ liệu từ raw snapshot.
- **Điều học được / Đóng góp chính:**
  - Kỹ thuật truy vết nguồn gốc dữ liệu (Data Lineage) và bảo toàn raw snapshot trước khi biến đổi.

### ## HoVaTen3-MSSV3
- **Vai trò:** Phụ trách RAG, Vector Database & Embedding.
- **Công việc chi tiết đã hoàn thành:**
  - Quản lý mô hình embedding `sentence-transformers/all-MiniLM-L6-v2`.
  - Nạp và quản lý 3 collection riêng biệt trong ChromaDB (`papers-baseline`, `papers-corrupted`, `papers-repaired`).
  - Xây dựng QA Agent truy vấn ngữ cảnh chính xác theo tài liệu.
- **Điều học được / Đóng góp chính:**
  - Cách cô lập các không gian vector để so sánh khách quan giữa dữ liệu sạch và dữ liệu bị lỗi.

### ## HoVaTen4-MSSV4
- **Vai trò:** Phụ trách Data Observability & Benchmark Evaluation.
- **Công việc chi tiết đã hoàn thành:**
  - Thiết lập Quality Gate theo chuẩn mới **Great Expectations 1.x** và giám sát Freshness SLA trong `src/observability/quality.py`.
  - Xây dựng bộ câu hỏi đánh giá chuẩn trong `src/evaluation/testset.py`.
  - Đo lường và xuất bảng đối chiếu 3 trạng thái vào `data/reports/corruption_report.md`.
- **Điều học được / Đóng góp chính:**
  - Cách thiết lập hệ thống cảnh báo sớm chặn đứng hiện tượng Silent Failure trước khi dữ liệu vào serving layer.
