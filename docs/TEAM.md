# Danh Sách Thành Viên & Báo Cáo Phân Công Nhóm

- **Tên Nhóm:** `LANGXIMI`
- **Mã Nhóm / Lớp:** `K4-L3-DAY10`
- **Tên Repository Nộp Bài:** `K4-L3-DAY10-LANGXIMI-DataPipeline`

---

## # Thành viên

| STT | Họ và tên | MSSV | Email | Vai trò & Phân công công việc | Báo cáo cá nhân |
|---:|---|---|---|---|---|
| 1 | Đàm Quang Trung | 2A202602525 | trungdam1305@gmail.com | Pipeline Lead & Integrator (`core/`, `phase1.py`, `corruption_flow.py`) — CP0: môi trường & `.env`; CP3: baseline `phase1.py`; CP4–CP5: `corruption_flow.py` (corruption → repair → so sánh 3 trạng thái); CP6: điều phối demo & kiểm tra contributor | `report/2A202602525_DamQuangTrung.md` |
| 2 | Lê Nguyễn Trâm Anh | 2A202602760 | — | Data Foundation & Recovery (`crossref.py`, `cleaning.py`, raw data) — CP0: thu thập Crossref, retry/backoff và fallback snapshot; CP1: làm sạch, `age_days`, `text_for_embedding`, khử trùng lặp; test `tests/test_data_foundation.py` | `report/2A202602760_LeNguyenTramAnh.md` |
| 3 | Hồ Đăng Phúc | 2A202602796 | — | RAG & Vector Index (`retrieval/index.py`, `embeddings.py`, `qa.py`, `agent.py`, ChromaDB) — CP2: embedding MiniLM, 3 collection ChromaDB tách biệt, truy vấn và QA agent | `report/2A202602796_HoDangPhuc.md` |
| 4 | Nguyễn Thanh Hòa | 2A202602559 | — | Observability & Evaluation (`quality.py` GX 1.x, `testset.py`, `reporting.py`, `corruption.py`) — CP1: quality gate và freshness SLA; CP2: test set 10 câu; CP4: 6 kịch bản tiêm lỗi; CP3–CP5: báo cáo Markdown | `report/2A202602559_NguyenThanhHoa.md` |

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
- **Hoàn thiện cuối (người sửa cuối cùng của repo):**
  - Sửa lỗi ở chế độ live (`REFRESH_SOURCE=1`): lưu lại dữ liệu live vào `data/raw/` để repair dựng lại đúng corpus, tự tạo lại test set khi ground-truth không còn trong corpus; quality gate baseline fail thì dừng trước khi index; `run_corruption_flow.py` exit khác 0 khi repair không khớp baseline.
  - Sửa `reporting.py` để hai báo cáo sinh hoàn toàn từ số liệu thực tế (bỏ các dòng PASSED/FAILED và nhận định gõ cứng, sửa lệch key làm `phase1_report.md` ghi 0 bản ghi); `metrics.py` ghi thêm `judge_fallbacks`.
  - Chạy lại toàn bộ artifact (không API key, judge heuristic nhất quán ở cả 3 trạng thái), dọn file tạm trong `data/quality/` và segment ChromaDB không còn dùng; chuẩn hoá tên báo cáo, cập nhật TEAM.md và báo cáo nhóm.
- **Điều học được / Đóng góp chính:**
  - Repair chỉ thật sự idempotent khi bảo toàn lineage: phải dựng lại từ đúng bản raw đã sinh ra baseline, và cả 3 trạng thái phải đo trên cùng một test set thì phép so sánh mới có ý nghĩa.
  - Tách 3 collection ChromaDB giúp đo tác động của dữ liệu lỗi mà không làm bẩn collection phục vụ chính.

### ## LeNguyenTramAnh-2A202602760
- **Vai trò:** Data Foundation & Recovery (Thành viên 2).
- **Công việc chi tiết đã hoàn thành** (commit `8b77986`, `63adacf`):
  - `src/ingestion/crossref.py`: parse payload Crossref (DOI, title, abstract đã bỏ tag JATS/HTML, tác giả, subject, ngày ISO), gọi API có retry/backoff cho 429/5xx và tự rơi về snapshot trong `data/raw/` khi lỗi mạng.
  - `src/ingestion/cleaning.py`: chuẩn hoá văn bản, khử trùng lặp theo `paper_id`, loại bản ghi thiếu DOI/title hoặc summary dưới 30 ký tự, tính `age_days`, ghép `text_for_embedding` 5 phần; kết quả tất định (sắp theo `paper_id`) nên repair dựng lại được y hệt.
  - `tests/test_data_foundation.py`: 5 test cho parse, cleaning, khử trùng lặp, repair lặp lại và fallback khi API lỗi.
  - Tạo repo nhóm trên tài khoản GitHub `itskathy05`.
- **Điều học được / Đóng góp chính:** _(thành viên tự bổ sung)_

### ## HoDangPhuc-2A202602796
- **Vai trò:** RAG & Vector Index (Thành viên 3).
- **Công việc chi tiết đã hoàn thành** (commit `12ef630`):
  - `src/retrieval/index.py`: 3 collection ChromaDB tách biệt (xoá và tạo lại mỗi lần build), kiểm tra số bản ghi khớp manifest, tìm kiếm dense (cosine) và hybrid (TF-IDF + dense, RRF), manifest dùng đường dẫn tương đối.
  - `src/retrieval/embeddings.py`: embedding `all-MiniLM-L6-v2` đã chuẩn hoá, kiểm tra đầu vào rỗng.
  - `src/retrieval/qa.py`: tra đúng bài theo tên hoặc DOI trong câu hỏi, trả lời "I don't know" khi không tìm thấy thay vì đoán.
  - `src/retrieval/agent.py`: agent LangChain với 2 tool (tìm kiếm, tra cứu) và agent mock tất định khi `LLM_PROVIDER=mock`.
- **Điều học được / Đóng góp chính:** _(thành viên tự bổ sung)_

### ## NguyenThanhHoa-2A202602559
- **Vai trò:** Observability & Evaluation (Thành viên 4).
- **Công việc chi tiết đã hoàn thành** (commit `b435257`, `662deda`):
  - `src/observability/quality.py`: quality gate Great Expectations 1.x (ephemeral context, 6 expectation) và Freshness SLA (`age_days > 180`, ngưỡng 25%).
  - `src/evaluation/testset.py`: test set 10 câu (3 summary, 3 authors, 2 date, 2 categories) kèm ground truth và DOI.
  - `src/ingestion/corruption.py`: 6 kịch bản tiêm lỗi và `data/results/corruption_log.json`.
  - `src/observability/reporting.py`: bản đầu của `phase1_report.md` và `corruption_report.md`.
  - Chạy pipeline lần đầu, commit artifact và viết `report/group_report.md`.
- **Điều học được / Đóng góp chính:** _(thành viên tự bổ sung)_
