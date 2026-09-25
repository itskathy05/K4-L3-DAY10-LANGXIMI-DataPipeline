# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Khóa/Lớp         | K4-L3-DAY10              |
| Tên nhóm         | LANGXIMI                 |
| Repository         | https://github.com/itskathy05/K4-L3-DAY10-LANGXIMI-DataPipeline |
| Ngày hoàn thành | 2026-09-25               |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Đàm Quang Trung | 2A202602525 | Pipeline Lead & Integrator | `core/`, `src/pipelines/phase1.py`, `corruption_flow.py` |
| 2 | Lê Nguyễn Trâm Anh | 2A202602760 | Data Foundation & Recovery | `src/ingestion/crossref.py`, `cleaning.py`, raw data snapshot |
| 3 | Hồ Đăng Phúc | 2A202602796 | RAG & Vector Index | `src/retrieval/index.py`, `embeddings.py`, ChromaDB |
| 4 | Nguyễn Thanh Hòa | 2A202602559 | Observability & Evaluation | `src/observability/quality.py`, `testset.py`, `reporting.py` |

## 2. Tóm tắt kết quả

Nhóm đã hoàn thành trọn vẹn toàn bộ 7 mốc Checkpoint (CP0 – CP6) của bài lab theo đúng tiến trình chuẩn:

1. **Baseline Pipeline (Pha 1):** Xây dựng thành công pipeline thu thập dữ liệu Crossref Academic (24 bản ghi snapshot), chuẩn hóa làm sạch loại bỏ mã JATS XML, tạo trường `text_for_embedding`, lưu trữ an toàn `data/clean/papers_clean.csv`. Hệ thống thiết lập chốt kiểm dịch Great Expectations 1.x (vượt qua 6/6 Expectations) và đạt chuẩn Freshness SLA (chỉ 4.2% quá hạn $\le$ 25%). Đánh chỉ mục vào ChromaDB (`papers-baseline`) và đánh giá trên bộ 10 câu hỏi benchmark chuẩn đạt kết quả tuyệt đối: **Retrieval Hit Rate = 100%**, **Mean Token F1 = 100%**.
2. **Thử thách Tiêm Lỗi Dữ Liệu (Pha 2 - Data Corruption):** Triển khai trọn vẹn 6 kịch bản tiêm lỗi thực tế trong `src/ingestion/corruption.py`. Kết quả đã chứng minh rõ hiện tượng nguy hiểm **Silent Failure**: AI không hề báo lỗi đỏ nhưng hiệu năng sụt giảm nghiêm trọng (**Hit Rate giảm xuống 60%**, **Token F1 giảm xuống 50%**). Chốt kiểm dịch Great Expectations 1.x và Freshness SLA lập tức phát hiện và gióng chuông cảnh báo (`quality_gate: FAILED`, `freshness: WARNING`).
3. **Phục Hồi Dữ Liệu An Toàn (Idempotent Repair):** Kích hoạt cơ chế tự phục hồi từ bản lưu trữ thô nguyên thủy (`data/raw/crossref_records.json`). Hệ thống chứng minh tính bất biến tuyệt đối (`is_idempotent: True`), khôi phục 100% phong độ ban đầu và xuất bản báo cáo đối chiếu định lượng 3 trạng thái đầy đủ tại `data/reports/corruption_report.md`.

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref API (hoặc Snapshot Offline data/raw/crossref_records.json)
    ├── 1. Ingestion & Raw Preservation -> data/raw/crossref_records.json
    ├── 2. Transformation & Cleaning   -> data/clean/papers_clean.csv (.json)
    ├── 3. Data Quality Gate           -> Great Expectations 1.x & Freshness SLA
    ├── 4. Semantic Embedding & Index  -> all-MiniLM-L6-v2 + ChromaDB
    ├── 5. Evaluation Benchmark        -> data/eval/test_set.json (Hit Rate, F1)
    ├── 6. Synthetic Corruption        -> 6 kịch bản lỗi & data/results/corruption_log.json
    └── 7. Idempotent Repair           -> Khôi phục từ Raw & xuất corruption_report.md
