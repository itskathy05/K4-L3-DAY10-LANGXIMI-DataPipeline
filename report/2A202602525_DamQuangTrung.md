# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Đàm Quang Trung            |
| MSSV               | 2A202602525                |
| Khóa/Lớp         | K4                         |
| Tên nhóm         | LANGXIMI                   |
| Vai trò chính    | Pipeline Lead & Integrator (Thành viên 1) |
| Repository         | https://github.com/itskathy05/K4-L3-DAY10-LANGXIMI-DataPipeline |
| Ngày hoàn thành | 2026-09-25                 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Baseline orchestration (CP3) | `src/pipelines/phase1.py`: `run_baseline`, `resolve_source_records`, `validate_clean_schema`, `run_quality_gate`, `ensure_test_set`, `run_agent_demo`, `main` | Raw snapshot `data/raw/crossref_records.json` (hoặc Crossref live khi `REFRESH_SOURCE=1`) và các module ingestion/observability/retrieval/evaluation | `data/clean/papers_clean.csv/.json`, collection `papers-baseline`, `data/eval/test_set.json`, `baseline_metrics.json`, `phase1_report.md` | Hoàn thành (cả chế độ snapshot và live — xem mục 6) |
| Corruption → repair orchestration (CP4–CP5) | `src/pipelines/corruption_flow.py`: `ensure_baseline`, `evaluate_stage`, `repair_from_raw`, `verify_repair`, `format_comparison_table`, `main` | Clean dataset, raw snapshot, cùng test set của baseline | `papers_clean_corrupted/_repaired.*`, collection `papers-corrupted`/`papers-repaired`, `corrupted_metrics.json`, `repaired_metrics.json`, `repair_verification.json`, `corruption_report.md`, bảng 3 trạng thái trên console | Hoàn thành |
| Tiện ích dùng chung trong `core/` | `src/core/utils.py`: `dataframe_records` (export qua `src/core/__init__.py`) | `pd.DataFrame` | Danh sách record JSON-safe để ghi artifact | Hoàn thành |

Tôi không nhận ownership cho `core/config.py` (có sẵn trong starter), `corruption.py`, `quality.py`, `testset.py` (thành viên 4), `crossref.py`/`cleaning.py` (thành viên 2) và `retrieval/` (thành viên 3). `reporting.py` do thành viên 4 viết bản đầu; tôi sửa lại ở bước hoàn thiện cuối (bảng dưới). Các commit của tôi trên `main` đều đi qua nhánh `trungdam`.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Dựng môi trường CP0 (`.venv`, `pip install -e .`, `.env` từ `.env.example`, không commit secret) | Cả nhóm | Smoke test `import chromadb, great_expectations, sentence_transformers` chạy được |
| Kiểm tra tích hợp với code của thành viên 2 trước khi merge | `crossref.py`, `cleaning.py` | 5/5 test trong `tests/test_data_foundation.py` vẫn pass khi ghép với thay đổi của tôi |
| Kiểm tra tương thích khi thành viên 3 viết lại `retrieval/` | `index.py`, `qa.py`, `agent.py` | Xác nhận API `LocalEmbeddingIndex.build(df, settings, path)`, `answer_question`, `build_agent` không đổi; chạy lại cả 2 flow trước khi merge (khi đó quality/testset/reporting/corruption còn TODO nên dùng bản giả đúng contract) |
| Chạy lại độc lập artifact của nhóm | Toàn pipeline sau commit `b435257` của thành viên 4 | Tái hiện đúng các chỉ số đã nộp và phát hiện lỗi hiển thị số bản ghi trong `phase1_report.md` |
| Hoàn thiện cuối repo (người sửa cuối cùng) | `reporting.py`, `metrics.py`, `data/`, `docs/TEAM.md`, `report/` | `reporting.py` sinh báo cáo hoàn toàn từ số liệu (bỏ các dòng PASSED/FAILED và nhận định gõ cứng, sửa lệch key làm báo cáo ghi 0 bản ghi); `metrics.py` ghi `judge_fallbacks`; chạy lại toàn bộ artifact với judge nhất quán; dọn file tạm trong `data/quality/` và segment ChromaDB không còn dùng; chuẩn hoá tên báo cáo, điền TEAM.md, sửa các chỗ báo cáo nhóm không khớp artifact |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Nối luồng baseline: ingest → clean → kiểm schema → quality gate → index → test set → evaluate → report | `src/pipelines/phase1.py` | Đủ artifact CP3; baseline hit rate 1.0, token F1 1.0 | `python script/run_phase1.py` (exit 0) |
| Nối luồng corruption → đo suy giảm → repair → so sánh 3 trạng thái | `src/pipelines/corruption_flow.py` | Đủ artifact CP4–CP5; bảng 3 trạng thái in ra console | `python script/run_corruption_flow.py` (exit 0) |
| Kiểm chứng repair idempotent bằng dữ liệu, không chỉ bằng metric | `verify_repair` → `data/results/repair_verification.json` | 24/24 `paper_id` khớp, 24/24 `text_for_embedding` giống hệt, 0 trùng lặp, `is_idempotent: true` | Đọc file JSON sau khi chạy flow |
| Cách ly 3 không gian vector | `LocalEmbeddingIndex.build(..., embeddings_path)` với 3 manifest khác nhau | `papers-baseline` 24, `papers-corrupted` 22, `papers-repaired` 24 bản ghi | `chromadb.PersistentClient("data/chroma").get_collection(name).count()` |
| Kiểm tra hợp đồng schema giữa cleaning và index | `validate_clean_schema` | Báo lỗi rõ tên cột thiếu thay vì lỗi mơ hồ bên trong Chroma | Chạy với dataframe thiếu cột `age_days` → `ValueError` liệt kê đúng cột |

