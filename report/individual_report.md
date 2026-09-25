# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | [Nguyễn Thanh Hòa]|
| MSSV               | [2A202602559]             |
| Khóa/Lớp         | K4-L3-DAY10                |
| Tên nhóm         | LANGXIMI                   |
| Vai trò chính    | Observability & Evaluation Lead (Role 4) |
| Repository         | https://github.com/itskathy05/K4-L3-DAY10-LANGXIMI-DataPipeline |
| Ngày hoàn thành | 2026-09-25                 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| **Data Quality Gate (GX 1.x)** | `src/observability/quality.py`<br>`run_data_quality_checks` | `pd.DataFrame` (sạch hoặc corrupted) | `baseline_quality_report.json`<br>`corrupted_quality_report.json` | **Hoàn thành 100%** |
| **Freshness SLA Monitoring** | `src/observability/quality.py`<br>`build_freshness_report` | `pd.DataFrame` có cột `age_days` | `freshness_report.json`<br>`freshness_report_corrupted.json` | **Hoàn thành 100%** |
| **Benchmark Test Set** | `src/evaluation/testset.py`<br>`build_test_set` | Cleaned `pd.DataFrame` (24 bài báo) | `data/eval/test_set.json` (10 câu hỏi chuẩn) | **Hoàn thành 100%** |
| **Markdown Reporting** | `src/observability/reporting.py`<br>`generate_phase1_report`<br>`generate_corruption_report` | Metrics, Quality report, Freshness report | `data/reports/phase1_report.md`<br>`data/reports/corruption_report.md` | **Hoàn thành 100%** |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Nghiệm thu dữ liệu làm sạch | Thành viên 2 (`src/ingestion/cleaning.py`) | Kiểm chứng 24 dòng sạch vượt qua 6/6 Expectations của GX 1.x |
| Thiết kế kịch bản tiêm lỗi | Thành viên 2 (`src/ingestion/corruption.py`) | Hoàn thiện 6 kịch bản tiêm lỗi thực tế gây suy giảm Hit Rate và F1 |
| Chạy tích hợp và kiểm thử pipeline | Thành viên 1 (`src/pipelines/`) | Chạy thành công end-to-end `run_phase1.py` và `run_corruption_flow.py` |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Triển khai Great Expectations 1.x | `src/observability/quality.py` | Cài đặt ephemeral context, 6 Expectations kiểm định độ trọn vẹn, duy nhất, độ dài | `python tests/check_obs.py` in ra `GX 1.x Status: True (6/6 passed)` |
| Giám sát độ tươi Freshness SLA | `src/observability/quality.py` | Tính toán tỉ lệ quá hạn `age_days > 180`, cảnh báo khi vượt 25% | `freshness_report.json`: `stale_ratio = 4.2% <= 25%` $\rightarrow$ `is_fresh = True` |
| Sinh đề thi chuẩn Benchmark | `src/evaluation/testset.py` | `data/eval/test_set.json` gồm đúng 10 câu hỏi qua 4 nghiệp vụ | `python tests/check_testset.py` in ra 10 câu hỏi kèm Ground Truth và DOI |
| Thử nghiệm chốt kiểm dịch khi bị tiêm lỗi | `tests/check_corruption_gate.py` | Bắt lỗi thành công dữ liệu bẩn (`GX Status: False`, `Freshness: Warning`) | Chạy script thử nghiệm tiêm lỗi, phát hiện 2 vi phạm expectation |
| Xuất báo cáo đối chiếu 3 trạng thái | `src/observability/reporting.py` | `data/reports/corruption_report.md` hiển thị bảng so sánh rõ nét | Chạy `run_corruption_flow.py` xuất bảng Markdown 3 trạng thái |

