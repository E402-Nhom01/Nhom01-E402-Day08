# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Trương Minh Tiền
**Vai trò trong nhóm:** Supervisor Owner
**Ngày nộp:** 14/04/2026
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào?

**Module/file tôi chịu trách nhiệm:**
- File chính: `graph.py` — Supervisor Orchestrator (Sprint 1)
- Functions tôi implement:
  - `AgentState` (TypedDict shared state) và `make_initial_state(task)` — khởi tạo state kèm `run_id` unique.
  - `supervisor_node(state)` — phân tích task, quyết định route và bật flag `needs_tool`, `risk_high`.
  - `route_decision(state)` — conditional edge trả về tên worker kế tiếp.
  - `human_review_node(state)` — HITL placeholder: gắn `hitl_triggered=True`, log cảnh báo, rồi route về retrieval để vẫn có evidence.
  - `build_graph()` + `run_graph(task)` — orchestrator Python thuần (Option A trong README): `supervisor → route → [retrieval | policy_tool | human_review] → synthesis → END`.
  - `save_trace(state)` — ghi JSON trace vào `artifacts/traces/`.

**Cách công việc của tôi kết nối với phần của thành viên khác:**
Tôi định nghĩa `AgentState` và quy ước các field (`supervisor_route`, `route_reason`, `retrieved_chunks`, `policy_result`, `mcp_tools_used`, `hitl_triggered`). Các worker mà Phương Anh (policy_tool) và nhóm MCP/synthesis phát triển đều đọc/ghi vào state thông qua đúng các key này, không truyền tham số riêng. Nhờ contract qua state, khi worker cập nhật I/O (ví dụ policy_tool thêm `mcp_tools_used`) thì `eval_trace.py` của Trí lấy được ngay, không cần sửa graph.

**Bằng chứng:** commit branch `main`, file `graph.py` dòng 24–74 (`AgentState`, `make_initial_state`), 81–137 (`supervisor_node`), 247–280 (build_graph).

---

## 2. Tôi đã ra một quyết định kỹ thuật gì?

**Quyết định:** Thêm một lớp "exception-signal guard" trong supervisor_node, chỉ route sang `policy_tool_worker` khi task có **cả** policy keyword **và** tín hiệu exception/escalation thực sự (Flash Sale, license, Level 2/3, contractor, emergency…). Các câu hỏi chỉ chứa policy keyword nhưng là fact lookup (ví dụ "hoàn tiền bao nhiêu ngày?") sẽ được route về `retrieval_worker`.

**Các lựa chọn thay thế:**
1. Bất cứ câu nào chứa "hoàn tiền/refund/access" → policy_tool (bản đầu của tôi). Đơn giản nhưng quá aggressive, làm route sai các câu tra cứu.
2. Gọi LLM để classify 3 route. Chính xác hơn ở biên nhưng thêm ~800ms/câu, không thể giải thích rõ `route_reason`.
3. Guard bằng exception signals (đã chọn). Thêm ~1 microsecond, `route_reason` log rõ signals match.

**Lý do chọn:** giữ được tính minh bạch của rule-based (xem `route_reason` trong trace là hiểu ngay), tránh false-positive quan trọng nhất (q02 fact query), không tăng latency. Nếu Sprint 4 cần bắt câu mơ hồ hơn mới bổ sung LLM ở nhánh fallback.

**Trade-off đã chấp nhận:** guard có thể miss các câu policy được diễn đạt không chuẩn (không có từ "flash sale/license/level 2/3"). Với bộ test 15 câu hiện tại chưa gặp case này; nếu xuất hiện sẽ bổ sung signals chứ không thay cơ chế.

**Bằng chứng từ code:**

```python
policy_hits = [kw for kw in policy_kw if kw in task]
exception_hits = [s for s in exception_signals if s in task]

if policy_hits and exception_hits:
    route = "policy_tool_worker"
    route_reason = f"policy keyword {policy_hits} + exception signal {exception_hits}"
elif policy_hits:
    route = "retrieval_worker"
    route_reason = f"policy keyword {policy_hits} but no exception signal → retrieval fact"
```

