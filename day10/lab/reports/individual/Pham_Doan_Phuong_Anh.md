**Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability**

**Họ và tên:** Pham Doan Phuong Anh
**Vai trò:** Ingestion / Raw Owner
**Ngày nộp:** 2026-04-15

---

### 1. Tôi phụ trách phần nào? (≈100 từ)

Tôi phụ trách phần **ingestion (raw data)**, cụ thể là quản lý file nguồn `data/raw/policy_export_dirty.csv` và đảm bảo pipeline có thể load dữ liệu ổn định thông qua module `etl_pipeline.py` (hàm `load_raw_csv`). Tôi chịu trách nhiệm đảm bảo dữ liệu đầu vào phản ánh đúng các tình huống thực tế như duplicate, format ngày sai, hoặc dữ liệu stale để phục vụ các bước cleaning và expectation phía sau.

Tôi phối hợp chặt với bạn Tien (Cleaning Owner) để đảm bảo schema raw phù hợp cho cleaning rules, và với bạn Dung (Monitoring) để đảm bảo trường `exported_at` có thể dùng cho freshness check.

**Bằng chứng:**

* File: `data/raw/policy_export_dirty.csv`
* Run sử dụng: `run_id=fix-good`, `inject-bad`, `inject-rules`
* Log load thành công:

```
INFO load_raw_csv: loaded 10 records from data/raw/policy_export_dirty.csv
```

---

### 2. Một quyết định kỹ thuật (≈120 từ)

Một quyết định quan trọng của tôi là **giữ raw data “bẩn có chủ đích” thay vì làm sạch sớm ở ingestion**. Cụ thể, tôi không normalize hoặc validate các trường như `exported_at`, `effective_date` ngay từ bước load, mà giữ nguyên để downstream xử lý.

Lý do là để đảm bảo pipeline có **separation of concerns**: ingestion chỉ chịu trách nhiệm load, còn cleaning và expectation chịu trách nhiệm validate. Điều này giúp test rõ ràng impact của từng rule (ví dụ R8 về ISO datetime) và dễ debug hơn khi có anomaly.

Ngoài ra, tôi đảm bảo ingestion **idempotent**: cùng một file CSV → luôn load ra cùng số record và thứ tự, không thay đổi nội dung, giúp các bước sau (hash chunk_id, embed) hoạt động ổn định.

---

### 3. Một lỗi hoặc anomaly đã xử lý (≈120 từ)

Một anomaly tôi gặp là **format ngày `exported_at` không đồng nhất**, ví dụ có dòng:

```
Thursday 10 April 2026
```

Triệu chứng ban đầu là bước `freshness_check` bị lỗi parse datetime hoặc cho kết quả sai.

Metric phát hiện là:

```
freshness_check: FAIL (invalid datetime format)
```

Nguyên nhân là ingestion vẫn load string này bình thường, nhưng downstream không parse được.

Cách xử lý: tôi giữ nguyên raw (không sửa tại ingestion), nhưng **phối hợp với cleaning** để đảm bảo rule R8 (`exported_at_must_be_iso`) sẽ quarantine record này trước khi tới monitoring.

Sau fix, log cho thấy:

```
quarantine_records +=1 (reason=invalid_exported_at_format)
```

và freshness check không còn crash.

---

### 4. Bằng chứng trước / sau (≈90 từ)

**Run:**

* Before: `run_id=inject-bad`
* After: `run_id=fix-good`

Trích từ `before_after_eval.csv`:

```
inject-bad,q_refund_window,hits_forbidden,yes
fix-good,q_refund_window,hits_forbidden,no
```

Giải thích: ingestion giữ nguyên dữ liệu refund “14 ngày”, nên khi skip cleaning (`--no-refund-fix`) thì retrieval trả về context sai (hits_forbidden=yes). Sau khi pipeline chạy đầy đủ (fix-good), dữ liệu được sửa thành “7 ngày” và không còn context sai.

Điều này chứng minh ingestion đã cung cấp đúng raw để downstream xử lý và quan sát được impact.

---

### 5. Cải tiến tiếp theo (≈60 từ)

Nếu có thêm 2 giờ, tôi sẽ thêm **schema validation nhẹ ở ingestion (non-blocking)**, ví dụ check số cột hoặc null cơ bản, nhưng chỉ log warning thay vì halt. Điều này giúp phát hiện sớm lỗi format file (CSV hỏng, thiếu cột) mà vẫn giữ nguyên triết lý không làm sạch dữ liệu ở bước ingestion.
