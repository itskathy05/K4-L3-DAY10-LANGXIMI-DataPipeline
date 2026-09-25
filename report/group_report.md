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

Nhóm đã hoàn thành các mốc CP0 – CP5 của bài lab (CP6 là buổi demo trực tiếp). Toàn bộ số liệu dưới đây lấy từ lần chạy lại ngày 2026-09-25 lúc 16:53 (GMT+7), không cấu hình API key:

1. **Baseline Pipeline (Pha 1):** Xây dựng thành công pipeline thu thập dữ liệu Crossref Academic (24 bản ghi snapshot), chuẩn hóa làm sạch loại bỏ mã JATS XML, tạo trường `text_for_embedding`, lưu trữ an toàn `data/clean/papers_clean.csv`. Hệ thống thiết lập chốt kiểm dịch Great Expectations 1.x (vượt qua 6/6 Expectations) và đạt chuẩn Freshness SLA (chỉ 4.2% quá hạn $\le$ 25%). Đánh chỉ mục vào ChromaDB (`papers-baseline`) và đánh giá trên bộ 10 câu hỏi benchmark chuẩn đạt kết quả tuyệt đối: **Retrieval Hit Rate = 100%**, **Mean Token F1 = 100%**.
2. **Thử thách Tiêm Lỗi Dữ Liệu (Pha 2 - Data Corruption):** Triển khai trọn vẹn 6 kịch bản tiêm lỗi thực tế trong `src/ingestion/corruption.py`. Kết quả đã chứng minh rõ hiện tượng nguy hiểm **Silent Failure**: pipeline không báo lỗi nào nhưng hiệu năng sụt giảm rõ (**Hit Rate giảm xuống 60%**, **Token F1 giảm xuống 50%**); 5/10 câu hỏi chuyển thành câu trả lời "I don't know". Chốt kiểm dịch Great Expectations 1.x và Freshness SLA lập tức phát hiện và gióng chuông cảnh báo (`quality_gate: FAILED`, `freshness: WARNING`).
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
| Corruption/repair | Clean DataFrame, Raw snapshot | Tiêm 6 dạng lỗi dữ liệu; khôi phục idempotent từ Raw records và kiểm chứng bằng `repair_verification.json` | `corruption_log.json`, `papers_clean_corrupted.csv`, `papers_clean_repaired.csv` | Thành viên 4 (corruption), 1 (repair), 2 (cleaning dùng cho repair) |
| Orchestration     | Toàn bộ các module | Điều phối luồng Phase 1 và Phase 2 end-to-end, so sánh 3 trạng thái | `script/run_phase1.py`, `script/run_corruption_flow.py`, reports | Thành viên 1 |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình             | Giá trị sử dụng |
| ---------------------------- | ------------------- |
| `LLM_PROVIDER`             | `gemini` (mặc định); lần chạy nộp bài không có API key nên judge dùng heuristic theo token F1 ở cả 3 trạng thái (`judge_fallbacks = 10/10`) |
| `LLM_MODEL`                | `gemini-2.5-flash` (mặc định, không được gọi vì không có key) |
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
| Baseline pipeline | Thành công (Exit code 0) | 2026-09-25 16:53 (GMT+7) | `data/results/baseline_metrics.json`, `data/reports/phase1_report.md` |
| Corruption flow   | Thành công (Exit code 0) | 2026-09-25 16:53 (GMT+7) | `data/results/corrupted_metrics.json`, `repaired_metrics.json`, `corruption_report.md` |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính                | Giá trị                             |
| --------------------------- | ------------------------------------- |
| Source                      | Snapshot `data/raw/crossref_records.json` (chế độ mặc định, dùng cho lần chạy nộp bài); Crossref REST API `https://api.crossref.org/works` khi đặt `REFRESH_SOURCE=1` |
| Query/filter                | `query=agentic retrieval augmented generation large language model`, `filter=from-pub-date:<ngày chạy − 180 ngày>,has-abstract:true`, `rows=24` (chỉ dùng ở chế độ live) |
| Thời điểm lấy dữ liệu | Snapshot đi kèm starter repo; lần chạy nộp bài (2026-09-25) đọc từ snapshot |
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
| LLM provider/model                       | `gemini` / `gemini-2.5-flash` (mặc định); không có API key nên judge dùng heuristic theo token F1 cho 10/10 câu ở cả 3 trạng thái |
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
| `judge_accuracy`     |     **1.000 (100%)** | Judge heuristic (theo token F1): 10/10 câu đúng |
| `mean_judge_score`   |     **5.000 / 5.0**  | Heuristic: câu đúng hoàn toàn được 5 điểm |
| Ragas, nếu có        | Skipped | Chỉ chạy khi đặt `RUN_RAGAS=1` |

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
| 1. Drop latest records | Bỏ rơi 20% bài báo mới nhất | 4 bài | Data size sụt giảm | 3 câu (eval_004, 007, 008) mất tài liệu → retrieval trượt, trả lời "I don't know"; quality gate không bắt được vì 22 dòng vẫn trong ngưỡng 5–5000 | Nạp lại đầy đủ từ snapshot thô |
| 2. Blank summary | Xóa rỗng trường `summary` | 2 bài | Vi phạm GX min length | eval_002 vẫn truy xuất đúng bài nhưng summary rỗng → "I don't know" (F1 = 0); GX fail độ dài `summary` | Đọc lại tóm tắt nguyên bản từ raw |
| 3. Inject noise | Chèn chuỗi ký tự rác vào tóm tắt | 2 bài | Nhiễu ngữ nghĩa vector | Không chạm tới bài nào trong test set nên metric không đổi; không expectation nào bắt được nhiễu | Làm sạch lại từ bản ghi gốc |
| 4. Truncate title | Cắt ngắn tiêu đề xuống < 8 ký tự | 2 bài | Mất thông tin định danh | eval_010 không còn tra được bài theo tên đầy đủ → retrieval trượt, "I don't know" | Khôi phục tiêu đề đầy đủ |
| 5. Stale date | Lùi ngày xuất bản 365 ngày trước | 20 bài | Vi phạm Freshness SLA | Freshness: 22/22 bản ghi quá hạn → STALE; không câu hỏi `date` nào còn tài liệu nên metric không đo được tác động | Tính toán lại ngày từ timestamp raw |
| 6. Duplicate rows | Nhân bản bản ghi tạo trùng ID | 2 bài | Vi phạm GX unique ID | GX fail `paper_id` unique; collection corrupted có vector trùng nhưng metric không đổi | Khử trùng lặp qua logic `seen_ids` |