Trace q02 trước fix: `route=policy_tool_worker`. Sau fix: `route=retrieval_worker, reason="policy keyword ['hoàn tiền'] but no exception signal → retrieval fact"`. Route accuracy scorecard nhảy từ 14/15 (93%) lên 15/15 (100%) trên test_questions.json.

---

## 3. Tôi đã sửa một lỗi gì?

**Lỗi:** Trace file bị **ghi đè** — 4 câu test khác nhau trong 1 lần chạy cùng ra đúng 1 file JSON duy nhất.

**Symptom:** Chạy `python graph.py` với 4 queries, folder `artifacts/traces/` chỉ có 1 file `run_20260414_124513.json` chứa state của query cuối, 3 query trước bị mất trace. Trí phát hiện khi đọc `analyze_traces()` thấy `total_traces` không khớp số câu đã chạy.

**Root cause:** Trong `make_initial_state`, `run_id` dùng format `'%Y%m%d_%H%M%S'` — độ phân giải chỉ tới **giây**. Graph chạy placeholder workers nên mỗi query xong trong <1s → 4 query liên tiếp cùng giây sinh cùng `run_id` → `save_trace` ghi cùng path.

**Cách sửa:** Đổi format sang `'%Y%m%d_%H%M%S_%f'` để thêm microsecond (6 số cuối). 1 dòng diff:

```python
# Trước
"run_id": f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
# Sau
"run_id": f"run_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
```

**Bằng chứng trước/sau:**

- Trước: 4 query → output log in 4 lần `Trace saved → ./artifacts/traces/run_20260414_124513.json` (same path).
- Sau: `run_20260414_140223_920262.json`, `...921167.json`, `...921356.json`, `...921517.json` — 4 file riêng biệt, microsecond đủ phân biệt.

Bug này không trigger khi workers thật chạy (mỗi query ~10s), nhưng vẫn fix để tránh race condition khi chạy song song sau này.

---

## 4. Tôi tự đánh giá đóng góp của mình

**Tôi làm tốt nhất ở điểm nào?** Thiết kế `AgentState` bao phủ đủ trường cho cả 4 sprint ngay từ đầu (supervisor flags, worker outputs, MCP usage, HITL, trace metadata). Workers sau này cắm vào state không phải đề nghị thêm field lần nào — giảm rework cho cả nhóm.

**Tôi làm chưa tốt ở điểm nào?** Routing rule đầu tiên của tôi quá greedy với keyword "hoàn tiền", sau đó tôi mới nhìn test_questions.json và phát hiện lệch. Nên đọc kỹ dataset trước khi code routing thay vì ước lượng.

**Nhóm phụ thuộc vào tôi ở đâu?** Phương Anh (policy_tool) và nhóm synthesis không chạy được nếu graph chưa gọi đúng worker — `AgentState` và `build_graph` là khung tích hợp của cả pipeline. Trí viết `eval_trace.py` cần `run_graph`/`save_trace` của tôi làm entry.

**Phần tôi phụ thuộc vào thành viên khác:** Cần policy_tool của Phương Anh có signature `run(state) → state` đúng contract để wire vào `policy_tool_worker_node`. Và cần ChromaDB đã được index (phần Bảo) để retrieval không abstain toàn bộ.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì?

Tôi sẽ port supervisor sang **LangGraph StateGraph** với `add_conditional_edges(route_decision)`. Lý do: trace hiện tại của tôi chỉ in thứ tự tuyến tính qua `history`, nhưng khi policy_tool tự gọi retrieval (không qua supervisor) thì graph topology bị ngầm — Trí phải đọc `workers_called` mới biết. Với LangGraph, checkpoint và trace DAG có sẵn, `docs/routing_decisions.md` có thể paste thẳng graph viz thay vì mô tả bằng chữ. Scope 2h vừa đủ: import `StateGraph`, map 4 node hiện có, giữ nguyên `supervisor_node` và `route_decision`.

---

*Lưu file này với tên: `reports/individual/Truong_Minh_Tien.md`*
