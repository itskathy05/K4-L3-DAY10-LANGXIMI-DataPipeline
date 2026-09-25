# Báo cáo cá nhân — Lê Nguyễn Trâm Anh (Thành viên 2)

> Báo cáo ghi lại phần việc Data Foundation và kết quả kiểm chứng ngày 2026-09-25.

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Lê Nguyễn Trâm Anh |
| MSSV | 2A202602760 |
| Khóa/Lớp | K4-L3-DAY10 |
| Tên nhóm | LANGXIMI |
| Vai trò chính | Thành viên 2 — Data Foundation Owner |
| Repository | https://github.com/itskathy05/K4-L3-DAY10-LANGXIMI-DataPipeline |
| Ngày báo cáo | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

| Module/deliverable | File/hàm phụ trách | Input | Output | Trạng thái |
| --- | --- | --- | --- | --- |
| Crossref ingestion | `src/ingestion/crossref.py`: `parse_crossref_payload`, `fetch_source_records`, `load_raw_records` | Crossref API hoặc snapshot tại `data/raw/` | `list[PaperRecord]` cùng dòng thông báo nguồn và số bản ghi | Hoàn thành ở mức module; live API và fallback đã được kiểm chứng |
| Cleaning và data model | `src/ingestion/cleaning.py`: `build_clean_dataframe` | `list[PaperRecord]`, `run_date` | DataFrame có `paper_id`, `age_days`, `text_for_embedding` và metadata cho retrieval | Hoàn thành ở mức module; 24 dòng từ snapshot đã được kiểm chứng |
| Dữ liệu đầu vào cho repair | `load_raw_records` và `build_clean_dataframe` | Raw records, cùng `run_date` của baseline | DataFrame sạch có thể dựng lại | Đã bàn giao hai hàm và contract dữ liệu |

Tôi bàn giao schema sạch cho thành viên 3 xây index và hai hàm đọc/làm sạch raw cho thành viên 1 điều phối baseline, repair. Nhờ giữ cùng `paper_id` (DOI đã chuẩn hóa) và `run_date`, dữ liệu đầu vào có thể được đối chiếu giữa các lần chạy mà không phụ thuộc vào dữ liệu đã bị corruption.

## 3. Kết quả theo vai trò

| Công việc | Bằng chứng | Kết quả đã quan sát |
| --- | --- | --- |
| Phân tích Crossref và bảo vệ snapshot fallback | `src/ingestion/crossref.py`, `tests/test_data_foundation.py` | Request live thật in `Source: LIVE Crossref` và `Records: 24`; hai file snapshot không đổi hash sau request |
| Chuẩn hóa dữ liệu | `src/ingestion/cleaning.py`, `data/clean/papers_clean.csv` | Snapshot tạo 24 dòng sạch với DOI duy nhất |
| Kiểm chứng hành vi nguồn dữ liệu | `tests/test_data_foundation.py` | 5/5 test đạt: parser, cleaning, tính lặp lại từ raw, nhánh live và fallback |

Số lượng 24 là kết quả của lần kiểm chứng ngày 2026-09-25; Crossref là nguồn sống nên kết quả lần chạy khác có thể thay đổi. Trong phạm vi `fetch_source_records()`, live records được trả về cho lượt chạy và hàm không ghi đè snapshot fallback; pipeline tích hợp quản lý raw records dùng cho repair.

## 4. Giải thích kỹ thuật

### Vấn đề cần giải quyết

Crossref cung cấp metadata không đồng nhất và có thể tạm thời không truy cập được. Phần Data Foundation cần biến response hoặc snapshot thành cùng một schema, giữ bản raw làm điểm khôi phục, rồi tạo dữ liệu sạch ổn định để nhóm đánh giá tác động của corruption và repair trên cùng tập tài liệu.

### Cách triển khai

Crossref trả metadata ở nhiều cấu trúc khác nhau: tiêu đề dạng danh sách, tác giả dạng các trường tên, ngày có thể thiếu tháng/ngày và abstract có thẻ JATS/XML. Parser chuẩn hóa các trường đó thành `PaperRecord`, bỏ item thiếu DOI hoặc tiêu đề, và chuyển ngày thiếu thành ngày đầu tiên của tháng/năm tương ứng. Request dùng retry cho 429/5xx; nếu không nhận được bản ghi hợp lệ, hàm đọc snapshot và in rõ `Source: FALLBACK snapshot`.

Cleaner chuyển DOI về chữ thường, bỏ thẻ markup/khoảng trắng thừa, loại dòng thiếu DOI, tiêu đề, ngày hợp lệ hoặc tóm tắt dưới 30 ký tự. DOI trùng giữ dòng hợp lệ đầu tiên. Hàm tạo `authors_joined`, `categories_joined`, `summary_chars`, `age_days = (run_date.date() - published).days` và `text_for_embedding` gồm năm dòng `Title`, `Authors`, `Published`, `Categories`, `Summary`; kết quả sắp theo DOI.