**Corruption log:**
- Đường dẫn: `data/results/corruption_log.json`
- Trạng thái: Có đầy đủ.
- Nhận xét: Log ghi nhận chi tiết 6 kịch bản, danh sách `affected_ids` cụ thể, số dòng baseline (24) và số dòng corrupted (22).

**Nguyên tắc phục hồi an toàn (Idempotent Repair):**
Quy trình repair tuyệt đối không sửa thủ công (patch tay) trên dữ liệu bẩn. Thay vào đó, pipeline đọc lại toàn bộ dữ liệu từ bản lưu trữ nguồn nguyên thủy không thể thay đổi (`data/raw/crossref_records.json`), chạy lại hàm làm sạch chuẩn và ghi đè đồng bộ lên serving layer. Kết quả được kiểm chứng bằng `data/results/repair_verification.json`: 24/24 `paper_id` và `text_for_embedding` khớp baseline, 0 trùng lặp, `is_idempotent: true`; nếu không khớp, `run_corruption_flow.py` exit khác 0.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal            | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét   |
| ------------------------ | -------: | --------: | -------: | -----------------------: | --------------: | ------------ |
| `retrieval_hit_rate`   | **1.000** | **0.600** | **1.000** | **-40 điểm %** | **100% phục hồi** | 4 câu trượt: 3 do `drop_latest_records`, 1 do `truncate_title` |
| `mean_token_f1`        | **1.000** | **0.500** | **1.000** | **-50 điểm %** | **100% phục hồi** | 5 câu F1 = 0: 4 câu trượt ở trên và eval_002 (summary rỗng); nhiễu không ảnh hưởng |
| `judge_accuracy`       | **1.000** | **0.500** | **1.000** | **-50 điểm %** | **100% phục hồi** | Judge heuristic theo token F1 nên giảm đúng như F1 |
| `mean_judge_score`     | **5.000** | **3.000** | **5.000** | **-2.000** | **100% phục hồi** | Heuristic: câu đúng 5 điểm, câu sai 1 điểm |
| Quality checks pass/fail | **True**  | **False** | **True**  | Báo động FAILED | Trở lại PASSED | GX 1.x bắt lỗi vi phạm length & unique |
| Freshness status         | **True**  | **False** | **True**  | STALE WARNING | Trở lại FRESH | Tỉ lệ mốc meo vọt lên 100% rồi về lại 4.2% |

