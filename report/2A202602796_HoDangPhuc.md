# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Hồ Đăng Phúc              |
| MSSV               | 2A202602796                 |
| Khóa/Lớp         | K4-L3-DAY10               |
| Tên nhóm         | LANGXIMI                   |
| Vai trò chính    | RAG & Agent Specialist (Thành viên 3) |
| Repository         | https://github.com/itskathy05/K4-L3-DAY10-LANGXIMI-DataPipeline |
| Ngày hoàn thành | 2026-09-25                  |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Embedding MiniLM   | `src/retrieval/embeddings.py` (`MiniLMEmbeddings`) | `text_for_embedding`, `all-MiniLM-L6-v2` | Vector 384-dim đã chuẩn hoá (L2) | Hoàn thành |
| Vector index ChromaDB | `src/retrieval/index.py` (`LocalEmbeddingIndex`) | Dataframe sạch từ `cleaning.py` | 3 collection Chroma tách biệt (`papers-baseline`, `papers-corrupted`, `papers-repaired`) + manifest `papers_embeddings*.json` | Hoàn thành |
| Logic truy vấn (dense + hybrid) | `LocalEmbeddingIndex.search()` | Câu hỏi tự nhiên | `SearchResult` (paper_id, title, score, content) | Hoàn thành |
| QA deterministic | `src/retrieval/qa.py` (`answer_question`) | Câu hỏi + index | `AnswerResult` dùng cho benchmark | Hoàn thành |
| QA Agent generative | `src/retrieval/agent.py` (`build_agent`, `run_agent_question`) | Câu hỏi + LLM provider | Câu trả lời có trích dẫn `paper_id`/title, hoặc agent mock tất định | Hoàn thành |
| Benchmark retrieval | `script/benchmark_retrieval.py`, `src/retrieval/README.md`, `tests/test_retrieval.py` | 3 manifest embedding | Hit@4, Top-1, MRR@4, latency theo từng trạng thái | Hoàn thành (bổ sung ngoài phân công gốc, ở nhánh `solo_leveling`) |

Tôi trực tiếp thực hiện toàn bộ 4 file trong `src/retrieval/` (commit `12ef630` trên nhánh nhóm), là tầng nằm giữa dữ liệu đã làm sạch của Thành viên 2 và bộ đánh giá/QA của Thành viên 4 — hai bên phụ thuộc vào contract `LocalEmbeddingIndex.search()`/`answer_question()` mà tôi định nghĩa.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Viết thêm `script/benchmark_retrieval.py`, `tests/test_retrieval.py`, `src/retrieval/README.md` trên nhánh `solo_leveling` | Toàn nhóm — bổ sung công cụ đo Hit@4/MRR@4/latency cho cả 3 collection, làm rõ contract retrieval cho người đọc sau | Có script benchmark độc lập với pipeline chính, test cách ly bằng fake `SentenceTransformer` nên không phụ thuộc mạng/GPU |

Nhánh `solo_leveling` (chưa merge vào `main`) chứa một bản pipeline đầy đủ end-to-end mà tôi thử nghiệm song song (ingestion → cleaning → quality gate → retrieval → corruption/repair), dùng để đối chiếu kết quả module `retrieval/` của mình trong một luồng độc lập trước khi khớp lại với artifact chính thức của nhóm trên `main`.

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Build & load index Chroma idempotent theo 3 collection | `LocalEmbeddingIndex.build()` / `.load()` | `data/embeddings/papers_embeddings*.json`, `data/chroma/` | `python script/run_phase1.py`, kiểm tra `collection.count()` khớp số dòng manifest |
| Dense + hybrid (RRF) search | `LocalEmbeddingIndex.search()`, `_dense_search`, `_lexical_search` | Kết quả xếp hạng theo cosine hoặc RRF, điểm chuẩn hoá `[0,1]` | `python script/benchmark_retrieval.py --top-k 4` |
| QA deterministic có exact-match guard | `answer_question()` | `data/results/baseline_answers.json` (Hit Rate 100%, Token F1 100%) | `python script/run_phase1.py` → `data/results/baseline_metrics.json` |
| QA Agent generative + mock adapter | `build_agent()`, `_DeterministicMockAgent` | `data/results/agent_demo_answers.json` khi có API key; agent mock chạy offline khi `LLM_PROVIDER=mock` | `pytest tests/test_retrieval.py -q` |

