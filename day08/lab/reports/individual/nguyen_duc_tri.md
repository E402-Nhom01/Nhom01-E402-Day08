# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline

**Họ và tên:** Nguyễn Đức Trí  
**MSSV:** 2A202600394  
**Vai trò trong nhóm:** Tech Lead / Retrieval Owner / Eval Owner / Documentation Owner  
**Ngày nộp:**13/04/2026
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi đã làm gì trong lab này? (100-150 từ)

> Sprint 3 em lựa chọn implement hybrid retrieval kết hợp rerank để tối ưu cả recall và precision. Cụ thể, pipeline được giữ nguyên bước retrieve rộng với retrieve_hybrid() nhằm tận dụng ưu điểm của dense (hiểu ngữ nghĩa) và sparse/BM25 (match keyword chính xác), giúp giảm miss các chunk quan trọng. Sau đó, bật use_rerank=True để áp dụng cross-encoder (ms-marco-MiniLM-L-6-v2) chấm lại độ liên quan giữa query và từng chunk, từ đó chọn ra top-3 chunk chất lượng cao nhất trước khi đưa vào prompt. Quyết định này dựa trên thực tế rằng hybrid giúp tăng coverage nhưng vẫn có noise, nên rerank đóng vai trò “lọc tinh”. So với baseline dense, variant này cải thiện rõ độ chính xác câu trả lời và giảm hallucination do context đầu vào sạch và sát hơn.

_________________

---

## 2. Điều tôi hiểu rõ hơn sau lab này (100-150 từ)

> Sau lab này, tôi hiểu rõ hơn về hybrid retrieval và grounded prompt. Với hybrid retrieval, trước đây tôi nghĩ chỉ cần dense là đủ, nhưng khi làm thực tế mới thấy dense có thể bỏ sót keyword quan trọng, còn BM25 lại không hiểu ngữ nghĩa. Kết hợp cả hai giúp tăng khả năng tìm đúng tài liệu liên quan, đặc biệt trong các query có cả thuật ngữ kỹ thuật và cách diễn đạt tự nhiên. Ngoài ra, grounded prompt giúp kiểm soát LLM tốt hơn rất nhiều. Thay vì để model trả lời tự do, việc ép nó chỉ dùng context đã retrieve và phải trích dẫn nguồn giúp giảm hallucination rõ rệt. Tôi nhận ra prompt không chỉ để “hỏi” mà còn là công cụ để “ràng buộc hành vi” của model.

_________________

---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn (100-150 từ)

> Điều không đúng kỳ vọng nhất là khi sử dụng Gemini API, đặc biệt là vấn đề rate limit. Ban đầu tôi nghĩ hiệu suất của API khá ổn và có thể xử lý nhiều request liên tục, nhất là khi đã thử dùng nhiều API key từ các account khác nhau. Tuy nhiên, thực tế lại thường xuyên gặp lỗi Rate limit hit, khiến pipeline bị chậm đáng kể do phải retry và chờ (30s mỗi lần). Đây cũng là phần tốn nhiều thời gian debug nhất vì ban đầu tôi nghi ngờ lỗi nằm ở code (loop gọi API, prompt quá dài, hoặc cấu hình model).

Sau khi kiểm tra kỹ, tôi nhận ra vấn đề không phải do logic code mà do giới hạn từ phía API. Điều này khiến tôi hiểu rõ hơn rằng khi xây dựng hệ thống RAG thực tế, cần tính đến batching, caching hoặc fallback model để tránh phụ thuộc hoàn toàn vào một API.

_________________

---

## 4. Phân tích một câu hỏi trong scorecard (150-200 từ)

> Câu hỏi: q09 — "ERR-403-AUTH là lỗi gì và cách xử lý?"
Phân tích:
Đây là dạng câu hỏi dùng để kiểm tra khả năng abstain. Trong corpus không hề có thông tin về mã lỗi ERR-403-AUTH.
Baseline (dense): Dense retrieval vẫn trả về các chunk từ IT Helpdesk FAQ liên quan đến “đăng nhập” hoặc “tài khoản bị khóa”. Những nội dung này có liên quan về mặt ngữ nghĩa với lỗi xác thực (auth error) nhưng không đề cập trực tiếp đến ERR-403-AUTH. Nếu prompt không đủ chặt, model dễ suy diễn và tạo ra câu trả lời không có trong dữ liệu, dẫn đến giảm độ faithfulness.
Vấn đề chính: Nằm ở bước generation. Retriever đã làm đúng nhiệm vụ (lấy các chunk gần nhất), nhưng model cần nhận ra rằng không có bằng chứng cụ thể và phải từ chối trả lời.
Variant (hybrid + rerank): Rerank bằng cross-encoder giúp đánh giá lại độ liên quan chính xác hơn, loại bỏ các chunk chỉ “gần nghĩa”. Kết hợp với prompt chống hallucination, hệ thống có thể trả lời đúng theo hướng: không có thông tin trong tài liệu.
_________________

---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì? (50-100 từ)
> Nếu có thêm thời gian, tôi sẽ thử query transformation (đặc biệt là HyDE) vì trong quá trình test, một số query mơ hồ hoặc diễn đạt khác với tài liệu khiến retrieval chưa tốt, dù đã dùng hybrid. Tôi muốn kiểm tra xem việc sinh “hypothetical answer” rồi embed có giúp tăng recall không. Ngoài ra, tôi sẽ thêm một evaluation loop đơn giản (precision@k hoặc human check) vì hiện tại mới đánh giá cảm tính. Điều này giúp tôi đo rõ variant nào thực sự cải thiện thay vì chỉ dựa vào quan sát.

_________________

---

*Lưu file này với tên: `reports/individual/nguyen_duc_tri.md`*
