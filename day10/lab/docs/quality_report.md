# Quality report — Lab Day 10 (nhóm)

**run_id (fix-good):** `fix-good` — 2026-04-15T08:53:42Z
**run_id (inject-bad):** `inject-bad` — 2026-04-15T08:52:19Z
**Ngày:** 2026-04-15

---

## 1. Tóm tắt số liệu

| Chỉ số | Trước (inject-bad) | Sau (fix-good) | Ghi chú |
|--------|-------|-----|---------|
| raw_records | 10 | 10 | cùng file raw `data/raw/policy_export_dirty.csv` |
| cleaned_records | 6 | 6 | lượng publish không đổi, khác biệt nằm ở **nội dung chunk refund** |
| quarantine_records | 4 | 4 | cùng 4 reason: duplicate / missing_effective_date / stale_hr_policy / unknown_doc_id |
| Expectation halt? | **Có** — `refund_no_stale_14d_window` fail (bỏ qua vì `--skip-validate`) | **Không** — 8/8 pass | halt đúng mục tiêu: chặn publish nếu không chạy skip-validate |

---

## 2. Before / after retrieval (bắt buộc)

Nguồn: `artifacts/eval/before_after_eval.csv` (fix-good) và `artifacts/eval/after_inject_bad.csv` (inject-bad).

**Câu hỏi then chốt: `q_refund_window`** — "Khách hàng có bao nhiêu ngày để yêu cầu hoàn tiền kể từ khi xác nhận đơn?"

**Trước (inject-bad, không fix 14→7):**
```
top1_doc_id=policy_refund_v4
top1_preview=Yêu cầu được gửi trong vòng 7 ngày làm việc kể từ thời điểm xác nhận đơn hàng.
contains_expected=yes
hits_forbidden=YES   ← top-k chứa chunk stale "14 ngày làm việc" (bản sync cũ policy-v3)
top_k_used=3
```

**Sau (fix-good, rule refund fix active):**
```
top1_doc_id=policy_refund_v4
top1_preview=Yêu cầu được gửi trong vòng 7 ngày làm việc kể từ thời điểm xác nhận đơn hàng.
contains_expected=yes
hits_forbidden=no    ← top-k sạch, chunk stale đã bị cleaning thay "14→7" + marker [cleaned]
top_k_used=3
```

**Nhận xét:** top1 "nhìn đúng" ở cả 2 run, nhưng **toàn bộ top-k** mới phản ánh observability thật. Trước fix, agent vẫn có thể đọc chunk "14 ngày làm việc" từ context và trả lời sai tuỳ prompt. Sau fix, rule `apply_refund_window_fix` replace `14 ngày làm việc → 7 ngày làm việc [cleaned: stale_refund_window]` nên top-k sạch hoàn toàn.

**Merit (khuyến nghị) — `q_leave_version`:**

**Trước:** `top1_doc_id=hr_leave_policy, top1_preview="...12 ngày phép năm theo chính sách 2026", top1_doc_expected=yes, hits_forbidden=no`
**Sau:** giống trước.

Không show được impact trên kịch bản inject hiện tại (inject chỉ bỏ refund fix, không chạm HR). Bản HR cũ 2025 (10 ngày) đã bị quarantine ở cả 2 run nhờ rule `stale_hr_policy_effective_date` → collection không chứa vector cũ để kéo vào top-k. Để show merit thật, cần kịch bản inject bỏ rule HR stale — nhóm note lại như hạn chế (mục 5).

---

## 3. Freshness & monitor

```
freshness_check=FAIL
{"latest_exported_at": "2026-04-10T08:00:00", "age_hours": 120.7, "sla_hours": 24.0,
 "reason": "freshness_sla_exceeded"}
```

**SLA chọn:** 24h (mặc định `FRESHNESS_SLA_HOURS=24`). Dữ liệu mẫu export ngày 2026-04-10, hôm nay 2026-04-15 → 120h > 24h → **FAIL đúng kỳ vọng**. Trong môi trường thật, FAIL là tín hiệu để on-call kiểm tra ingest job trước khi agent trả lời user bằng snapshot cũ (nguyên tắc debug Day 10: freshness đứng đầu).

---

## 4. Corruption inject (Sprint 3)

**Cách inject:** chạy pipeline với 2 flag `--no-refund-fix --skip-validate`:
- `--no-refund-fix` → bỏ rule replace `14→7 ngày làm việc` trong `policy_refund_v4`.
- `--skip-validate` → bỏ qua expectation halt (`refund_no_stale_14d_window`) để vẫn embed data xấu vào Chroma.

Lệnh:
```bash
python etl_pipeline.py run --run-id inject-bad --no-refund-fix --skip-validate
python eval_retrieval.py --out artifacts/eval/after_inject_bad.csv
```

**Cách phát hiện:** cột `hits_forbidden=yes` trong `after_inject_bad.csv` cho câu `q_refund_window` — quét **toàn bộ top-k** (không chỉ top-1), bắt đúng chunk stale còn sót trong vector store dù top-1 trả lời "đúng". Đây là observability tinh thần slide Day 10: "đáp án đúng ≠ context đúng".

---

## 5. Hạn chế & việc chưa làm

- Merit `q_leave_version`: chưa có evidence inject bỏ rule HR stale — cần run thêm 1 kịch bản cố ý comment out block `stale_hr_policy_effective_date` để show cả 2 bản (10 ngày + 12 ngày) cùng vào retrieval.
- Manifest đồng đội chạy trên Windows nên `raw_path`/`cleaned_csv` dùng `\\` — không ảnh hưởng freshness check, nhưng nếu chấm chéo OS khác cần chú ý.
- Log run `inject-bad` / `fix-good` không lưu lại ở máy chạy eval (logs ở máy đồng đội) — bổ sung bằng cách rerun trên máy nào cũng được (pipeline idempotent, chunk_id stable).