### Input, output và contract

| Thành phần | Contract |
| --- | --- |
| Input ingestion | Crossref `message.items` hoặc JSON snapshot; `Settings` cung cấp query, filter, số bản ghi và đường dẫn |
| Output ingestion | `list[PaperRecord]`; bản ghi thiếu DOI/tiêu đề bị loại; fallback snapshot giữ nguyên |
| Input cleaning | `list[PaperRecord]` và `run_date: datetime` |
| Output cleaning | `pandas.DataFrame` có `paper_id`, `title`, `summary`, `published`, `authors_joined`, `categories_joined`, `abs_url`, `pdf_url`, `text_for_embedding` mà retrieval sử dụng |
| Repair contract | Đọc lại raw bằng `load_raw_records()` rồi gọi `build_clean_dataframe()` với cùng `run_date` của baseline để so sánh chính xác |

### Cách xác minh đã chạy

```powershell
$env:PYTHONPATH='src'; pytest tests/test_data_foundation.py -v
python -c "import sys; sys.path.insert(0, 'src'); from core.config import load_settings; from ingestion.crossref import fetch_source_records; fetch_source_records(load_settings())"
```

Kết quả lần chạy: 5/5 test đạt; request live trả 24 bản ghi; cleaning từ snapshot tạo 24 dòng sạch với DOI duy nhất. Hai file `data/clean/papers_clean.csv` và `papers_clean.json` đã được tạo trong quá trình kiểm tra tích hợp.

## 5. Quyết định kỹ thuật quan trọng

- **Bối cảnh:** Crossref live phải là nguồn được thử trước, nhưng snapshot fallback cần giữ nguyên để còn khôi phục khi mất mạng.
- **Phương án cân nhắc:** Ghi đè hai file raw bằng kết quả live; hoặc giữ snapshot bất biến và trả live records cho lượt chạy hiện tại.
- **Phương án đã chọn:** Trong module ingestion, giữ snapshot fallback và trả live records trực tiếp; dùng snapshot khi cần nguồn dự phòng.
- **Lý do:** Bảo toàn snapshot dự phòng và làm rõ nguồn dữ liệu của mỗi lượt chạy.
- **Bằng chứng:** Test live/fallback đều đạt; hash của hai snapshot không đổi sau request live thật.

## 6. Tình huống vận hành đã xử lý và kiểm chứng module

Tình huống cần xử lý là Crossref live không trả được dữ liệu sau retry. Trong test, tôi giả lập lỗi kết nối tại request; `fetch_source_records()` chuyển sang snapshot sẵn có, in `Source: FALLBACK snapshot` và trả danh sách bản ghi dùng được. Test kiểm tra snapshot vẫn nguyên vẹn. Đây là nhánh dự phòng được kiểm chứng bằng mock, không phải kết quả của một lần API live bị lỗi.

Bộ test chạy hoàn toàn offline bằng dữ liệu mẫu và request giả lập, giúp tái hiện cùng kết quả trong nhiều lần chạy. Năm bài kiểm tra xác nhận schema từ Crossref, quy tắc cleaning, khả năng dựng lại DataFrame từ raw, lựa chọn nguồn live và sử dụng snapshot fallback. Lần gọi API thực tế cũng trả về 24 bản ghi và in rõ `Source: LIVE Crossref`.

## 7. Hiểu biết về luồng end-to-end

1. Crossref/snapshot được parse thành `PaperRecord`; cleaning tạo DataFrame; quality gate cần kiểm tra trước khi tài liệu được embedding bằng MiniLM và nạp vào ChromaDB.
2. Evaluation set giữ câu hỏi, ground truth và DOI đúng. Hit rate kiểm tra DOI đó có trong tài liệu truy xuất; Token F1 và judge đo câu trả lời so với ground truth.
3. Quality checks phát hiện schema, null, trùng DOI và tóm tắt quá ngắn; freshness đo tuổi dữ liệu qua `age_days` và ngưỡng SLA.
4. Ba trạng thái phải dùng cùng test set để chênh lệch metric phản ánh thay đổi dữ liệu, thay vì do câu hỏi khác nhau.
5. Repair được xác nhận bằng dữ liệu sạch dựng lại từ đúng raw baseline, DOI và nội dung khớp, quality/freshness cùng metrics được đo lại trên cùng test set.

## 8. Kết quả Data Foundation và pipeline tích hợp của nhóm

### 8.1. Kết quả phần việc Data Foundation của tôi

| Chỉ số | Kết quả kiểm chứng |
| --- | ---: |
| Bản ghi Crossref live | 24 |
| Bản ghi trong snapshot | 24 |
| Dòng sạch | 24 |
| DOI duy nhất trong dữ liệu sạch | 24 |
| Test Data Foundation đạt | 5/5 |

