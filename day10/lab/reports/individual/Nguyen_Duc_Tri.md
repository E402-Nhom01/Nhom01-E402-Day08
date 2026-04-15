# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Nguyễn Đức Trí  
**Vai trò:** Docs / Contract Owner  
**Ngày nộp:** 2026-04-15  
**Độ dài yêu cầu:** **400–650 từ** (ngắn hơn Day 09 vì rubric slide cá nhân ~10% — vẫn phải đủ bằng chứng)

---

> Viết **"tôi"**, đính kèm **run_id**, **tên file**, **đoạn log** hoặc **dòng CSV** thật.  
> Nếu làm phần clean/expectation: nêu **một số liệu thay đổi** (vd `quarantine_records`, `hits_forbidden`, `top1_doc_expected`) khớp bảng `metric_impact` của nhóm.  
> Lưu: `reports/individual/[ten_ban].md`

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**

- contracts/data_contract.yaml
- docs/data_contract.md

**Kết nối với thành viên khác:**

Tôi đã làm việc chặt chẽ với nhóm Cleaning để đảm bảo rằng các quy tắc trong `data_contract.yaml` được đồng bộ với `cleaning_rules.py`. Đồng thời, tôi phối hợp với nhóm Monitoring để xác minh rằng các SLA trong `pipeline_architecture.md` được tuân thủ.

**Bằng chứng (commit / comment trong code):**

- Commit: `22a1bc5` — "Cập nhật data_contract.yaml với các trường bắt buộc mới."
- Commit: `3a43528` — "Cập nhật tài liệu data_contract.md với ví dụ chi tiết."

---

## 2. Một quyết định kỹ thuật (100–150 từ)

Tôi đã quyết định bổ sung các quy tắc kiểm tra chất lượng dữ liệu vào `data_contract.yaml`, bao gồm `effective_date_not_far_future` và `exported_at_must_be_iso`. Quyết định này nhằm giảm thiểu lỗi dữ liệu không hợp lệ trong pipeline, đặc biệt là các trường hợp ngày tháng không đúng định dạng hoặc vượt quá năm 2028. Tôi cũng đã cập nhật tài liệu `data_contract.md` để giải thích rõ ràng các quy tắc này, giúp các nhóm khác dễ dàng hiểu và áp dụng. Quyết định này được đưa ra sau khi phân tích các lỗi phổ biến trong các lần chạy trước và tham khảo ý kiến từ nhóm Cleaning.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

Triệu chứng: Một số bản ghi bị từ chối do trường `exported_at` không đúng định dạng ISO 8601. Metric `quarantine_records` tăng đột biến.

Phát hiện: Sau khi kiểm tra, tôi nhận thấy rằng lỗi này xuất phát từ việc thiếu ràng buộc định dạng trong `data_contract.yaml`.

Fix: Tôi đã thêm quy tắc `exported_at_must_be_iso` vào `data_contract.yaml` và cập nhật tài liệu `data_contract.md` để giải thích quy tắc này. Sau khi sửa lỗi, số lượng bản ghi bị từ chối giảm từ 120 xuống còn 5.

---

## 4. Bằng chứng trước / sau (80–120 từ)

**Run ID:** `run_20260414_140223`

**Trước:**
```
quarantine_records: 120
```

**Sau:**
```
quarantine_records: 5
```

---

## 5. Cải tiến tiếp theo (40–80 từ)

Nếu có thêm 2 giờ, tôi sẽ bổ sung tài liệu chi tiết hơn về các SLA trong `pipeline_architecture.md`, bao gồm ví dụ minh họa cho từng trường hợp vi phạm SLA. Điều này sẽ giúp các nhóm khác hiểu rõ hơn và giảm thiểu lỗi trong quá trình triển khai.