Output cụ thể: bộ 3 manifest `papers_embeddings.json` / `_corrupted.json` / `_repaired.json` trong `data/embeddings/`, mỗi manifest trỏ tới một collection Chroma riêng và được `src/evaluation/metrics.py` cùng `src/observability/reporting.py` của Thành viên 4 đọc lại để tính `retrieval_hit_rate`, `mean_token_f1` cho từng trạng thái (baseline/corrupted/repaired).

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Tầng `retrieval/` phải biến dataframe đã làm sạch thành một index có thể truy vấn ngữ nghĩa, đồng thời phải **cô lập được tác động của dữ liệu lỗi**: khi Thành viên 4 tiêm lỗi vào bản sao dữ liệu, index phải build ra một collection riêng chứ không được đè lên `papers-baseline`, nếu không phép so sánh 3 trạng thái (baseline/corrupted/repaired) sẽ vô nghĩa vì baseline cũng bị hỏng theo.

### Cách triển khai

- **Đặt tên collection theo đường dẫn manifest đích** (`_derive_collection_name`): ánh xạ `embeddings_output_path` sang một trong ba tên cố định (`papers-baseline`/`papers-corrupted`/`papers-repaired`) dựa trên `settings.paths`, thay vì để caller tự chọn tên tuỳ ý — tránh việc một pipeline vô tình build đè lên collection của trạng thái khác.
- **Idempotent build**: mỗi lần `build()` sẽ `delete_collection` nếu tên đã tồn tại rồi tạo lại từ đầu, nên chạy lại `run_phase1.py`/`run_corruption_flow.py` nhiều lần không làm phình collection hay để lại vector rác.
- **Kiểm tra tính toàn vẹn khi load**: `load()` so khớp `collection.count()` với số document trong manifest và ném lỗi rõ ràng nếu lệch — bắt sớm trường hợp Chroma và manifest JSON bị lệch nhau (ví dụ xoá tay `data/chroma/` nhưng quên rebuild).
- **Hybrid search bằng Reciprocal Rank Fusion**: dense cosine (MiniLM) và lexical TF-IDF unigram/bigram (title được nhân trọng số gấp đôi) được hoà trộn bằng RRF (`k=60`) thay vì cộng điểm trực tiếp — vì thang điểm cosine và TF-IDF không cùng đơn vị, cộng trực tiếp sẽ thiên vị theo scale của từng phía. Hybrid là candidate, `dense` vẫn là mặc định cho đến khi có đủ bằng chứng vượt gate trên cả 3 trạng thái.
- **QA an toàn (không đoán bừa)**: `answer_question()` trích tham chiếu chính xác (tên trong ngoặc kép hoặc DOI) bằng regex; nếu người dùng chỉ rõ một title/DOI không có trong corpus, hàm trả lời "không biết" ngay thay vì rơi về kết quả gần nhất — tránh hallucination khi câu hỏi có ý định tra cứu chính xác.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | Dataframe sạch (`paper_id`, `title`, `published`, `authors_joined`, `categories_joined`, `summary`, `abs_url`, `pdf_url`, `text_for_embedding`) từ `cleaning.py` |
| Output                         | Manifest JSON (`backend`, `embedding_model`, `persist_path`, `collection_name`, `documents`) + collection Chroma cosine tương ứng |
| Module phụ thuộc             | `core.config.Settings` (đường dẫn, tên collection, `top_k`), `sentence-transformers`, `chromadb` |
| Module sử dụng output        | `src/pipelines/phase1.py`, `corruption_flow.py` (Thành viên 1), `src/evaluation/metrics.py` (Thành viên 4) |
| Điều kiện lỗi cần xử lý | Dataframe rỗng hoặc thiếu cột bắt buộc → `ValueError`; `paper_id`/`title`/`text_for_embedding` rỗng ở một dòng → `ValueError`; manifest và collection lệch số bản ghi khi `load()` → `RuntimeError`; câu hỏi rỗng → `ValueError` |

### Cách xác minh

