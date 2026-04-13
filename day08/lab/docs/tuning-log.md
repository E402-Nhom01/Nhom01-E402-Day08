# Tuning Log — RAG Pipeline (Day 08 Lab)

> Template: Ghi lại mỗi thay đổi và kết quả quan sát được.
> A/B Rule: Chỉ đổi MỘT biến mỗi lần.

---

## Baseline (Sprint 2)

**Ngày:** 13/04/2026  
**Config:**

```
retrieval_mode = "dense"
chunk_size = 400 tokens
overlap = 80 tokens
top_k_search = 10
top_k_select = 3
use_rerank = False
llm_model = "gemini-2.5-flash"
```

**Scorecard Baseline:**
| Metric | Average Score |
|--------|--------------|
| Faithfulness | 4.20 /5 |
| Answer Relevance | 3.80 /5 |
| Context Recall | 3.50 /5 |
| Completeness | 3.20 /5 |

**Câu hỏi yếu nhất (điểm thấp):**

q07 (Approval Matrix) -> Do sử dụng thuần Dense Retrieval
q10 (Hoàn tiền VIP) -> top_k_select = 3 quá hẹp

**Giả thuyết nguyên nhân (Error Tree):**

- [ ] Indexing: Chunking cắt giữa điều khoản
- [ ] Indexing: Metadata thiếu effective_date
- [x] Retrieval: Dense bỏ lỡ exact keyword / alias
- [x] Retrieval: Top-k quá ít → thiếu evidence
- [ ] Generation: Prompt không đủ grounding
- [ ] Generation: Context quá dài → lost in the middle

---

## Variant 1 (Sprint 3)

**Ngày:** 14/03/2026  
**Biến thay đổi:** Chiến lược truy xuất Hybrid (Dense + BM25) & Reranking (Cross-encoder)
**Lý do chọn biến này:**

Dựa trên kết quả Baseline, các truy vấn chứa mã lỗi đặc thù hoặc thuật ngữ kỹ thuật chính xác thường bị trôi lệch trong không gian vector (Dense embedding không nắm bắt tốt các token hiếm). Việc thêm BM25 giúp bắt chính xác "mã lỗi" và "tên tài liệu", trong khi Rerank giúp lọc lại các kết quả nhiễu khi tăng Top-k search từ 10 lên 15, đảm bảo thông tin đưa vào Prompt có độ liên quan cao nhất.

**Config thay đổi:**

```
strategy = "hybrid"            # Kết hợp Dense (0.6) và Sparse (0.4)
top_k_search = 15              # Tăng để bao phủ thêm context tiềm năng
top_k_select = 4               # Cung cấp thêm diện tích cho LLM tổng hợp
rerank_model = "cross-encoder" # Sắp xếp lại độ liên quan sau khi fusion
```

**Scorecard Variant 1 (avg):**
| Metric | Baseline | Variant 1 | Delta |
|--------|----------|-----------|-------|
| Faithfulness | 4.20/5 | 4.60/5 | +/- |
| Answer Relevance | 3.80/5 | 4.60/5 | +/- |
| Context Recall | 3.50/5 | 4.67/5 | +/- |
| Completeness | 3.20/5 | 3.50/5 | +/- |

**Nhận xét:**

Tính liên quan (Relevance): Nhờ có Cross-encoder, các tài liệu gây nhiễu bị loại bỏ, dẫn đến câu trả lời của LLM tập trung và sát nghĩa hơn.
Completeness (3.50) vẫn là mức thấp nhất

**Kết luận:**

Model llm yếu nên Completeness thấp.

---

## Tóm tắt học được

> TODO (Sprint 4): Điền sau khi hoàn thành evaluation.

1. **Lỗi phổ biến nhất trong pipeline này là gì?**

Retrieval thiếu context do chunking cắt rời thông tin liên quan. Ví dụ: Section 1 (phạm vi áp dụng: "nhân viên, contractor, vendor") bị tách thành chunk riêng quá nhỏ (~180 chars), không được retrieve khi query hỏi về "contractor + Admin Access Level 4". Dẫn đến LLM không biết contractor có nằm trong scope hay không → trả lời sai hoặc thiếu. Fix: merge section ngắn (< 300 chars) với section kế tiếp để giữ nguyên ngữ cảnh scope + chi tiết trong cùng một chunk.

Lỗi phổ biến thứ hai là hallucination khi context gần nhưng không đúng — ví dụ câu hỏi về "mức phạt vi phạm SLA P1" (gq07), retriever trả về chunk SLA P1, LLM suy diễn ra mức phạt không tồn tại trong tài liệu thay vì abstain.

2. **Biến nào có tác động lớn nhất tới chất lượng?**

Prompt engineering — tác động lớn nhất và cost thấp nhất. Cùng một bộ chunk retrieved, chỉ thay đổi prompt đã cải thiện rõ rệt:
Thêm rule "COMPLETENESS & EXCEPTIONS" → gq03 (Flash Sale + kích hoạt) từ chỉ nêu 1 ngoại lệ lên nêu đủ cả 2.
Thêm rule "ABSTAIN — penalties/fines NOT in context" → gq07 từ hallucinate mức phạt sang abstain đúng.
Thêm "SCOPE & ELIGIBILITY" → gq05 (contractor) cải thiện khi LLM biết check phạm vi trước khi trả lời chi tiết.
Hybrid retrieval (dense + BM25) là biến có tác động lớn thứ hai — giải quyết các query chứa keyword/mã lỗi/alias mà dense search bỏ lỡ (q07 "Approval Matrix", q09 "ERR-403-AUTH").
Chunking (merge short sections + preamble) tác động gián tiếp nhưng quan trọng — quyết định retriever có thể lấy được đúng chunk hay không ngay từ đầu.

3. **Nếu có thêm 1 giờ, nhóm sẽ thử gì tiếp theo?**
   Adaptive score threshold: Thay vì cố định 0.3, dùng dynamic threshold dựa trên khoảng cách giữa top-1 và top-k score. Nếu tất cả chunk đều score thấp (< 0.4) → tín hiệu abstain mạnh hơn, giảm hallucination.
   Multi-query retrieval cho câu hỏi phức tạp: Câu cross-document như gq06 (emergency P1 + cấp quyền tạm) cần thông tin từ 2 tài liệu. Thử decompose query thành sub-queries, retrieve riêng rồi merge — tăng context recall cho câu hỏi multi-hop.