Output cụ thể do phần việc của tôi tạo ra:

```text
  Metric               | Baseline | Corrupted | Repaired
  ---------------------+----------+-----------+---------
  Retrieval hit rate   | 1.000    | 0.600     | 1.000
  Mean token F1        | 1.000    | 0.500     | 1.000
  Judge accuracy       | 1.000    | 0.500     | 1.000
  Mean judge score     | 5.000    | 3.000     | 5.000
  Quality gate success | True     | False     | True
  Freshness is_fresh   | True     | False     | True
Corruption scenarios logged: 6
Repair is idempotent: True
```

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Các module do 3 thành viên khác viết chỉ có giá trị khi được nối đúng thứ tự và đúng hợp đồng dữ liệu. Phần của tôi phải bảo đảm: (1) dữ liệu xấu bị kiểm tra trước khi vào vector store, (2) ba trạng thái baseline/corrupted/repaired được so sánh công bằng, (3) repair thật sự khôi phục từ nguồn tin cậy và chạy lại bao nhiêu lần cũng ra cùng kết quả.

### Cách triển khai

- **Thứ tự Phase 1:** `resolve_source_records` mặc định đọc snapshot `data/raw/crossref_records.json`; chỉ gọi Crossref khi `REFRESH_SOURCE=1` và rơi về snapshot nếu lỗi. Sau khi clean, `validate_clean_schema` kiểm tra đủ 10 cột mà index và evaluation cần, rồi mới lưu CSV/JSON. Quality gate (GX 1.x + freshness) chạy **trước** bước index để phát hiện dữ liệu xấu trước khi vào ChromaDB.
- **So sánh công bằng:** `ensure_test_set` chỉ tạo test set khi chưa có file hoặc khi đặt `REFRESH_TEST_SET=1`; corrupted và repaired được đánh giá bằng đúng file `data/eval/test_set.json` của baseline. Mỗi trạng thái có freshness report riêng (`freshness_report_<stage>.json`) để không ghi đè báo cáo baseline.
- **Cách ly:** mỗi trạng thái dùng một collection riêng (`papers-baseline`, `papers-corrupted`, `papers-repaired`); dữ liệu lỗi được index vào collection cách ly để đo thiệt hại mà không chạm vào collection phục vụ chính.
- **Repair:** `repair_from_raw` không vá các dòng hỏng mà dựng lại toàn bộ từ raw snapshot qua đúng hàm cleaning của baseline; `verify_repair` so tập `paper_id`, nội dung `text_for_embedding`, số dòng và trùng lặp với baseline rồi ghi `repair_verification.json`.
- **An toàn khi thiếu cấu hình:** `ensure_baseline` tự chạy Phase 1 nếu thiếu artifact baseline; demo agent tự bỏ qua khi không có API key hoặc khi agent lỗi, nên pipeline vẫn exit 0 trên máy không có `.env`.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | `data/raw/crossref_records.json` (list `PaperRecord`); `Settings` từ `core/config.py`; biến môi trường `REFRESH_SOURCE`, `REFRESH_TEST_SET`, `LLM_PROVIDER` |
| Output                         | Artifact trong `data/clean/`, `data/chroma/`, `data/embeddings/`, `data/eval/`, `data/quality/`, `data/results/`, `data/reports/`; bảng so sánh trên console |
| Module phụ thuộc             | `ingestion/crossref.py`, `ingestion/cleaning.py`, `ingestion/corruption.py`, `observability/quality.py`, `observability/reporting.py`, `evaluation/testset.py`, `evaluation/metrics.py`, `retrieval/index.py`, `retrieval/agent.py` |
| Module sử dụng output        | `script/run_phase1.py`, `script/run_corruption_flow.py`; báo cáo nhóm và báo cáo cá nhân đọc lại artifact |
| Điều kiện lỗi cần xử lý | Thiếu cột hoặc dataframe rỗng (dừng với thông báo rõ); API lỗi/429 (rơi về snapshot); chưa có baseline khi chạy Phase 2 (tự chạy Phase 1); thiếu API key (bỏ qua demo, judge dùng heuristic); repair không khớp baseline (`is_idempotent: false`) |