### Hai kết luận nhân quả cốt lõi:
1. **Dữ liệu lỗi $\rightarrow$ Silent Failure $\rightarrow$ Quality Gate gióng chuông:** Khi tiêm lỗi, pipeline vẫn ingest, index và trả lời mà không có exception nào; 5/10 câu thành "I don't know", hit rate giảm 40 điểm % và token F1 giảm 50 điểm %. Sự cố được phát hiện ở tầng dữ liệu: GX fail 2/6 expectation (`paper_id` unique, độ dài `summary`) và freshness báo 100% quá hạn; dữ liệu lỗi chỉ được index vào collection cách ly `papers-corrupted` để đo thiệt hại.
2. **Idempotent Repair $\rightarrow$ Khôi phục toàn vẹn 100%:** Khi kích hoạt cơ chế tự phục hồi từ raw snapshot, dữ liệu sạch được tái lập hoàn toàn, đưa toàn bộ chỉ số Retrieval Hit Rate, Token F1, và Quality Gate trở lại 100% phong độ ban đầu (`is_idempotent: True`).

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** `data/reports/phase1_report.md` ghi "Tổng số bản ghi thu thập: 0" và "Số bản ghi sau làm sạch: 0" dù pipeline xử lý 24 bản ghi; đồng thời `corruption_report.md` in các dòng quality gate/freshness và phần nhận định dưới dạng chữ gõ cứng thay vì lấy từ kết quả.
- **Nguyên nhân:** hai module ghép với nhau không cùng contract: `phase1.py` (thành viên 1) ghi `source_summary` với key `raw_records`/`clean_rows`, còn `reporting.py` (thành viên 4) đọc `raw_count`/`clean_count` và mặc định về 0 khi không thấy key; hàm báo cáo đối chiếu nhận quality/freshness làm tham số nhưng không dùng tới.
- **Cách xử lý:** thống nhất key theo `phase1.py`; viết lại `reporting.py` để mọi số liệu và nhận định sinh từ artifact (quality, freshness, `corruption_log.json`, `corrupted_answers.json`, `repair_verification.json`), thêm `judge_fallbacks` vào metrics để báo cáo ghi rõ judge dùng LLM hay heuristic.
- **Cách xác minh:** chạy lại `python script/run_phase1.py` và `python script/run_corruption_flow.py` (exit 0); `phase1_report.md` ghi đúng 24 bản ghi raw và 24 bản ghi sạch, còn bảng quality/freshness trong `corruption_report.md` khớp với các file trong `data/quality/`.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng   | Hướng cải thiện có thể kiểm chứng |
| --------------------- | -------------- | ----------------------------------------- |
| Corpus hiện tại có quy mô 24 bài báo | Chưa bao quát toàn bộ độ trễ khi scale dữ liệu lớn | Mở rộng scale ingestion lên 500-1000 bài báo để kiểm thử tải của ChromaDB |
| Freshness SLA kiểm tra theo mốc ngày cố định | Cần cập nhật ngày hiện tại để đo độ tươi liên tục | Tích hợp cron job định kỳ chạy automated freshness monitoring hàng ngày |
| LLM Judge phụ thuộc hạn ngạch API ngoài | Có thể gặp lỗi `429 Too Many Requests` khi vượt quota | Tích hợp local LLM (Ollama) làm judge offline để độc lập hoàn toàn với cloud API |
| Lần chạy nộp bài không có API key nên judge là heuristic theo token F1 | `judge_accuracy` không độc lập với `mean_token_f1` | Chạy lại có API key; đạt khi `judge_fallbacks = 0` ở cả 3 file metrics |
| Test set lấy 10 bài đầu theo `paper_id`; cả 2 câu `date` rơi vào bài bị `drop_latest_records` xoá | Không đo được silent failure của `stale_date` (trả lời sai ngày một cách tự tin) | Thêm câu `date` cho bài còn lại sau corruption; kỳ vọng F1 của câu `date` giảm trong khi hit rate giữ nguyên |
| Quality gate không bắt được `drop_latest_records`, `truncate_title`, `inject_noise` | Ba lỗi này chỉ lộ ra qua metric | Thêm expectation độ dài `title` ≥ 8 và so số dòng với lần chạy trước; kỳ vọng bản corrupted fail thêm expectation |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [x] Phân công khớp với module, artifact và kết quả thực tế.
- [x] Lệnh tái hiện đã được chạy lại thành công trên phiên bản nộp bài.
- [x] Baseline, corrupted và repaired dùng chung bộ evaluation test set chuẩn.
- [x] Bảng metrics khớp 100% với các file trong `data/results/`.
- [x] Quality/freshness conclusions khớp 100% với `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact sinh ra đầy đủ, hợp lệ.
- [ ] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng (còn thiếu báo cáo của thành viên 2 và 3).
- [x] Không có `.env`, API key, token hoặc secret trong source code hay báo cáo.
