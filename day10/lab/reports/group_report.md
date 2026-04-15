# Báo Cáo Nhóm — Lab Day 10: Data Pipeline & Data Observability

**Tên nhóm:** ___________
**Thành viên:**
| Tên | Vai trò (Day 10) | Email |
|-----|------------------|-------|
| ___ | Ingestion / Raw Owner | ___ |
| ___ | Cleaning & Quality Owner | ___ |
| Huynh Thai Bao | Embed & Idempotency Owner | ___ |
| Truong Minh Tien | Monitoring / Docs Owner | marcuschill1823@gmail.com |

**Ngày nộp:** 2026-04-15
**Repo:** ___________
**Độ dài khuyến nghị:** 600–1000 từ

---

> **Nộp tại:** `reports/group_report.md`
> **Deadline commit:** xem `SCORING.md`.
> Run_id chính của nhóm: `fix-good` (publish baseline), `inject-bad` (Sprint 3 corruption), `inject-rules` (Sp4.1 chứng minh R7/R8/R9).

---

## 1. Pipeline tổng quan (150–200 từ)

**Tóm tắt luồng:** `ingest (CSV raw) → clean (allowlist + normalize + quarantine) → expectation suite (warn/halt) → embed upsert + prune (Chroma persistent) → manifest JSON → freshness check`. Nguồn raw là CSV mẫu `data/raw/policy_export_dirty.csv` (10 record mô phỏng export bẩn từ hệ nguồn: duplicate, doc_id lạ, ngày không ISO, conflict version HR, refund stale 14 ngày). `run_id` được truyền qua `--run-id` hoặc auto sinh từ UTC timestamp, nhúng vào mọi artifact (`artifacts/{logs,cleaned,quarantine,manifests}/*_<run_id>.{csv,json,log}`) và metadata của mỗi chunk trong Chroma để trace lineage. Manifest có: `run_id`, `run_timestamp`, `raw_records`, `cleaned_records`, `quarantine_records`, `latest_exported_at`, flag `no_refund_fix` / `skipped_validate`, path Chroma. Pipeline idempotent: rerun cùng raw → cùng `chunk_id` (hash stable) → upsert không phình vector; đồng thời prune id cũ không còn trong cleaned để giữ index = snapshot publish hiện tại.

**Lệnh chạy một dòng (copy từ README):**

```bash
python etl_pipeline.py run --run-id fix-good --raw data/raw/policy_export_dirty.csv
```

---

## 2. Cleaning & expectation (150–200 từ)

Baseline có 6 rule (allowlist doc_id, parse effective_date, quarantine HR < 2026, dedupe chunk_text, fix stale refund 14→7, quarantine text rỗng) và 6 expectation. Nhóm thêm **3 rule** + **2 expectation** (đều ở `transform/cleaning_rules.py` và `quality/expectations.py`):

### 2a. Bảng metric_impact (bắt buộc — chống trivial)

| Rule / Expectation mới | Trước (baseline `policy_export_dirty.csv`) | Sau / khi inject (`policy_export_inject_rules.csv`) | Chứng cứ |
|---|---|---|---|
| R7 `unicode_normalize_strip_zero_width` → quarantine `mojibake_detected` nếu có `\ufffd` | 0 quarantine | **+1** quarantine (row 1 `hoàn ti�n 7 ngày`) | `artifacts/quarantine/quarantine_inject-rules.csv` row 2 |
| R8 `exported_at_must_be_iso` → quarantine `invalid_exported_at_format` | 0 quarantine | **+1** quarantine (row 2 `Thursday 10 April 2026`) | `quarantine_inject-rules.csv` row 3 |
| R9 `effective_date_not_far_future` (cutoff 2028-01-01) → quarantine `effective_date_far_future` | 0 quarantine | **+1** quarantine (row 3 `effective_date=2099-01-01`) | `quarantine_inject-rules.csv` row 4 |
| E7 `hr_leave_has_current_2026_version` (halt) — positive invariant | `current_hr_chunks=1` pass | `current_hr_chunks=1` pass; **halt nếu bị inject** bỏ HR 2026 (ngăn publish sau khi quarantine quá tay) | log run `sprint2-baseline`, `inject-rules` |
| E8 `exported_at_is_iso_datetime` (halt) — defense-in-depth cho R8 | `non_iso_exported_at=0` pass | `non_iso_exported_at=0` pass (R8 quarantine trước nên E8 không thấy) | log run `inject-rules` |

**Chi tiết 3 rule mới:** R7 dùng `unicodedata.NFKC` + strip BOM/ZWSP/NBSP, chỉ quarantine khi text có U+FFFD (mojibake không tự phục hồi). R8 regex ISO 8601 datetime — chặn sớm để `monitoring/freshness_check.py` parse `latest_exported_at` không crash. R9 cutoff `2028-01-01` chống typo năm (2099) làm lệch thứ tự version.

**Ví dụ 1 lần expectation fail:** Sprint 3 chạy `--no-refund-fix` → `expectation[refund_no_stale_14d_window] FAIL (halt) :: violations=1`; cách xử lý: dùng `--skip-validate` để demo có chủ đích (dòng log `WARN: expectation failed but --skip-validate → tiếp tục embed`), embed vào `day10_kb` để eval chứng minh `hits_forbidden=yes`.

---

## 3. Before / after ảnh hưởng retrieval hoặc agent (200–250 từ)

