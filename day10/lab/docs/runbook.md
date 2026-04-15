# Runbook — Lab Day 10 (incident tối giản)

---

## Symptom

- User / agent trả lời **sai cửa sổ hoàn tiền** ("14 ngày" thay vì 7 ngày), hoặc **sai số ngày phép HR** ("10 ngày" thay vì 12 ngày chính sách 2026).
- Pipeline run báo `freshness_check=FAIL` — snapshot data cũ hơn SLA.
- Log có dòng `expectation[...] FAIL (halt)` → pipeline dừng (`exit=2`) không embed.

---

## Detection

| Metric                                            | Nguồn                                                                   | Ý nghĩa                                                                                                               |
| ------------------------------------------------- | ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `freshness_check`                                 | `monitoring/freshness_check.py` đọc `latest_exported_at` trong manifest | FAIL nếu `age_hours > sla_hours` (mặc định 24h)                                                                       |
| `expectation[...] FAIL (halt)`                    | `quality/expectations.py`                                               | Ngăn publish data xấu (refund stale 14 ngày, HR 10 ngày, effective_date non-ISO, exported_at non-ISO, HR 2026 bị mất) |
| `hits_forbidden=yes` trong `artifacts/eval/*.csv` | `eval_retrieval.py` quét toàn bộ top-k                                  | Top-1 có thể đúng nhưng context vẫn còn chunk stale — observability thật                                              |
| `quarantine_records` tăng bất thường              | manifest JSON                                                           | Nguồn raw đang bẩn hơn baseline → cần kiểm ingest job                                                                 |

---

## Diagnosis

Thứ tự theo slide Day 10: **Freshness / version → Volume & errors → Schema & contract → Lineage / run_id → mới đến model/prompt**.

| Bước | Việc làm                                                                                                                                                 | Kết quả mong đợi                                                                                                                       |
| ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | `cat artifacts/manifests/manifest_<run_id>.json` — kiểm `latest_exported_at`, `raw_records`, `cleaned_records`, `quarantine_records`, `skipped_validate` | Nếu `skipped_validate=true` → có người chạy `--skip-validate`, rollback ngay                                                           |
| 2    | `python etl_pipeline.py freshness --manifest artifacts/manifests/manifest_<run_id>.json`                                                                 | PASS = data tươi; WARN = sắp hết hạn; FAIL = đã stale → ngừng trả lời user / treat retrieval kết quả là cảnh báo                       |
| 3    | Mở `artifacts/quarantine/quarantine_<run_id>.csv` — xem cột `reason`                                                                                     | Xác định failure mode (unknown_doc_id / mojibake_detected / stale_hr_policy / invalid_exported_at_format / effective_date_far_future…) |
| 4    | Đối chiếu `artifacts/cleaned/cleaned_<run_id>.csv` với source of truth `data/docs/*.txt`                                                                 | Nếu chunk_text khác file canonical → export upstream đã drift                                                                          |
| 5    | `python eval_retrieval.py --out /tmp/eval_check.csv` → xem `hits_forbidden`                                                                              | Nếu = yes ở câu nào → context vẫn dính chunk stale dù top-1 "nhìn đúng"                                                                |
| 6    | `grep run_id artifacts/logs/run_<id>.log` — kiểm đầy đủ 8 expectation line                                                                               | Đảm bảo không bị skip; nếu halt → đọc `detail` để biết dòng nào fail                                                                   |

---

## Mitigation

- **Rerun pipeline clean** sau khi fix upstream: `python etl_pipeline.py run --run-id rerun-<tag>` — chunk_id stable nên upsert an toàn, prune xoá id lạc hậu.
- **Rollback embed**: vì index là snapshot publish, chạy lại pipeline với raw đúng version → collection tự sync (không cần rollback thủ công).
- **Tạm banner "data stale"**: nếu freshness FAIL không fix kịp, agent layer (Day 09) nên thêm disclaimer "data last refreshed X hours ago" vào response — gap hiện tại.
- **Không dùng `--skip-validate` trong prod**: chỉ dành cho demo Sprint 3 inject có chủ đích.

### Ví dụ freshness output

```bash
$ python etl_pipeline.py freshness --manifest artifacts/manifests/manifest_fix-good.json
FAIL {"latest_exported_at": "2026-04-10T08:00:00", "age_hours": 121.32, "sla_hours": 24.0, "reason": "freshness_sla_exceeded"}
```

**Giải thích:** data mẫu xuất 2026-04-10, hôm nay 2026-04-15 → 121h > 24h SLA → FAIL. Lý do nhóm không che FAIL này (không tăng SLA lên 200h): muốn giữ signal thật để reviewer thấy freshness hoạt động đúng nghiệp vụ. PASS kỳ vọng sau khi refresh raw CSV với `exported_at` mới (< 24h so với giờ chạy).

---

## Prevention

- **Thêm expectation**: E7 `hr_leave_has_current_2026_version` (positive invariant — halt nếu mất bản mới), E8 `exported_at_is_iso_datetime` (defense-in-depth cho R8). Nếu sau này có version HR 2027 → cập nhật cutoff ở `contracts/data_contract.yaml` → rule sẽ đọc từ đó (move hard-code ra — planned).
- **Alert channel**: đang đặt `__TODO__` trong yaml → sẽ nối Slack/PagerDuty nếu on-call Day 11.
- **Owner rõ ràng**: 4 owner nhóm trong `group_report.md` — có người chịu trách nhiệm rerun khi FAIL.
- **Guardrail Day 11**: thêm LLM-judge trên eval để catch drift semantic; thêm measurement publish-boundary (`run_timestamp - embed_done`) để bắt lag giữa ingest và publish.
