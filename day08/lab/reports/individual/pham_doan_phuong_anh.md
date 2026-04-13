# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline

**Họ và tên:** Phạm Đoàn Phương Anh  
**MSSV:** 2A202600257  
**Vai trò trong nhóm:** Tech Lead / Retrieval Owner / Eval Owner / Documentation Owner  
**Ngày nộp:** ___________  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi đã làm gì trong lab này? (100-150 từ)

Trong lab này, mình phụ trách chính Sprint 1 với việc xây dựng baseline pipeline cho toàn bộ nhóm. Mình thiết lập flow cơ bản của RAG (chunking → indexing → retrieval → generation) để các thành viên có thể phát triển thêm ở các sprint sau.

Bên cạnh đó, ở các Sprint 2, 3, 4, mình đều có tham gia hỗ trợ tinh chỉnh các chi tiết nhỏ. Ví dụ, ở Sprint 2, mình cùng các bạn điều chỉnh chiến lược chunking (chunk size, overlap); ở Sprint 3, khi test với bộ test_questions, mình phân tích lỗi và đề xuất hướng viết prompt theo kiểu phân tách điều kiện và kiểm tra grounding.

Dù một số thử nghiệm chưa đạt kết quả tối ưu (do hạn chế của model backbone), pipeline tổng thể vẫn hoạt động ổn định. Ngoài ra, với vai trò Tech Lead, mình cũng log và in score để giúp các thành viên hiểu cách đánh giá và cải thiện hệ thống.

_________________

---

## 2. Điều tôi hiểu rõ hơn sau lab này (100-150 từ)

Sau lab này, mình hiểu rõ hơn cách một pipeline RAG vận hành end-to-end và cách debug từng bước trong pipeline, đặc biệt khi LLM hoạt động như một “blackbox”. Thay vì chỉ nhìn vào output cuối, mình học cách kiểm tra từng thành phần như retrieval có đúng context chưa, hay prompt có đủ constraint để ép model trả lời đúng không.

Điểm mình thấy thú vị nhất là hybrid retrieval. Việc kết hợp giữa dense retrieval và BM25 giúp cân bằng giữa semantic matching và keyword matching, từ đó cải thiện đáng kể khả năng tìm đúng tài liệu. Ngoài ra, những “tip & trick” nhỏ như điều chỉnh threshold của cosine similarity hoặc ép format citation cũng ảnh hưởng rất lớn đến kết quả cuối.

Phần evaluation bằng LLM cũng giúp mình hiểu rõ hơn cách dùng model để tự chấm điểm và giải thích output, mang tính “thực chiến” cao.
_________________

---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn (100-150 từ)

Điều khiến mình ngạc nhiên nhất là với những câu hỏi khó, model thường không “tìm điểm rơi” hợp lý mà trả lời trực tiếp là không có thông tin, thay vì cố gắng diễn đạt một câu trả lời gần đúng bằng ngôn ngữ tự nhiên.

Ban đầu, mình kỳ vọng rằng khi retrieval đã cung cấp một phần context liên quan, model có thể tận dụng để suy luận hoặc trả lời một phần. Tuy nhiên, với các constraint prompt chặt (ví dụ bắt buộc citation), model lại có xu hướng “fail-safe” bằng cách từ chối trả lời.

Khó khăn lớn nhất là cân bằng giữa anti-hallucination và answer coverage. Nếu prompt quá strict, model sẽ abstain quá nhiều; nhưng nếu nới lỏng, lại dễ bị hallucination. Việc tìm được mức cân bằng này mất khá nhiều thời gian thử nghiệm.

_________________

---

## 4. Phân tích một câu hỏi trong scorecard (150-200 từ)

> Chọn 1 câu hỏi trong test_questions.json mà nhóm bạn thấy thú vị.
> Phân tích:
> - Baseline trả lời đúng hay sai? Điểm như thế nào?
> - Lỗi nằm ở đâu: indexing / retrieval / generation?
> - Variant có cải thiện không? Tại sao có/không?

**Câu hỏi:** ___________

**Phân tích:**

_________________

---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì? (50-100 từ)

Nếu có thêm thời gian, mình sẽ tiếp tục tune hybrid retrieval, đặc biệt là điều chỉnh trọng số giữa dense và BM25 hoặc thử dynamic top-k để cải thiện coverage.

Ngoài ra, mình muốn thử thiết kế lại prompt theo hướng “mềm” hơn một chút để model có thể trả lời tự nhiên hơn, thay vì luôn rơi vào trạng thái “Không đủ dữ liệu”, trong khi vẫn đảm bảo hạn chế hallucination.
_________________

---

*Lưu file này với tên: `reports/individual/pham_doan_phuong_anh.md`*