```

### Trách nhiệm của từng khối

| Khối             | Input          | Xử lý chính             | Output/artifact          | Owner          |
| ----------------- | -------------- | -------------------------- | ------------------------ | -------------- |
| Ingestion         | Crossref REST API / Snapshot | Bóc tách payload, fallback snapshot khi mất mạng, lưu raw | `data/raw/crossref_records.json`, `crossref_response.json` | Thành viên 2 |
| Cleaning          | Raw PaperRecords | Khử trùng lặp `paper_id`, bỏ JATS tags, tính `age_days`, tạo embedding text | `data/clean/papers_clean.csv`, `papers_clean.json` | Thành viên 2 |
| Embedding/index   | Cleaned DataFrame | Tạo vector MiniLM 384-dim, nạp 3 collection ChromaDB tách biệt | `data/chroma/`, `papers-baseline`, `corrupted`, `repaired` | Thành viên 3 |
| Evaluation        | Cleaned DataFrame, Chroma Index | Sinh 10 câu hỏi chuẩn (4 loại), tính Hit Rate, Token F1, LLM Judge | `data/eval/test_set.json`, `baseline_metrics.json` | Thành viên 4 |
| Observability     | DataFrame theo từng stage | Ephemeral GX 1.x suite (6 expectations), Freshness SLA monitor | `data/quality/*_quality_report.json`, `freshness_report.json` | Thành viên 4 |
| Corruption/repair | Clean DataFrame, Raw snapshot | Tiêm 6 dạng lỗi dữ liệu; khôi phục idempotent từ Raw records | `corruption_log.json`, `papers_clean_corrupted.csv`, `repaired.csv` | Thành viên 2 & 4 |
| Orchestration     | Toàn bộ các module | Điều phối luồng Phase 1 và Phase 2 end-to-end, so sánh 3 trạng thái | `script/run_phase1.py`, `script/run_corruption_flow.py`, reports | Thành viên 1 |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình             | Giá trị sử dụng |
| ---------------------------- | ------------------- |
| `LLM_PROVIDER`             | `gemini` (hoặc mock fallback) |
| `LLM_MODEL`                | `gemini-2.5-flash`  |
| Embedding model              | `sentence-transformers/all-MiniLM-L6-v2` |
| Số lượng Crossref records | 24 bài báo khoa học |
| Retrieval `top_k`           | 4                   |
| Freshness threshold          | 180 ngày (SLA $\le 25\%$ quá hạn) |
| Random seed, nếu có        | Mặc định ổn định    |

### Lệnh cài đặt

```bash
python -m pip install -e .
```

### Lệnh chạy

1. Chạy toàn tuyến Baseline (Phase 1):
```bash
python script/run_phase1.py
```

2. Chạy toàn tuyến Corruption, Repair & So sánh 3 trạng thái (Phase 2):
```bash
python script/run_corruption_flow.py
```

### Kết quả tái hiện

| Lệnh             | Trạng thái                                    | Thời điểm chạy gần nhất | Bằng chứng                         |
| ----------------- | ----------------------------------------------- | ----------------------------- | ------------------------------------ |
| Baseline pipeline | Thành công (Exit code 0) | 2026-09-25 15:35 | `data/results/baseline_metrics.json`, `data/reports/phase1_report.md` |
| Corruption flow   | Thành công (Exit code 0) | 2026-09-25 16:05 | `data/results/corrupted_metrics.json`, `repaired_metrics.json`, `corruption_report.md` |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính                | Giá trị                             |
| --------------------------- | ------------------------------------- |
| Source                      | Crossref REST API (`https://api.crossref.org/works`) & Local snapshot fallback |
| Query/filter                | `query=retrieval augmented generation`, `filter=has-abstract:true` |
| Thời điểm lấy dữ liệu | 2026-09-25                            |
| Số record nhận được    | 24 bản ghi                            |
| Cơ chế retry/backoff      | Urllib3 Retry (3 lần, backoff factor 0.5, bắt lỗi 429/500/502/503/504) và tự động fallback sang local snapshot |

### Raw và clean schema

| Trường        | Kiểu dữ liệu | Bắt buộc?  | Ý nghĩa   | Xử lý khi thiếu/sai |
| --------------- | --------------- | ------------ | ----------- | ---------------------- |
| `paper_id` | `str` | Có | Mã định danh DOI chuẩn hóa chữ thường | Bỏ qua dòng nếu thiếu |
| `title` | `str` | Có | Tiêu đề bài báo đã làm sạch tag | Bỏ qua dòng nếu rỗng |
| `summary` | `str` | Có | Tóm tắt nội dung khoa học | Bỏ qua nếu độ dài < 30 ký tự |
| `authors_joined` | `str` | Không | Danh sách tác giả ngăn cách bởi dấu phẩy | Để trống nếu không có tác giả |
| `categories_joined` | `str` | Không | Danh sách lĩnh vực chuyên môn | Để trống nếu không có |
| `published` | `str` (ISO-8601) | Có | Ngày xuất bản chuẩn định dạng YYYY-MM-DD | Bỏ qua dòng nếu parse ngày lỗi |
| `age_days` | `int` | Có | Số ngày tuổi tính từ run_date đến ngày xuất bản | Tính tự động từ `(run_date - published).days` |
| `text_for_embedding` | `str` | Có | Ngữ cảnh 5 phần ghép nối để nhúng vector | Sinh tự động theo cấu trúc định sẵn |

### Quy tắc cleaning

| Quy tắc                                 | Quality dimension liên quan | Số record bị tác động | Cách xác minh      |
| ---------------------------------------- | ---------------------------- | -------------------------: | -------------------- |
| Bóc tách và xóa thẻ `<jats:p>`, HTML tags | Validity / Conformance       | 24 | Regex `re.sub(r"<[^>]*>", " ", unescape(v))` |
| Chuẩn hóa khoảng trắng dư thừa           | Consistency                  | 24 | Hàm `normalize_whitespace` |
| Bỏ qua record thiếu DOI, title hoặc summary < 30 chars | Completeness / Validity | 0 | Kiểm tra kích thước DataFrame giữ vững 24 dòng |
| Khử trùng lặp khóa duy nhất `paper_id`   | Uniqueness                   | 0 (sạch) | Đảm bảo `seen_ids` độc nhất |
| Tính toán `age_days` theo ngày chạy     | Timeliness                   | 24 | Kiểm tra `age_days >= 0` |

**Cách tạo `text_for_embedding`:**
Được ghép chuẩn hóa 5 khối ngữ cảnh:
```text
Title: <title>
Authors: <authors_joined>
Published: <published>
Categories: <categories_joined>
Summary: <summary>
```

## 6. Evaluation setup

| Thành phần                             | Cấu hình thực tế          |
| ---------------------------------------- | ----------------------------- |
| Số câu hỏi                            | 10 câu hỏi đối chiếu (Ground Truth) |
| Các `question_type`                    | `summary` (3 câu), `authors` (3 câu), `date` (2 câu), `categories` (2 câu) |
| Ground-truth document ID                 | Mã DOI chính xác của bài báo tương ứng chứa câu trả lời |
| Embedding model                          | `sentence-transformers/all-MiniLM-L6-v2` (384 chiều) |
| Vector store/collection                  | ChromaDB: `papers-baseline`, `papers-corrupted`, `papers-repaired` |
| Retrieval `top_k`                       | 4                             |
| LLM provider/model                       | `gemini` (`gemini-2.5-flash`) kèm heuristic fallback an toàn |
| Test set dùng chung cho ba trạng thái | `data/eval/test_set.json` (Cố định, bất biến) |

**Lý do giữ nguyên test set qua 3 trạng thái:**
Để đánh giá khách quan và khoa học mức độ suy giảm do lỗi dữ liệu và năng lực phục hồi, bộ đề thi (evaluation benchmark) bắt buộc phải là biến cố định (controlled variable). Nếu thay đổi test set, sự sụt giảm chỉ số sẽ bị nhiễu và không thể quy kết cho lỗi dữ liệu (Data Corruption).

## 7. Kết quả baseline

### Artifact checklist

| Artifact                 | Đường dẫn thực tế                | Trạng thái | Ghi chú   |
| ------------------------ | -------------------------------------- | ------------ | ---------- |
| Raw response/records     | `data/raw/`                          | Có | Đủ `crossref_response.json` và `crossref_records.json` |
| Cleaned dataset          | `data/clean/`                        | Có | Đủ `papers_clean.csv` và `papers_clean.json` (24 dòng) |
| Embedding manifest/index | `data/chroma/`                       | Có | PersistentClient chứa collection `papers-baseline` |
| Evaluation set           | `data/eval/`                         | Có | Đủ `test_set.json` (10 câu hỏi) |
| Baseline metrics         | `data/results/baseline_metrics.json` | Có | Hit rate = 1.000, Token F1 = 1.000 |
| Quality/freshness        | `data/quality/`                      | Có | `baseline_quality_report.json`, `freshness_report.json` |
| Baseline report          | `data/reports/phase1_report.md`      | Có | Báo cáo Markdown chi tiết số liệu Pha 1 |

### Baseline metrics

| Metric                 |       Giá trị | Diễn giải                             |
| ---------------------- | --------------: | --------------------------------------- |
| `retrieval_hit_rate` |     **1.000 (100%)** | 10/10 câu hỏi truy xuất chính xác tài liệu chứa đáp án trong Top 4 |
| `mean_token_f1`      |     **1.000 (100%)** | Câu trả lời của Agent trùng khớp hoàn hảo với Ground Truth |
| `judge_accuracy`     |     **1.000 (100%)** | Đánh giá tính chính xác đạt mức tuyệt đối |
| `mean_judge_score`   |     **5.000 / 5.0**  | Điểm chất lượng trung bình tối đa |
| Ragas, nếu có        | Skipped | Tối ưu thời gian chạy bằng Heuristic & LLM Judge chuẩn hóa |

## 8. Data quality và freshness

### Quality checks (Great Expectations 1.x)

| Check | Quality dimension | Ngưỡng/kỳ vọng | Kết quả baseline | Bằng chứng |
| ------------ | ----------------- | ------------------ | ----------------------- | ------------ |
| `ExpectTableRowCountToBeBetween` | Completeness | 5 đến 5000 dòng | **Passed** (24 dòng) | `data/quality/baseline_quality_report.json` |
| `ExpectColumnValuesToNotBeNull` (`paper_id`) | Completeness | 0% null | **Passed** (0% null) | `data/quality/baseline_quality_report.json` |
| `ExpectColumnValuesToNotBeNull` (`title`) | Completeness | 0% null | **Passed** (0% null) | `data/quality/baseline_quality_report.json` |
| `ExpectColumnValuesToNotBeNull` (`text_for_embedding`) | Completeness | 0% null | **Passed** (0% null) | `data/quality/baseline_quality_report.json` |
| `ExpectColumnValuesToBeUnique` (`paper_id`) | Uniqueness | 100% unique | **Passed** (24/24 unique) | `data/quality/baseline_quality_report.json` |
| `ExpectColumnValueLengthsToBeBetween` (`summary`) | Validity / Conformance | Min 30 ký tự | **Passed** (Tất cả $\ge 30$) | `data/quality/baseline_quality_report.json` |

### Freshness SLA

| Thuộc tính               | Giá trị                           |
| -------------------------- | ----------------------------------- |
| Freshness được đo tại | Cột `age_days` trong `data/clean/papers_clean.json` |
| Timestamp mới nhất       | `2026-07-22` (cũ nhất: `2026-03-28`) |
| Ngưỡng freshness         | 180 ngày; tỉ lệ quá hạn cho phép $\le 25\%$ |
| Trạng thái baseline      | **FRESH (`is_fresh = True`)**       |
| Lý do                     | Chỉ có 1/24 bài báo quá hạn 180 ngày (tỉ lệ $4.2\% \le 25\%$) |

## 9. Corruption scenarios và repair

| Corruption | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair |
| ------------------ | ---------- | ---------------------: | ------------------------ | --------------------- | -------------- |
| 1. Drop latest records | Bỏ rơi 20% bài báo mới nhất | 4 bài | Data size sụt giảm | Hit rate giảm mạnh do thiếu tài liệu | Nạp lại đầy đủ từ snapshot thô |
| 2. Blank summary | Xóa rỗng trường `summary` | 2 bài | Vi phạm GX min length | Token F1 sụt giảm nghiêm trọng | Đọc lại tóm tắt nguyên bản từ raw |
| 3. Inject noise | Chèn chuỗi ký tự rác vào tóm tắt | 2 bài | Nhiễu ngữ nghĩa vector | Giảm độ tương đồng cosine | Làm sạch lại từ bản ghi gốc |
| 4. Truncate title | Cắt ngắn tiêu đề xuống < 8 ký tự | 2 bài | Mất thông tin định danh | Agent khó trích xuất context | Khôi phục tiêu đề đầy đủ |
| 5. Stale date | Lùi ngày xuất bản 365 ngày trước | 20 bài | Vi phạm Freshness SLA | Hệ thống báo động STALE WARNING | Tính toán lại ngày từ timestamp raw |
| 6. Duplicate rows | Nhân bản bản ghi tạo trùng ID | 2 bài | Vi phạm GX unique ID | Gây ghost vectors trong ChromaDB | Khử trùng lặp qua logic `seen_ids` |

**Corruption log:**
- Đường dẫn: `data/results/corruption_log.json`
- Trạng thái: Có đầy đủ.
- Nhận xét: Log ghi nhận chi tiết 6 kịch bản, danh sách `affected_ids` cụ thể, số dòng baseline (24) và số dòng corrupted (22).

**Nguyên tắc phục hồi an toàn (Idempotent Repair):**
Quy trình repair tuyệt đối không sửa thủ công (patch tay) trên dữ liệu bẩn. Thay vào đó, pipeline đọc lại toàn bộ dữ liệu từ bản lưu trữ nguồn nguyên thủy không thể thay đổi (`data/raw/crossref_records.json`), chạy lại hàm làm sạch chuẩn và ghi đè đồng bộ lên serving layer. Cơ chế này đảm bảo tính Idempotent: chạy 1 lần hay 100 lần kết quả vẫn luôn đồng nhất và sạch bóng.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal            | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét   |
| ------------------------ | -------: | --------: | -------: | -----------------------: | --------------: | ------------ |
| `retrieval_hit_rate`   | **1.000** | **0.600** | **1.000** | **-40.0%** | **100% phục hồi** | Bị ảnh hưởng nặng do mất tài liệu mới |
| `mean_token_f1`        | **1.000** | **0.500** | **1.000** | **-50.0%** | **100% phục hồi** | Sụt giảm do summary rỗng và nhiễu văn bản |
| `judge_accuracy`       | **1.000** | **0.500** | **1.000** | **-50.0%** | **100% phục hồi** | Điểm chính xác giảm tương ứng |
| `mean_judge_score`     | **5.000** | **3.000** | **5.000** | **-2.000** | **100% phục hồi** | Đánh giá chất lượng tụt từ Xuất sắc xuống Trung bình |
| Quality checks pass/fail | **True**  | **False** | **True**  | Báo động FAILED | Trở lại PASSED | GX 1.x bắt lỗi vi phạm length & unique |
| Freshness status         | **True**  | **False** | **True**  | STALE WARNING | Trở lại FRESH | Tỉ lệ mốc meo vọt lên 100% rồi về lại 4.2% |

### Hai kết luận nhân quả cốt lõi:
1. **Dữ liệu lỗi $\rightarrow$ Silent Failure $\rightarrow$ Quality Gate gióng chuông:** Khi tiêm lỗi dữ liệu, Agent vẫn trả lời bình thường mà không hề crash, nhưng độ chính xác Hit Rate sụt tới 40% và F1 sụt 50%. Nhờ có chốt kiểm dịch Great Expectations 1.x và Freshness SLA, sự cố được phát hiện ngay lập tức ở tầng dữ liệu trước khi lọt vào sản phẩm phục vụ người dùng.
2. **Idempotent Repair $\rightarrow$ Khôi phục toàn vẹn 100%:** Khi kích hoạt cơ chế tự phục hồi từ raw snapshot, dữ liệu sạch được tái lập hoàn toàn, đưa toàn bộ chỉ số Retrieval Hit Rate, Token F1, và Quality Gate trở lại 100% phong độ ban đầu (`is_idempotent: True`).

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** Khi chạy script kiểm thử riêng lẻ trong thư mục `tests/` hoặc khi gọi module `corruption.py`, chương trình gặp lỗi `ModuleNotFoundError: No module named 'core'` và `NotImplementedError` tại hàm tiêm lỗi.
- **Nguyên nhân:** Khi chạy file từ thư mục con, Python chỉ tìm kiếm package trong thư mục con đó mà chưa nhận diện thư mục `src/`. Đồng thời, module `corruption.py` mới chỉ có code khung.
- **Cách xử lý:** 
  1. Thêm cấu hình đường dẫn `sys.path.insert(0, ...)` trỏ chính xác về thư mục `src/` trong các script kiểm thử.
  2. Cài đặt trọn vẹn 6 kịch bản tiêm độc tố dữ liệu và tái tạo embedding trong `src/ingestion/corruption.py`.
- **Cách xác minh:** Chạy thành công lệnh `python script/run_phase1.py` và `python script/run_corruption_flow.py` với exit code 0, toàn bộ artifact được kiểm chứng `[ok]`.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng   | Hướng cải thiện có thể kiểm chứng |
| --------------------- | -------------- | ----------------------------------------- |
| Corpus hiện tại có quy mô 24 bài báo | Chưa bao quát toàn bộ độ trễ khi scale dữ liệu lớn | Mở rộng scale ingestion lên 500-1000 bài báo để kiểm thử tải của ChromaDB |
| Freshness SLA kiểm tra theo mốc ngày cố định | Cần cập nhật ngày hiện tại để đo độ tươi liên tục | Tích hợp cron job định kỳ chạy automated freshness monitoring hàng ngày |
| LLM Judge phụ thuộc hạn ngạch API ngoài | Có thể gặp lỗi `429 Too Many Requests` khi vượt quota | Tích hợp local LLM (Ollama) làm judge offline để độc lập hoàn toàn với cloud API |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [x] Phân công khớp với module, artifact và kết quả thực tế.
- [x] Lệnh tái hiện đã được chạy lại thành công trên phiên bản nộp bài.
- [x] Baseline, corrupted và repaired dùng chung bộ evaluation test set chuẩn.
- [x] Bảng metrics khớp 100% với các file trong `data/results/`.
- [x] Quality/freshness conclusions khớp 100% với `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact sinh ra đầy đủ, hợp lệ.
- [x] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng.
- [x] Không có `.env`, API key, token hoặc secret trong source code hay báo cáo.