### 8.2. Kết quả pipeline tích hợp của nhóm

Bảng sau là **kết quả chung của pipeline tích hợp**, được đo trên cùng bộ đánh giá. Phần Data Foundation của tôi cung cấp dữ liệu đầu vào; các bước RAG, Observability, Evaluation và điều phối pipeline do các thành viên tương ứng phụ trách.

| Metric / Signal | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| Số records | 24 | 22 | 24 |
| Retrieval Hit Rate | 1.000 | 0.600 | 1.000 |
| Mean Token F1 | 1.000 | 0.500 | 1.000 |
| Judge Accuracy | 1.000 | 0.500 | 1.000 |
| Mean Judge Score | 5.000 | 3.000 | 5.000 |
| Quality Gate | PASS | FAIL | PASS |
| Expectations đạt | 6/6 | 4/6 | 6/6 |
| Freshness | FRESH | WARNING | FRESH |
| Tỉ lệ bản ghi quá hạn | 4.2% | 100% | 4.2% |

Baseline với 24 bản ghi sạch giúp pipeline đạt Retrieval Hit Rate và Mean Token F1 đều bằng 1.000. Nhóm ghi nhận **6 kịch bản corruption**; ở trạng thái corrupted, Quality Gate chuyển sang FAIL, Freshness cảnh báo WARNING, Hit Rate giảm còn 0.600 và Token F1 còn 0.500. Sau repair từ raw data, dataset trở lại 24 bản ghi, Quality Gate và Freshness phục hồi, Hit Rate và Token F1 trở lại 1.000.

Hai chuỗi nguyên nhân và bằng chứng của **pipeline tích hợp do nhóm thực hiện** là:

1. Corruption làm tập dữ liệu còn 22 records và tất cả records này quá hạn; Quality Gate từ PASS chuyển thành FAIL (4/6 expectations đạt), Freshness từ FRESH sang WARNING. Đồng thời Retrieval Hit Rate giảm từ 1.000 xuống 0.600, Mean Token F1 từ 1.000 xuống 0.500. Theo `corruption_report.md`, các câu hỏi mất tài liệu gốc hoặc thiếu nội dung tóm tắt là những trường hợp trả lời không được; đây là tác động cụ thể của dữ liệu đầu vào lên truy xuất và trả lời.
2. Repair đọc lại raw records rồi chạy cleaning với `run_date` của baseline, đưa tập dữ liệu về 24 records. Quality Gate trở lại PASS (6/6), Freshness trở lại FRESH; Retrieval Hit Rate và Mean Token F1 đều trở lại 1.000. `repair_verification.json` ghi `is_idempotent = true`, repaired khớp baseline **24/24 `paper_id`** và **24/24 `text_for_embedding`**.

Trong sáu kịch bản corruption được nhóm ghi log, `drop_latest_records` và `blank_summary` cho thấy rõ vì sao raw preservation quan trọng: tài liệu bị mất hoặc mất tóm tắt không thể được phục hồi đáng tin cậy từ bản clean đã bị sửa. Phần việc của tôi giữ DOI/`paper_id` ổn định và cleaning có kết quả lặp lại; nhóm sử dụng đầu vào đó để phát hiện suy giảm và xác minh repair.

**Artifact đối chiếu:** `data/reports/corruption_report.md`, `data/results/repair_verification.json` và các file metric trong `data/results/`. Bảng trên dùng bộ số liệu cuối cùng đã thống nhất trong báo cáo nhóm.

## 9. Điều học được và hướng cải thiện

1. Dữ liệu raw và document ID ổn định là điều kiện để truy vết và dựng lại index.
2. Cleaning loại lỗi cấu trúc trước khi quality gate; quality/freshness vẫn cần đo và báo cáo độc lập.
3. So sánh chất lượng RAG chỉ có nghĩa khi baseline, corrupted và repaired dùng đúng cùng corpus gốc và test set.

Nếu mở rộng phần việc Data Foundation, tôi sẽ bổ sung thông tin provenance cho mỗi lần lấy dữ liệu (nguồn live/fallback, thời điểm, số bản ghi và mã băm raw) vào một manifest riêng. Có thể kiểm chứng cải thiện này bằng cách chạy lại từ manifest và so sánh `paper_id`, `text_for_embedding` với artifact baseline, đồng thời vẫn giữ snapshot fallback bất biến.

## 10. Xác nhận trước khi nộp

- [x] Tôi đã điền họ tên, MSSV và xác nhận tên nhóm.
- [x] Tôi đã đọc lại phần mô tả đóng góp, quyết định và bài học theo đúng trải nghiệm của mình.
- [x] Tôi có thể giải thích luồng end-to-end và phần việc mình phụ trách.
- [x] Báo cáo không chứa API key, token hoặc secret.

**Họ và tên xác nhận:** [Lê Nguyễn Trâm Anh]  
**Ngày xác nhận:** [25/9/2026]
