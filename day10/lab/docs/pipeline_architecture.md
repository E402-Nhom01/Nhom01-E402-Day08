# Kiến trúc pipeline — Lab Day 10

**Nhóm:** ****\_\_\_****
**Cập nhật:** 2026-04-15

---

## 1. Sơ đồ luồng

```
 ┌──────────────────┐    ┌───────────────────┐    ┌────────────────────┐    ┌─────────────────┐    ┌──────────────────┐
 │ raw export (CSV) │ -> │ clean + quarantine │ -> │ expectation suite  │ -> │ embed (Chroma)  │ -> │ serving Day 08/09│
 │ policy_export_*  │    │ transform/         │    │ quality/           │    │ upsert+prune    │    │ agent retrieval   │
 │ (10 record mẫu)  │    │ cleaning_rules.py  │    │ expectations.py    │    │ day10_kb        │    │                   │
 └────────┬─────────┘    └─────────┬──────────┘    └─────────┬──────────┘    └───────┬─────────┘    └──────────────────┘
          │                        │                         │                       │
          │                        ▼                         │                       ▼
          │            artifacts/quarantine/*.csv            │              artifacts/manifests/*.json
          │            (reason: mojibake_detected,           │              (run_id, *_records,
          │             unknown_doc_id, stale_hr,            │               latest_exported_at)
          │             invalid_exported_at_format, …)       │                       │
          │                                                  │                       ▼
          ▼                                                  ▼            monitoring/freshness_check.py
   artifacts/logs/                              halt if expectation FAIL   (sla_hours=24, boundary=ingest)
   run_<id>.log                                 (override: --skip-validate)
```

**Lineage:** mỗi run gắn `run_id` (UTC timestamp hoặc `--run-id`) vào log, cleaned CSV, quarantine CSV, manifest JSON, và metadata mỗi chunk trong Chroma — có thể trace ngược từ chunk → run → raw record.

---

## 2. Ranh giới trách nhiệm

| Thành phần             | Input                                     | Output                                                          | Owner nhóm                |
| ---------------------- | ----------------------------------------- | --------------------------------------------------------------- | ------------------------- |
| Ingest                 | `data/raw/*.csv` (DictReader UTF-8)       | `List[Dict]` thô                                                | Ingestion Owner           |
| Transform (clean)      | raw rows                                  | `cleaned`, `quarantine` (tuple); 9 rule — 6 baseline + R7/R8/R9 | Cleaning & Quality Owner  |
| Quality (expectations) | cleaned rows                              | 8 `ExpectationResult` + `should_halt` bool                      | Cleaning & Quality Owner  |
| Embed                  | `cleaned_<run>.csv`                       | Chroma `day10_kb` (upsert theo `chunk_id`, prune id lạc hậu)    | Embed & Idempotency Owner |
| Monitor                | `artifacts/manifests/manifest_<run>.json` | `(status, detail)` PASS / WARN / FAIL                           | Monitoring / Docs Owner   |

---

## 3. Idempotency & rerun

- `chunk_id = f"{doc_id}_{seq}_{sha256(doc_id|text|seq)[:16]}"` — hash stable qua run, không đổi nếu raw giống nhau.
- `col.upsert(ids=[chunk_id], ...)` thay vì `add` → rerun cùng raw không phình vector.
- Prune: `col.delete(ids=prev_ids - current_ids)` sau upsert → **index = snapshot publish**, không còn chunk cũ lạc hậu (tránh "mồi cũ" trong top-k).
- Kiểm chứng: 2 lần rerun `fix-good` liên tiếp → log đầu `embed_upsert count=6`, log sau `embed_prune_removed=0, embed_upsert count=6` (collection không tăng).

---

## 4. Liên hệ Day 09

Pipeline Day 10 dùng **cùng 4 tài liệu canonical** `data/docs/*.txt` với Day 09 (policy_refund_v4, sla_p1_2026, it_helpdesk_faq, hr_leave_policy), nhưng embed vào **collection riêng** `day10_kb` (env `CHROMA_COLLECTION`, path `CHROMA_DB_PATH`). Day 09 agent có thể switch sang `day10_kb` bằng cách đổi env — khi đó retrieval sẽ dùng snapshot đã qua validate/quarantine của Day 10 → câu trả lời version-correct (refund 7 ngày, HR 12 ngày phép 2026).

---

## 5. Rủi ro đã biết

- **Freshness chỉ đo boundary ingest** (`latest_exported_at`): không bắt trường hợp ingest tươi nhưng embed chậm (publish-boundary gap).
- **Expectation halt cứng**: không phân biệt test-env vs prod, không có feature-flag — nếu raw tạm sai format sẽ chặn cả pipeline.
- **Không phát hiện drift semantic**: rule chỉ kiểm format/version; nếu chunk_text bị đổi nghĩa (LLM rewrite sai) → pipeline không báo.
- **Chroma persistent path là filesystem local**: multi-writer race nếu chạy song song 2 pipeline cùng collection.
- **Cutoff hard-code**: `FAR_FUTURE_CUTOFF = "2028-01-01"` và `hr_leave_min_effective_date = "2026-01-01"` chưa đọc từ contract — mong muốn move sang env/YAML để versioning động (merit Distinction).