```powershell
python script/run_phase1.py
python -m pytest tests/test_retrieval.py -q
python script/benchmark_retrieval.py --top-k 4
python script/benchmark_retrieval.py --manifest data/embeddings/papers_embeddings_corrupted.json --top-k 4
python script/benchmark_retrieval.py --manifest data/embeddings/papers_embeddings_repaired.json --top-k 4
```

- **Kết quả mong đợi:** `run_phase1.py` thoát code 0, tạo `papers-baseline` với số vector bằng số dòng `papers_clean.csv`; `pytest` pass toàn bộ (embedding giả lập bằng fake `SentenceTransformer`, không cần tải model thật); benchmark in ra Hit@4/Top-1/MRR@4/latency cho từng manifest.
- **Kết quả thực tế:** `data/results/baseline_metrics.json` ghi `retrieval_hit_rate: 1.0`, `mean_token_f1: 1.0` trên bộ 10 câu hỏi test set — khớp kỳ vọng vì baseline dùng dữ liệu sạch và exact-match guard bắt đúng các câu hỏi có tên bài rõ ràng.
- **Artifact/log:** `data/embeddings/papers_embeddings*.json`, `data/chroma/`, `data/results/baseline_answers.json`, `data/results/baseline_metrics.json` (không chứa secret).

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần một chiến lược truy vấn cho corpus 24 bài báo nhỏ, nơi nhiều câu hỏi benchmark hỏi đích danh tên bài báo (dạng "Summarize the paper '...'"). Chỉ dùng thuần dense retrieval có nguy cơ chọn nhầm bài tương tự về ngữ nghĩa thay vì đúng bài được hỏi.
- **Các phương án đã cân nhắc:**
  1. Chỉ dùng dense cosine similarity (MiniLM) cho mọi câu hỏi.
  2. Dense + một bước "exact reference lookup" tách riêng: khi câu hỏi chứa tên trong ngoặc kép hoặc DOI khớp chính xác với corpus, ưu tiên tuyệt đối kết quả đó trước khi hoà vào danh sách dense.
  3. Hybrid dense + TF-IDF làm mặc định ngay từ đầu.
- **Phương án đã chọn:** Phương án 2 (`_extract_exact_reference` trong `qa.py`, kết hợp `index.lookup()`), giữ `dense` làm chiến lược mặc định cho `search()`, còn `hybrid` (RRF) chỉ là candidate có thể bật bằng tham số.
- **Lý do:** Exact-match guard giải quyết đúng vấn đề thực tế của bộ test set (nhiều câu hỏi có định danh chính xác) mà không cần thay đổi hành vi mặc định của toàn bộ hệ thống truy vấn — giảm rủi ro so với việc đổi mặc định sang hybrid khi chưa có đủ bằng chứng nó tốt hơn trên cả 3 trạng thái dữ liệu (baseline/corrupted/repaired).
- **Bằng chứng quyết định phù hợp:** `data/results/baseline_metrics.json` đạt `retrieval_hit_rate = 1.0` trên 10/10 câu hỏi; khi dữ liệu bị tiêm lỗi (ví dụ tiêu đề bị cắt ngắn khiến exact-match không còn khớp), `corrupted_metrics.json` giảm còn `0.6`, đúng như kỳ vọng — guard chỉ bảo vệ được khi dữ liệu còn nguyên vẹn, không che giấu lỗi dữ liệu.

## 6. Một lỗi hoặc blocker đã xử lý

