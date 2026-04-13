# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline

**Họ và tên:** Trương Minh Tiền  
**MSSV:** 2A202600438  
**Vai trò trong nhóm:** Retrieval Owner  
**Ngày nộp:** 2026-04-13  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi đã làm gì trong lab này? (100-150 từ)

Tôi đảm nhận vai trò Retrieval Owner, chủ yếu làm Sprint 2 — xây dựng baseline retrieval và grounded answer function.

Cụ thể, tôi implement:
- **`retrieve_dense()`**: Query ChromaDB bằng embedding vector, convert cosine distance sang similarity score, thêm threshold filter (score > 0.3) để loại bỏ chunk nhiễu.
- **`retrieve_sparse()`**: BM25 keyword search sử dụng rank-bm25, tokenize corpus và query rồi rank theo BM25 score.
- **`build_context_block()`** và **`build_grounded_prompt()`**: Đóng gói retrieved chunks thành context có đánh số [1], [2]... và xây dựng prompt ép model chỉ trả lời từ context, có citation, abstain khi thiếu dữ liệu.
- **`call_llm()`**: Gọi Gemini API với retry logic cho rate limit.

Phần của tôi là cầu nối giữa Sprint 1 (index) và Sprint 3 (tuning) — output của retrieve_dense() được Sprint 3 dùng làm baseline để so sánh với hybrid và rerank.

---

## 2. Điều tôi hiểu rõ hơn sau lab này (100-150 từ)

Sau lab này tôi hiểu rõ hơn hai concept:

**Dense retrieval với cosine similarity**: Trước đây tôi chỉ biết "embedding search" là tìm vector gần nhau. Khi implement thực tế, tôi nhận ra cosine distance từ ChromaDB cần convert sang similarity (1 - distance), và quan trọng hơn là cần threshold filtering. Không phải chunk nào trả về cũng relevant — nhiều chunk score 0.2-0.3 hoàn toàn là noise. Việc set threshold 0.3 giúp loại bỏ chunk không liên quan trước khi đưa vào prompt.

**Grounded prompt design**: Tôi hiểu tại sao prompt phải có 4 quy tắc: evidence-only, abstain, citation, short/clear. Khi test với câu "ERR-403-AUTH", nếu prompt không có quy tắc abstain, model sẽ bịa ra câu trả lời từ general knowledge. Prompt engineering không chỉ là viết câu hay mà là thiết kế constraint cho model.

---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn (100-150 từ)

Điều ngạc nhiên nhất là **dense search đủ tốt cho câu hỏi đơn giản nhưng fail với keyword/mã lỗi**. Khi test "SLA ticket P1 là bao lâu?", dense retrieval trả về chunk chính xác ngay. Nhưng với "ERR-403-AUTH", dense search trả về chunk hoàn toàn không liên quan vì embedding không capture được mã lỗi cụ thể — đây là lý do cần BM25/hybrid search ở Sprint 3.

Khó khăn lớn nhất là **Gemini rate limit**. Ban đầu tôi chỉ có retry đơn giản với sleep cố định 30 giây, nhưng khi chạy evaluation 10 câu liên tiếp, rate limit liên tục bị hit. Phải chuyển sang exponential backoff với jitter mới ổn định. Giả thuyết ban đầu "gọi API tuần tự là đủ" hoàn toàn sai — cần spacing thông minh hơn.

---

## 4. Phân tích một câu hỏi trong scorecard (150-200 từ)

**Câu hỏi:** q09 — "ERR-403-AUTH là lỗi gì và cách xử lý?"

**Phân tích:**

Đây là câu hỏi kiểm tra khả năng **abstain** — thông tin về mã lỗi ERR-403-AUTH không tồn tại trong bất kỳ tài liệu nào trong corpus.

**Baseline (dense):** Dense retrieval trả về các chunk từ IT Helpdesk FAQ có chứa từ "đăng nhập", "tài khoản bị khóa" — semantic gần với "auth error" nhưng không phải ERR-403-AUTH. Nếu prompt không đủ mạnh, model sẽ suy diễn từ các chunk này và bịa ra câu trả lời. Điểm Faithfulness thấp nếu model hallucinate.

**Lỗi nằm ở:** Generation — retriever đúng khi trả về chunk liên quan nhất có thể, nhưng generation phải nhận ra rằng không chunk nào thực sự chứa "ERR-403-AUTH" và abstain. Đây là bài test cho grounded prompt design.

**Variant (hybrid + rerank):** Rerank giúp vì cross-encoder chấm lại relevance chính xác hơn — score thấp cho chunk chỉ "gần nghĩa" nhưng không match. Kết hợp với prompt anti-hallucination mạnh, variant abstain đúng: "Không tìm thấy thông tin về ERR-403-AUTH trong tài liệu hiện có."

---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì? (50-100 từ)

1. **Adaptive threshold cho dense retrieval**: Hiện tại threshold cố định 0.3 cho mọi query. Tôi sẽ thử dynamic threshold dựa trên score distribution — nếu top chunk chỉ đạt 0.35 thì đó là tín hiệu abstain, khác với trường hợp top chunk đạt 0.8.

2. **Query expansion cho mã lỗi**: Kết quả eval cho thấy dense search yếu với keyword/code. Tôi sẽ thử thêm bước detect query type — nếu query chứa pattern mã lỗi (ERR-xxx), tự động chuyển sang BM25-first thay vì dense-first.

---

*Lưu file này với tên: `reports/individual/truong_minh_tien.md`*