**Kịch bản inject (Sprint 3):** Chạy pipeline với `--no-refund-fix --skip-validate` (run_id = `inject-bad`) — bỏ rule replace `14→7 ngày làm việc` trong `policy_refund_v4`, đồng thời bỏ qua expectation halt để vẫn embed data xấu vào Chroma. Sau đó chạy `eval_retrieval.py` lưu `after_inject_bad.csv`. Chạy lại pipeline chuẩn (`fix-good`) + eval → `before_after_eval.csv`.

**Kết quả định lượng:**

| Câu hỏi | Metric | Inject-bad | Fix-good | Delta |
|---|---|---|---|---|
| `q_refund_window` | `hits_forbidden` | **yes** (top-k kéo chunk "14 ngày làm việc") | **no** (chunk đã fix thành "7 ngày" + marker `[cleaned: stale_refund_window]`) | ✅ Chứng minh retrieval tệ trước fix |
| `q_refund_window` | `contains_expected` | yes | yes | top-1 "nhìn đúng" ở cả 2 — chỉ top-k mới phát hiện |
| `q_p1_sla` | — | pass | pass | Không đổi (không inject) |
| `q_lockout` | — | pass | pass | Không đổi |
| `q_leave_version` | `top1_doc_expected` | yes (HR 2026) | yes | **Chưa có impact** — kịch bản inject không chạm HR (xem hạn chế) |

Nguồn: `artifacts/eval/after_inject_bad.csv` (row 2) vs `artifacts/eval/before_after_eval.csv` (row 2). Đây đúng tinh thần observability slide Day 10: "đáp án đúng ≠ context đúng" — phải quét toàn bộ top-k, không chỉ top-1. Chi tiết thêm trong `docs/quality_report.md`.

---

## 4. Freshness & monitoring (100–150 từ)

**SLA chọn:** 24h (biến env `FRESHNESS_SLA_HOURS`), đo tại boundary **ingest** — `monitoring/freshness_check.py` đọc `latest_exported_at` trong manifest (= `max(exported_at)` từ cleaned CSV). Kết quả trên data mẫu: `freshness_check=FAIL, age_hours=121, reason=freshness_sla_exceeded` — **FAIL hợp lý** vì CSV mẫu xuất ngày `2026-04-10`, hôm nay 2026-04-15. Semantics: PASS = snapshot còn tươi; WARN (chưa dùng) = gần cutoff; FAIL = on-call phải kiểm ingest job trước khi agent trả lời user. Gap: chưa đo boundary **publish** (thời điểm upsert Chroma) — ghi trong `docs/runbook.md` như việc cần bổ sung (bonus Distinction +1).

---

## 5. Liên hệ Day 09 (50–100 từ)

Chroma collection `day10_kb` tách riêng khỏi Day 09 (`day09_kb` / mặc định Day 08) để cô lập snapshot publish của lab Day 10 — agent multi-agent có thể switch collection bằng env `CHROMA_COLLECTION`. Về mặt dữ liệu, 4 doc_id (`policy_refund_v4`, `sla_p1_2026`, `it_helpdesk_faq`, `hr_leave_policy`) kế thừa nguyên văn từ `data/docs/*.txt` Day 09; pipeline Day 10 thêm tầng validate/quarantine/freshness trước embed — nếu Day 09 agent trỏ vào `day10_kb`, câu trả lời refund/HR sẽ đúng version vì đã lọc stale ở data layer.

---

## 6. Peer review (slide phần E · 2/4 — 3 câu)

| Câu hỏi | Trả lời + chứng cứ |
|---|---|
| **Rerun 2 lần có duplicate vector không?** | Không. `chunk_id` hash stable từ `(doc_id, chunk_text, seq)`; `col.upsert(ids=...)` theo chunk_id + prune id không còn trong cleaned. Log 2 lần chạy `fix-good` liên tiếp: `embed_prune_removed=0, embed_upsert count=6` (không phình). |
| **Freshness đo ở bước nào — ingest hay publish?** | Ingest (qua `latest_exported_at` = max `exported_at` cleaned). Publish boundary là gap đã ghi trong `docs/runbook.md` — cần đo thêm `run_timestamp - embed_done_at` nếu muốn full. |
| **Record bị flag đi đâu — quarantine hay vẫn embed?** | Quarantine — file `artifacts/quarantine/quarantine_<run_id>.csv`, KHÔNG embed. Chỉ embed nếu `--skip-validate` override (demo Sprint 3, ghi rõ trong manifest field `skipped_validate: true`). |

---

## 7. Rủi ro còn lại & việc chưa làm

- **Merit `q_leave_version`:** chưa có evidence inject cho HR versioning — cần kịch bản tắt rule `stale_hr_policy_effective_date` để cả 10 ngày + 12 ngày cùng vào retrieval, rồi so sánh `hits_forbidden`.
- **Publish-boundary freshness:** mới đo ở ingest; thêm metric `run_timestamp - max(cleaned_exported_at)` để bắt trường hợp ingest tươi nhưng publish chậm.
- **GE/pydantic:** expectation hiện tại là dataclass tự viết — nếu tích hợp Great Expectations sẽ đạt bonus Distinction (+2).
- **Grading JSONL:** `data/grading_questions.json` GV public sau 17:00 — sẽ chạy `python grading_run.py --out artifacts/eval/grading_run.jsonl` khi có file.
- **Manifest Windows path:** run trước của đồng đội có `raw_path` backslash (`data\\raw\\...`); run mới trên Mac có path forward slash + absolute. Không ảnh hưởng freshness, ghi nhận để reviewer biết.