### Cách xác minh

Lần chạy sinh artifact nộp bài (2026-09-25, 16:53 GMT+7), không cấu hình API key để mọi trạng thái dùng cùng một cách chấm và giám khảo chạy lại trên máy không có key sẽ ra đúng số liệu này:

```bash
python script/run_phase1.py
python script/run_corruption_flow.py
python -m pytest -q tests
```

- **Kết quả mong đợi:** cả hai lệnh exit 0; corrupted thấp hơn baseline; repaired bằng baseline; `is_idempotent: true`; test hiện có vẫn pass.
- **Kết quả thực tế:** hai lệnh đều exit 0; hit rate 1.0 / 0.6 / 1.0; token F1 1.0 / 0.5 / 1.0; judge heuristic ở 10/10 câu cho cả 3 trạng thái (`judge_fallbacks`); collection 24 / 22 / 24 bản ghi; `repair_verification.json` báo 24/24 khớp; 5/5 test pass. Trước đó, lần chạy đầu của nhóm cho ra `phase1_report.md` ghi "Tổng số bản ghi thu thập: 0" vì `phase1.py` ghi key `raw_records`/`clean_rows` còn `reporting.py` đọc `raw_count`/`clean_count`; sau khi thống nhất key, báo cáo ghi đúng 24 bản ghi raw và 24 bản ghi sạch.
- **Artifact/log:** `data/results/baseline_metrics.json`, `corrupted_metrics.json`, `repaired_metrics.json`, `repair_verification.json`, `corruption_log.json`; `data/reports/phase1_report.md`, `corruption_report.md`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Sau khi tiêm lỗi, pipeline cần một cách đưa dữ liệu về trạng thái đúng mà chạy lại nhiều lần vẫn ra cùng kết quả.
- **Các phương án đã cân nhắc:** (1) vá trực tiếp từng dòng bị lỗi trong dataset corrupted; (2) chép lại bản `papers_clean.csv` cũ; (3) dựng lại toàn bộ từ raw snapshot qua đúng hàm cleaning của baseline, rồi kiểm chứng bằng dữ liệu.
- **Phương án đã chọn:** (3), kèm `verify_repair` và collection riêng `papers-repaired`.
- **Lý do:** dữ liệu đã hỏng không còn cho biết giá trị đúng (ngày gốc bị ghi đè, bản ghi bị xoá thì không còn); `papers_clean.csv` là artifact trung gian nên có thể chính nó bị hỏng. Raw snapshot là nguồn gốc (lineage) và cleaning là hàm tất định (khử trùng lặp và sắp xếp theo `paper_id`), còn mỗi lần build đều xoá và tạo lại collection, nên chạy lại không sinh vector trùng. Collection riêng giữ nguyên baseline để so sánh và rollback.
- **Bằng chứng quyết định phù hợp:** `repair_verification.json` báo `is_idempotent: true` (24/24 `paper_id` và `text_for_embedding` khớp, 0 trùng lặp); `repaired_metrics.json` bằng đúng `baseline_metrics.json`; repaired qua lại quality gate và freshness (`stale_ratio` 4.2%).

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Khi bật chế độ live, flow vẫn exit 0 nhưng in `idempotent repair verified: False` và `repaired metrics: hit_rate=0.000 token_f1=0.005`. Ở một lần chạy khác, khi test set cũ còn trên đĩa, `baseline metrics: hit_rate=0.000` vì 0/10 tài liệu ground-truth có trong corpus mới.
- **Lệnh hoặc bước tái hiện:** `REFRESH_SOURCE=1 python script/run_phase1.py` rồi `python script/run_corruption_flow.py` (chạy trên bản sao, không có API key).
- **Nguyên nhân gốc:** hai phần ghép lại: (1) từ commit `63adacf`, `fetch_source_records` không còn lưu dữ liệu live vào `data/raw/`, và `phase1.py` cũng không lưu, nên `repair_from_raw` dựng lại từ snapshot cũ — một corpus khác hẳn baseline; (2) `ensure_test_set` dùng lại test set đã có mà không kiểm tra `ground_truth_doc_ids` còn nằm trong corpus hay không.
- **Cách xử lý:** sửa trong phạm vi file của tôi, không đổi hành vi của `fetch_source_records` (thành viên 2 cố ý giữ nguyên snapshot khi gọi hàm này): (1) `resolve_source_records` lưu đúng bộ records live đã dùng cho baseline vào `data/raw/crossref_records.json`, và chỉ gắn nhãn `live-api` khi records thật sự khác snapshot; (2) `ensure_test_set` tạo lại test set khi có `ground_truth_doc_ids` không còn trong corpus; (3) `run_corruption_flow.py` exit khác 0 khi `is_idempotent: false`, để lỗi không còn im lặng. Cùng lúc, `run_baseline` dừng trước bước index nếu quality gate baseline fail.
- **Cách xác minh sau khi sửa:** chạy hai flow trên bản sao, giả lập Crossref trả về 24 bài khác snapshot: dữ liệu live được lưu vào `data/raw/`, test set được tạo lại cho corpus mới, baseline hit rate 1.0 và `repair_verification.json` báo `is_idempotent: true`. Giả lập repair lệch (bỏ bớt 4 bản ghi raw) thì `run_corruption_flow.py` thoát với mã lỗi; giả lập quality gate fail thì Phase 1 dừng trước khi index. Lần chạy chế độ snapshot vẫn cho đúng các chỉ số ở mục 4.
- **Điều học được:** một bước repair chỉ an toàn khi lineage được giữ trọn: dữ liệu nào đã sinh ra baseline thì chính dữ liệu đó phải được lưu lại để repair dựng lại. Một pipeline báo "chạy thành công" (exit 0) chưa chắc đã đúng — cần một bước kiểm chứng bằng dữ liệu như `verify_repair`, và khi kiểm chứng thất bại thì phải dừng với mã lỗi.

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?** Mặc định pipeline đọc `data/raw/crossref_records.json`; khi `REFRESH_SOURCE=1` thì gọi Crossref (có retry và backoff cho 429/5xx) và rơi về snapshot nếu lỗi. `build_clean_dataframe` bỏ tag JATS/HTML, khử trùng lặp theo `paper_id`, loại bản ghi có summary dưới 30 ký tự, tính `age_days` và ghép `text_for_embedding` 5 phần (Title/Authors/Published/Categories/Summary). Sau khi qua kiểm tra schema và quality gate, `all-MiniLM-L6-v2` biến `text_for_embedding` thành vector 384 chiều đã chuẩn hoá, lưu vào ChromaDB (HNSW, khoảng cách cosine) kèm metadata để trích câu trả lời.
2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?** Test set có 10 câu (3 summary, 3 authors, 2 date, 2 categories), mỗi câu có `ground_truth` và `ground_truth_doc_ids` (DOI). Retrieval "trúng" khi một trong top-4 tài liệu trả về nằm trong `ground_truth_doc_ids`. Chất lượng câu trả lời đo bằng token F1 so với `ground_truth` và bằng LLM judge (thang 1–5); khi không gọi được LLM, judge rơi về heuristic dựa trên F1.
3. **Quality checks khác freshness monitoring ở điểm nào?** Quality (GX 1.x, 6 expectation: số dòng, không null ở `paper_id`/`title`/`text_for_embedding`, `paper_id` duy nhất, độ dài `summary`) kiểm tra dữ liệu có đúng hình dạng không, không phụ thuộc thời điểm chạy. Freshness kiểm tra dữ liệu còn mới không: `is_fresh = False` khi hơn 25% bản ghi có `age_days > 180`. Trong bài, bản corrupted fail 2 expectation (unique `paper_id`, độ dài `summary`) và freshness báo `stale_ratio` 100%; một dataset có thể hợp lệ hoàn toàn về quality mà vẫn cũ.
4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?** Để chênh lệch chỉ số chỉ đến từ dữ liệu, không đến từ câu hỏi. Tôi đã kiểm tra 3 file `*_answers.json` có đúng cùng 10 câu hỏi theo cùng thứ tự.
5. **Repair được xem là thành công dựa trên artifact và metric nào?** `repair_verification.json` (`is_idempotent: true`, 24/24 `paper_id` và `text_for_embedding` khớp, 0 trùng lặp), `repaired_metrics.json` bằng `baseline_metrics.json`, `repaired_quality_report.json` PASSED, `freshness_report_repaired.json` FRESH, và collection `papers-repaired` có 24 bản ghi như baseline.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |      1.0 |       0.6 |      1.0 | 4 câu trượt: 3 câu hỏi về bài bị `drop_latest_records` xoá (eval_004, 007, 008) và 1 câu về bài bị cắt tiêu đề (eval_010) |
| `mean_token_f1`      |      1.0 |       0.5 |      1.0 | Thêm eval_002: vẫn trúng tài liệu nhưng summary đã bị xoá trắng nên câu trả lời rỗng |
| `judge_accuracy`     |      1.0 |       0.5 |      1.0 | Cả 3 trạng thái cùng chấm bằng heuristic theo token F1 (`judge_fallbacks` = 10/10), nên so sánh được nhưng giảm đúng như F1 |
| `mean_judge_score`   |      5.0 |       3.0 |      5.0 | Heuristic: câu đúng hoàn toàn được 5 điểm, câu sai 1 điểm |
| Quality checks         |   6/6 PASS |   4/6 (FAIL) |   6/6 PASS | Fail `expect_column_values_to_be_unique(paper_id)` do dòng trùng và `expect_column_value_lengths_to_be_between(summary)` do summary bị xoá |
| Freshness status       | FRESH (4.2% stale) | WARNING (100% stale) | FRESH (4.2% stale) | `stale_date` lùi ngày 20 bản ghi; cộng 2 dòng trùng, cả 22/22 dòng đều quá 180 ngày |