**Output cụ thể chứng minh phần việc:**
Bảng đối chiếu 3 trạng thái tại [`data/reports/corruption_report.md`](file:///D:/Sourcecode/vinai/lab/Lab10/K4-L3A-Day10-Data-Pipeline-Data-Observability-LANGXIMI/data/reports/corruption_report.md):
- **Baseline:** Hit rate = 100%, F1 = 100%, GX Status = PASSED, Freshness = FRESH.
- **Corrupted:** Hit rate = 60%, F1 = 50%, GX Status = **FAILED**, Freshness = **WARNING**.
- **Repaired:** Hit rate = 100%, F1 = 100%, GX Status = **PASSED**, Freshness = **FRESH**.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
Trong các hệ thống RAG thực tế, lỗi dữ liệu (dữ liệu thiếu, rỗng, sai format, mốc meo) thường không làm sập chương trình mà gây ra **Silent Failure**: Model vẫn tự tin trả lời nhưng là trả lời sai sự thật (Hallucination). Phần việc của Role 4 là xây dựng "Trạm kiểm dịch dữ liệu" (Data Observability Gate) để phát hiện và ngăn chặn dữ liệu xấu trước khi được nhúng vector vào ChromaDB, đồng thời cung cấp thước đo định lượng (Benchmark) để chứng minh tính hiệu quả của pipeline.

### Cách triển khai
1. **Great Expectations 1.x:** Khởi tạo Ephemeral context trên bộ nhớ RAM (`gx.get_context(mode="ephemeral")`), gắn DataFrame asset và batch definition. Tạo ExpectationSuite gồm 6 quy tắc kiểm tra nghiêm ngặt:
   - Số dòng từ 5 đến 5000.
   - Không được null ở các trường sống còn: `paper_id`, `title`, `text_for_embedding`.
   - Trường định danh `paper_id` phải duy nhất 100%.
   - Trường `summary` phải có độ dài tối thiểu 30 ký tự để đảm bảo đủ ngữ cảnh học thuật.
2. **Freshness SLA:** Lọc các bản ghi có `age_days > 180` ngày. Nếu tỉ lệ bài báo cũ vượt quá ngưỡng 25%, hệ thống lập tức gắn cờ cảnh báo `is_fresh = False`.
3. **Benchmark Test Set:** Lấy 10 bài báo đại diện và trích xuất câu hỏi - đáp án chuẩn (Ground Truth) theo 4 dạng nghiệp vụ: 3 câu `summary`, 3 câu `authors`, 2 câu `date`, 2 câu `categories`.

### Input, output và contract

| Thành phần | Mô tả |
| ------------------------------ | ------------------------------------------- |
| Input | `pd.DataFrame` chứa các cột chuẩn: `paper_id`, `title`, `summary`, `authors_joined`, `categories_joined`, `published`, `age_days`, `text_for_embedding` |
| Output | Dict kết quả `{"success": bool, "successful_expectations": int, ...}` và file JSON artifact tại `data/quality/` |
| Module phụ thuộc | Nhận clean dataframe từ `src/ingestion/cleaning.py` |
| Module sử dụng output | `src/pipelines/phase1.py` và `src/pipelines/corruption_flow.py` quyết định dừng/cảnh báo dữ liệu; `src/retrieval/index.py` nhận test set để đánh giá |
| Điều kiện lỗi cần xử lý | Xử lý an toàn khi DataFrame rỗng (trả về `is_fresh = False`), fallback heuristic judge khi LLM ngoài bị quá tải quota |

### Cách xác minh

```bash
# Kiểm tra Quality Gate & Freshness
python tests/check_obs.py

# Kiểm tra Benchmark Test Set
python tests/check_testset.py

# Kiểm tra năng lực bắt lỗi khi dữ liệu bị tiêm lỗi
python tests/check_corruption_gate.py
```

- **Kết quả mong đợi:** Dữ liệu sạch đạt 6/6 checks và FRESH; Dữ liệu bẩn bị đánh trượt (FAILED) và STALE WARNING; Sinh đủ 10 câu hỏi test.
- **Kết quả thực tế:** 100% khớp kỳ vọng, console in `GX 1.x Status: True (6/6 passed)` trên baseline và `FAILED (4/6 passed)` trên corrupted data.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Lựa chọn phương thức quản lý context trong Great Expectations 1.x (File-based Context truyền thống hay Ephemeral Context trên RAM).
- **Các phương án đã cân nhắc:**
  1. *Phương án A (File-based):* Tạo thư mục `gx/` trên ổ đĩa với các file cấu hình YAML/JSON phức tạp.
  2. *Phương án B (Ephemeral):* Sử dụng `gx.get_context(mode="ephemeral")` chạy trực tiếp trong RAM.
- **Phương án đã chọn:** Chọn **Phương án B (Ephemeral Context)** theo chuẩn mới nhất của GX 1.x.
- **Lý do:** 
  - Tốc độ thực thi cực nhanh (>1100 metrics/giây).
  - Không sinh rác cấu hình trong Git repo, tránh xung đột file cấu hình giữa các môi trường máy tính khác nhau.
  - Phù hợp hoàn hảo với kiến trúc pipeline CI/CD hiện đại.
- **Bằng chứng quyết định phù hợp:** Quality Gate chạy trơn tru trong chưa đầy 0.1 giây trong cả Phase 1 và Phase 2 mà không gặp bất kỳ lỗi I/O nào.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:**
  ```text
  ModuleNotFoundError: No module named 'core'
  ```
- **Lệnh hoặc bước tái hiện:** Chạy file kiểm thử `python check_obs.py` từ thư mục con `tests/`.
- **Nguyên nhân gốc:** Khi chạy script từ thư mục con, Python tự động gán `sys.path[0]` là thư mục con (`tests/`), do đó Python không tìm thấy package `core` và `observability` nằm trong thư mục `src/`.
- **Cách xử lý:** Bổ sung cấu hình `sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))` ở đầu các script trong `tests/` để đảm bảo Python luôn nhận diện được thư mục mã nguồn `src/` dù chạy từ bất kỳ thư mục làm việc nào.
- **Cách xác minh sau khi sửa:** Chạy lại `python check_obs.py`, script thực thi thành công 100% và in ra kết quả kiểm định.
- **Điều học được:** Luôn chủ động quản lý đường dẫn module tương đối trong các script kiểm thử độc lập để tránh phụ thuộc vào biến môi trường cục bộ của từng máy.

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?**
   Dữ liệu được kéo từ Crossref REST API (hoặc snapshot fallback) $\rightarrow$ lưu trữ bất biến tại `data/raw/` (Data Lineage) $\rightarrow$ làm sạch HTML tags, tính `age_days`, ghép `text_for_embedding` $\rightarrow$ qua chốt kiểm dịch Great Expectations 1.x và Freshness SLA $\rightarrow$ chuyển thành vector embedding 384 chiều qua mô hình `all-MiniLM-L6-v2` $\rightarrow$ nạp vào collection tương ứng trong ChromaDB.
2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**
   Bộ test gồm 10 câu hỏi chuẩn có sẵn đáp án `ground_truth` và mã tài liệu chuẩn `ground_truth_doc_ids`. Khi Agent truy xuất context:
   - Nếu tài liệu chuẩn nằm trong Top 4 tài liệu được truy xuất $\rightarrow$ tính là Retrieval Hit (`Hit Rate = 1`).
   - Câu trả lời của Agent được so khớp từ vựng với `ground_truth` để tính điểm chồng lấn `Token F1`.
3. **Quality checks khác freshness monitoring ở điểm nào trong bài lab?**
   - *Quality checks (GX 1.x):* Giám sát tính toàn vẹn, đúng đắn về mặt cấu trúc và schema của dữ liệu (không null, duy nhất, độ dài tối thiểu, số dòng).
   - *Freshness monitoring:* Giám sát tính kịp thời và độ tươi mới theo thời gian (Time Dimension) của dữ liệu, ngăn ngừa tình trạng dữ liệu quá hạn gây kiến thức lỗi thời cho AI.
4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**
   Để phép đo mang tính khoa học và kiểm soát biến số (Controlled Experiment). Giữ nguyên test set đảm bảo sự thay đổi chỉ số hoàn toàn phản ánh tác động của chất lượng dữ liệu, chứ không phải do câu hỏi dễ hơn hay khó hơn.
5. **Repair được xem là thành công dựa trên artifact và metric nào?**
   Dựa trên:
   - `repair_verification.json` xác nhận `is_idempotent: True` (số dòng, mã ID, nội dung khớp 100% với baseline ban đầu).
   - `repaired_metrics.json` cho thấy Retrieval Hit Rate và Token F1 phục hồi hoàn toàn về mức 1.000 (100%).
   - Quality Gate báo `PASSED` và Freshness báo `FRESH`.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` | **1.000** | **0.600** | **1.000** | Giảm 40% do 20% bài báo mới bị bỏ rơi và tiêu đề bị cắt ngắn |
| `mean_token_f1`      | **1.000** | **0.500** | **1.000** | Giảm 50% do summary bị xóa trắng và chèn ký tự rác |
| `judge_accuracy`     | **1.000** | **0.500** | **1.000** | Điểm chính xác giảm tương ứng với sự suy giảm của context |
| `mean_judge_score`   | **5.000** | **3.000** | **5.000** | Chất lượng câu trả lời bị tụt từ mức Xuất sắc xuống Trung bình |
| Quality checks         | **True**  | **False** | **True**  | Bắt lỗi thành công vi phạm summary length và duplicate ID |
| Freshness status       | **True**  | **False** | **True**  | Phát hiện chính xác dữ liệu bị lùi ngày thành mốc meo |

### Kết luận từ số liệu

1. **Chuỗi 1 (Corruption & Silent Failure):** Tiêm lỗi xóa summary và duplicate row $\rightarrow$ Quality Gate GX 1.x chuyển trạng thái sang `False` (4/6 expectations passed) $\rightarrow$ Retrieval Hit Rate sụt từ 1.000 xuống 0.600 và Token F1 sụt từ 1.000 xuống 0.500.
2. **Chuỗi 2 (Idempotent Repair):** Phục hồi từ `crossref_records.json` $\rightarrow$ Quality Gate và Freshness SLA trở lại trạng thái `True` $\rightarrow$ Retrieval Hit Rate và Token F1 phục hồi 100% về mức 1.000 ban đầu.

**Phân tích ảnh hưởng:**
Lỗi bỏ rơi bản ghi mới (`drop_latest_records`) và xóa tóm tắt (`blank_summary`) có sức tàn phá lớn nhất đối với hệ thống RAG, vì chúng trực tiếp tước bỏ context mà mô hình cần để suy luận.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất
1. **Tầm quan trọng của Data Observability:** Không có chốt kiểm dịch dữ liệu, hệ thống AI sẽ âm thầm trả lời sai (Silent Failure) mà không bao giờ báo lỗi đỏ.
2. **Sức mạnh của Great Expectations 1.x:** Cú pháp Ephemeral Context mới của GX 1.x giúp việc kiểm định dữ liệu tự động diễn ra cực kỳ nhanh gọn và chuẩn xác trong quy trình MLOps.
3. **Nguyên tắc bảo toàn Data Lineage:** Luôn lưu trữ bản sao dữ liệu thô nguyên thủy (Raw Preservation) để đảm bảo khả năng tự phục hồi bất biến (Idempotent Repair) khi có sự cố.

### Nếu có thêm thời gian
Xây dựng một Web Dashboard trực quan hóa theo thời gian thực (Interactive Observability Dashboard) bằng Streamlit để hiển thị phân bố độ tuổi bài báo, biểu đồ radar so sánh 3 trạng thái và cảnh báo chất lượng dữ liệu ngay khi phát hiện vi phạm SLA.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** [Họ và tên của bạn]  
**Ngày xác nhận:** 2026-09-25