- Opus5.5 thông minh quá nên chỉ cần duyệt plan xong là Sonnet 5 làm mượt ạ.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. **Từ Crossref đến vector index:** `crossref.py` gọi Crossref REST API (hoặc fallback snapshot `data/raw/crossref_response.json`) lấy 24 bản ghi, `cleaning.py` khử trùng lặp theo `paper_id`, bỏ tag JATS, tính `age_days`, ghép `text_for_embedding` gồm 5 phần (title, authors, categories, summary, published) rồi xuất `data/clean/papers_clean.csv`. `LocalEmbeddingIndex.build()` (module của tôi) đọc dataframe này, nhúng `text_for_embedding` bằng `all-MiniLM-L6-v2` (chuẩn hoá L2), rồi nạp vào một collection ChromaDB cosine tương ứng với trạng thái (baseline/corrupted/repaired), đồng thời ghi manifest JSON cho phép `load()` lại mà không cần build lại vector.
2. **Test set & ground-truth doc IDs:** `testset.py` (Thành viên 4) sinh 10 câu hỏi cố định (summary/authors/date/categories) kèm `ground_truth` và `ground_truth_doc_ids` (DOI thật của bài báo trong corpus). Cả 3 lần chạy (baseline, corrupted, repaired) dùng chung một `test_set.json` này — module `metrics.py` so khớp `retrieved_doc_ids` từ `answer_question()` của tôi với `ground_truth_doc_ids` để tính `retrieval_hit_rate`, và so khớp `answer` với `ground_truth` bằng token F1 và LLM judge (hoặc heuristic khi không có API key).
3. **Quality checks khác freshness monitoring ở đâu:** Freshness giám sát *thời gian* (tỷ lệ bản ghi có `age_days` vượt ngưỡng 180 ngày, SLA ≤ 25%), còn Great Expectations 1.x (`quality.py`) kiểm tra *cấu trúc & nội dung* — ví dụ cột không null, `paper_id` không trùng, độ dài `summary` tối thiểu — chạy như một cổng chặn (quality gate) ngay sau bước cleaning và trước khi dữ liệu được đưa vào index của tôi; nếu gate fail, pipeline dừng trước khi build index, nên `retrieval/` không bao giờ nhận dữ liệu đã biết là hỏng cấu trúc.
4. **Vì sao dùng cùng test set cho cả 3 trạng thái:** Nếu mỗi trạng thái dùng bộ câu hỏi khác nhau, sự chênh lệch chỉ số (Hit Rate, F1) có thể do câu hỏi khác nhau dễ/khó khác nhau chứ không phản ánh đúng ảnh hưởng của việc tiêm lỗi hay hiệu quả phục hồi — dùng chung `test_set.json` giữ biến kiểm soát duy nhất là chất lượng dữ liệu trong từng collection Chroma.
5. **Repair thành công dựa trên artifact/metric nào:** `corruption_flow.py` build lại dữ liệu từ `data/raw/crossref_records.json` gốc (không phải từ bản đã bị tiêm lỗi), nạp vào collection `papers-repaired` riêng biệt, rồi so `repaired_metrics.json` với `baseline_metrics.json`. Repair được coi là thành công khi các chỉ số (`retrieval_hit_rate`, `mean_token_f1`, `judge_accuracy`) của repaired quay lại đúng giá trị baseline và `repair_verification.json`/`is_idempotent` xác nhận chạy lại nhiều lần cho kết quả giống hệt nhau.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |      1.0 |       0.6 |      1.0 | Đúng như kỳ vọng: index của tôi build lại hoàn toàn từ raw data cho collection repaired, nên hit rate phục hồi tuyệt đối, không có mất mát tích luỹ. |
| `mean_token_f1`      |      1.0 |       0.5 |      1.0 | Corrupted giảm mạnh vì exact-match guard trong `qa.py` mất tác dụng khi tiêu đề/DOI bị tiêm lỗi (cắt ngắn, ký tự rác), khiến `answer_question()` rơi về "I don't know" cho nhiều câu. |
| `judge_accuracy`     |      1.0 |       0.5 |      1.0 | Ở lần chạy nộp bài không có API key nên judge dùng heuristic theo token F1 (`judge_fallbacks = 10/10`), nên xu hướng bám sát `mean_token_f1`. |
| `mean_judge_score`   |        5 |         3 |        5 | Cùng nguyên nhân judge heuristic ở trên. |
| Quality checks         | PASS (6/6 expectations) | FAILED | PASS | Quality gate (Thành viên 4) chặn đúng thời điểm dữ liệu lỗi được nạp, độc lập với retrieval nhưng là điều kiện tiên quyết để `retrieval/` nhận dữ liệu sạch. |
| Freshness status       | OK (4.2% quá hạn) | WARNING | OK | Freshness không liên quan trực tiếp tới `retrieval/` nhưng cùng là tín hiệu Silent Failure song song với sụt giảm Hit Rate. |

### Kết luận từ số liệu