### Kết luận từ số liệu

1. `drop_latest_records` xoá 4 bài và `truncate_title` cắt tiêu đề 2 bài → quality gate chưa thấy lỗi ở 2 kịch bản này (số dòng 22 vẫn trong ngưỡng), nhưng `blank_summary` và `duplicate_rows` làm fail 2 expectation, còn `stale_date` làm freshness báo 100% stale → hit rate giảm từ 1.0 xuống 0.6 và token F1 từ 1.0 xuống 0.5.
2. Repair dựng lại từ `data/raw/crossref_records.json` → quality về 6/6, freshness về 4.2% stale → hit rate và token F1 về đúng 1.0, `is_idempotent: true`.

Corruption nào ảnh hưởng rõ nhất và vì sao?

`drop_latest_records`: nó gây 3 trên 5 câu hỏi sai (eval_004, eval_007, eval_008). Câu hỏi nhắc đúng tên bài, bài không còn trong corpus nên hệ thống trả lời "I don't know from the indexed corpus." và retrieval trượt. Đây cũng là lỗi quality gate không bắt được, vì 22 dòng vẫn nằm trong ngưỡng số dòng cho phép.

Kết quả nào khác với kỳ vọng ban đầu?

- `stale_date` làm cũ 20/22 dòng nhưng **không làm giảm chỉ số nào**: cả 2 câu hỏi về ngày đều nhắm vào bài đã bị `drop_latest_records` xoá. Lỗi này chỉ bị freshness phát hiện; test set hiện tại không đo được trường hợp "tự tin trả lời sai ngày" — đúng dạng silent failure mà bài lab muốn chứng minh.
- Cả 5 câu sai đều là "I don't know" chứ không phải câu trả lời bịa: `qa.py` từ chối trả lời khi không tìm thấy bài được nhắc tên. Sự suy giảm vì vậy hiện ra khá rõ; `inject_noise` và `duplicate_rows` không ảnh hưởng chỉ số vì các bài bị nhiễu không có trong test set, còn dòng trùng không làm lệch kết quả khi hệ thống tra đúng tên bài.
- Ở lần chạy đầu của nhóm, judge rơi về heuristic không đều giữa các trạng thái (4/10 câu baseline so với 10/10 câu corrupted và repaired), nhiều khả năng do giới hạn request của model miễn phí; tôi phát hiện bằng cách đếm chuỗi `"Fallback heuristic judge"` trong 3 file `*_answers.json`. Vì vậy tôi thêm `judge_fallbacks` vào metrics và chạy lại toàn bộ không có API key để cả 3 trạng thái dùng cùng một cách chấm; hit rate và token F1 không đổi so với lần chạy đầu.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Về data pipeline: tách collection và dùng chung một test set là điều kiện để phép so sánh 3 trạng thái có ý nghĩa; repair phải dựng lại từ đúng nguồn đã sinh ra baseline thì mới idempotent.
2. Về data quality/observability: quality gate và freshness bắt được những lỗi khác nhau, và cả hai vẫn bỏ sót (mất bản ghi, cắt tiêu đề) — nên vẫn phải đo thêm chỉ số RAG; exit 0 không có nghĩa là kết quả đúng.
3. Về ảnh hưởng của data đến RAG agent: cùng một lỗi dữ liệu có thể lộ ra thành "I don't know" hoặc thành câu trả lời sai mà tự tin; test set cần có câu hỏi chạm đúng vào dữ liệu bị lỗi thì mới đo được silent failure.

### Nếu có thêm thời gian

Tôi sẽ mở rộng quality gate để bắt những lỗi hiện chỉ lộ ra qua metric: thêm expectation độ dài `title` tối thiểu 8 ký tự (bắt `truncate_title`) và so số dòng với lần chạy baseline trước đó (bắt `drop_latest_records`). Lý do: hai kịch bản này gây 4/5 câu sai nhưng gate hiện tại không phát hiện. Cách đo: chạy lại `run_corruption_flow.py`; thành công khi `corrupted_quality_report.json` fail thêm 2 expectation tương ứng, trong khi baseline và repaired vẫn đạt toàn bộ expectation.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [ ] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Đàm Quang Trung
**Ngày xác nhận:** 2026-09-25
