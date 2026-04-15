# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Huỳnh Thái Bảo  
**Vai trò:**  Embed & Idempotency Owner (Trọng tâm Sprint 3)  
**Ngày nộp:** 15/04/2026  
**Độ dài yêu cầu:** **400–650 từ**

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**
- Script đánh giá: `eval_retrieval.py` và xuất kết quả ra thư mục `artifacts/eval/`.
- Kịch bản tiêm lỗi trên `etl_pipeline.py`.
- Viết báo cáo đối chiếu kết quả trả về của RAG: `docs/quality_report.md`.

**Kết nối với thành viên khác:**
Nhiệm vụ của tôi ở Sprint 3 là độc lập đánh giá "thành quả" của bạn Cleaning Owner. Bạn ấy viết rule lọc dữ liệu, còn tôi sắm vai trò Tester/Evaluator: tôi cố tình bypass các rule đó (tiêm lỗi - inject corruption) để đẩy dữ liệu bẩn vào Vector DB. Sau đó, tôi thu thập chứng cứ để chứng minh rằng nếu Agent RAG không có các rule làm sạch của team thì AI sẽ lấy nhầm tài liệu cũ và trả lời sai lệch ra sao, qua đó bảo vệ giá trị ứng dụng của Data Pipeline.

**Bằng chứng:**
Tôi xuất thành công các file đánh giá làm minh chứng trước/sau: `after_inject_bad.csv` và `before_after_eval.csv` (ứng với run_id: `inject-bad` và `fix-good`).

---

## 2. Một quyết định kỹ thuật (100–150 từ)

Quyết định kỹ thuật trọng tâm của tôi ở phần công việc Sprint 3 là cách thiết lập kịch bản đánh giá (A/B testing) mức độ an toàn của RAG. Thay vì sửa tráo đổi data raw csv thủ công để test (rất tốn thời gian và dễ phá hỏng cấu trúc nguồn của nhóm), tôi quyết định dùng cơ chế của pipeline là truyền cờ bypass lỗi `--no-refund-fix` và `--skip-validate`. 

Khi chạy với lệnh này (run_id `inject-bad`), hệ thống bị ép ép nạp một đoạn chunk policy cũ (chính sách "14 ngày làm việc" đã phế bỏ). Việc dùng code can thiệp kiểm tra lỗi lúc này không chỉ xem Top-1 có ra tài liệu đúng không, mà tôi quyết định ứng dụng logic quét toàn bộ Top-K chunk cho cột `hits_forbidden`. Điều này khẳng định 100% nếu có tài liệu cấm nào lọt vào Context của RAG đều không thể trốn thoát được sự phát hiện của script Eval.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

**Triệu chứng:** Ở lần chạy `inject-bad` để mô phỏng sự cố rò rỉ dữ liệu (không đi qua bước clean data chuẩn), hệ thống dính anomaly "Stale Data" (dữ liệu thiu). Khi LLM nhận câu hỏi "Khách hàng có bao nhiêu ngày để hoàn tiền?", do Vector DB lúc này chứa cả bản policy 14 ngày, mô hình RAG bị nhiễu thông tin. Metric `hits_forbidden` đổi cảnh báo từ `no` sang `yes`.

**Cách xử lý:** Sự cố giải lập này cảnh báo cho team rằng dị thường về "conflict version" không thể fix dán tiếp bằng Prompt LLM. Tôi đối chiếu lại với file chạy `fix-good`. Ở luồng chuẩn, Data Pipeline chặn đứng policy cũ ở Quarantine, không cho rò rỉ vào Chroma. Kết quả là `hits_forbidden` trở lại an toàn (`no`), agent Vector DB hoàn toàn miễn nhiễm với Stale Data.

---

## 4. Bằng chứng trước / sau (80–120 từ)

Trích xuất so sánh sự cố trực tiếp trên file CSV đối với câu hỏi `q_refund_window`:

**Trước (Dữ liệu bị Corrupted do tiêm bypass báo lỗi):**
`q_refund_window,...policy_refund_v4,Yêu cầu được gửi trong vòng 7 ngày làm việc...,yes,yes,,3`
*(Nhận xét: Nguy hiểm ngầm vì `contains_expected=yes` làm lầm tưởng hệ thống trả lời đúng, nhưng quét kỹ Top-k lại vướng `hits_forbidden=yes` vì hệ thống đã nuốt phải chunk 14 ngày).*

**Sau (Chạy Data Pipeline chuẩn làm sạch):**
`q_refund_window,...policy_refund_v4,Yêu cầu được gửi trong vòng 7 ngày làm việc...,yes,no,,3`
*(Dữ liệu bẩn không lọt vào Chroma, `hits_forbidden=no`).*

---

## 5. Cải tiến tiếp theo (40–80 từ)

Với bằng chứng ở mục 4 đã giải quyết xong câu rủi ro chính sách hoàn tiền 14 ngày, nếu có thêm 2 giờ, tôi sẽ tạo kịch bản inject lỗi tiếp theo bằng cách gỡ rule cấu hình `stale_hr_policy_effective_date`. Mục tiêu là cố tình nhét dòng thông tin xin nghỉ phép của năm ngoái (10 ngày) vào câu luận `q_leave_version`. Từ đó lấy điểm Merit Point thông qua việc chứng minh cột `top1_doc_expected` thực sự lấy sai bản hợp đồng làm ảnh hưởng quyền lợi Agent.