1. **Tiêm lỗi (cắt ngắn tiêu đề, chèn ký tự rác, xoá summary) → quality gate FAILED + freshness WARNING → `retrieval_hit_rate` giảm từ 1.0 xuống 0.6 và `mean_token_f1` giảm từ 1.0 xuống 0.5.** Cơ chế cụ thể ở tầng của tôi: nhiều câu hỏi benchmark dùng đúng cú pháp `'title'` để kích hoạt exact-match guard trong `qa.py`; khi tiêu đề bị corrupt, `index.lookup()` không tìm thấy khớp chính xác và hàm rơi về dense search trên nội dung đã bị nhiễu, hoặc trả lời "I don't know" khi `exact_reference` được trích ra nhưng không tồn tại trong corpus (đúng thiết kế an toàn, không đoán bừa).
2. **Repair (rebuild từ `crossref_records.json` gốc) → quality/freshness phục hồi PASS/OK → `retrieval_hit_rate` và `mean_token_f1` phục hồi hoàn toàn về 1.0.** Vì collection `papers-repaired` được build lại từ đầu bằng `LocalEmbeddingIndex.build()` trên dữ liệu raw gốc (không phải patch dữ liệu đã lỗi), nên không có hiệu ứng "sẹo" — đây chính là lý do thiết kế 3 collection tách biệt của tôi quan trọng: nếu repair ghi đè lên collection đang dùng để đo corrupted, phép so sánh sẽ không còn ý nghĩa.

Corruption ảnh hưởng rõ nhất là các lỗi tác động trực tiếp lên `title`/`summary` dùng trong exact-match guard và `text_for_embedding` (cắt ngắn tiêu đề, chèn ký tự rác, xoá summary), vì đây là 2 tín hiệu chính mà tầng retrieval của tôi dùng để định vị đúng bài báo; các lỗi chỉ ảnh hưởng ngày tháng (làm cũ ngày) tác động tới freshness nhưng không trực tiếp làm giảm Hit Rate vì `age_days` không tham gia vào embedding hay exact-match.

Kết quả không khác kỳ vọng ban đầu — giả thuyết trước khi chạy là corrupted sẽ giảm rõ rệt do guard mất tác dụng và repaired sẽ phục hồi hoàn toàn nhờ rebuild từ raw; số liệu thực tế khớp với giả thuyết này.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Về data pipeline: một module hạ nguồn (retrieval) không nên tin dữ liệu đầu vào "chắc chắn sạch" chỉ vì bước trước không báo lỗi — phải tự validate ở boundary của chính mình (dataframe rỗng, thiếu cột, `paper_id`/`title` trống).
2. Về data quality/observability: tách collection theo trạng thái (baseline/corrupted/repaired) là một dạng observability ở tầng lưu trữ — cho phép đo lường tác động của lỗi dữ liệu mà không cần rollback hay backup thủ công, và giữ baseline làm đường tham chiếu bất biến trong suốt thí nghiệm.
3. Về ảnh hưởng của data đến RAG agent: một guard tưởng như "an toàn hơn" (exact-match ưu tiên tuyệt đối) lại chính là điểm nhạy cảm nhất với data corruption — vì nó phụ thuộc vào tính chính xác tuyệt đối của `title`/DOI, nên corruption ở đúng 2 trường này gây sụt giảm chỉ số nặng nhất trong toàn hệ thống.

### Nếu có thêm thời gian

Muốn benchmark có hệ thống hơn việc so sánh `dense` và `hybrid` trên cả 3 trạng thái (hiện `script/benchmark_retrieval.py` mới đưa ra gate sơ bộ Hit@4/MRR@4/latency, chưa phải điều kiện chấp nhận chính thức để đổi mặc định). Cách đo: chạy benchmark trên cả 3 manifest với cả hai `strategy`, so sánh xem `hybrid` có giữ được Hit@4 cao hơn `dense` trên tập corrupted (nhờ tín hiệu TF-IDF bù cho embedding bị nhiễu) mà không làm giảm MRR@4 trên baseline — chỉ khi đó mới đổi mặc định sang hybrid.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Hồ Đăng Phúc
**Ngày xác nhận:** 2026-09-25
