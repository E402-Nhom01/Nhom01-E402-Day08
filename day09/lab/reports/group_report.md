# Báo Cáo Nhóm — Lab Day 09: Multi-Agent Orchestration

**Tên nhóm:** ___________  
**Thành viên:**
| Tên | Vai trò | Email |
|-----|---------|-------|
| Trương Minh Tiền | Supervisor Owner |  |
| Phạm Đoàn Phương Anh | Worker Owner | ___ |
| Nguyễn Đức Dũng & Huỳnh Thái Bảo | MCP Owner | ___ |
| Nguyễn Đức Trí | Trace & Docs Owner | ___ |

**Ngày nộp:** 14/04/2026  
**Repo:** https://github.com/E402-Nhom01/Nhom01-E402-Day06.git 
**Độ dài khuyến nghị:** 600–1000 từ

---

> **Hướng dẫn nộp group report:**
> 
> - File này nộp tại: `reports/group_report.md`
> - Deadline: Được phép commit **sau 18:00** (xem SCORING.md)
> - Tập trung vào **quyết định kỹ thuật cấp nhóm** — không trùng lặp với individual reports
> - Phải có **bằng chứng từ code/trace** — không mô tả chung chung
> - Mỗi mục phải có ít nhất 1 ví dụ cụ thể từ code hoặc trace thực tế của nhóm

---

## 1. Kiến trúc nhóm đã xây dựng (150–200 từ)

> Hệ thống Day 09 được thiết kế theo mô hình supervisor–workers, gồm ba worker chính. Retrieval Worker chịu trách nhiệm truy vấn ChromaDB để lấy các đoạn ngữ cảnh liên quan kèm nguồn (citation). Policy Tool Worker xử lý các tình huống cần kiểm tra quy tắc nghiệp vụ như điều kiện hoàn tiền hoặc quyền truy cập, đồng thời chủ động gọi MCP tools khi dữ liệu trong kho tri thức chưa đủ. Synthesis Worker tổng hợp toàn bộ evidence thu thập được để tạo câu trả lời cuối cùng, đảm bảo tính nhất quán và bám sát nguồn. Về routing, supervisor phân luồng dựa trên loại yêu cầu: các câu hỏi liên quan SLA, sự cố hoặc ticket sẽ ưu tiên qua retrieval; các câu hỏi liên quan chính sách hoặc cần xác minh điều kiện sẽ chuyển sang policy tool worker; các trường hợp mơ hồ hoặc rủi ro cao có thể được gắn cờ để human review. Hệ thống tích hợp các MCP tools cốt lõi như search_kb, get_ticket_info, check_access_permission và create_ticket, giúp tăng tính linh hoạt, khả năng mở rộng và dễ theo dõi thông qua log theo từng worker.



Dùng kết quả từ `docs/system_architecture.md`.

**Hệ thống tổng quan:**

_________________

**Routing logic cốt lõi:**
> Supervisor dùng rule-based routing với keyword matching làm lớp quyết định chính (không phụ thuộc LLM classifier). Cụ thể: nếu task chứa từ khóa policy/refund/access thì route sang policy_tool_worker; nếu chứa từ khóa SLA/P1/ticket/escalation thì route sang retrieval_worker; nếu tín hiệu mơ hồ hoặc rủi ro cao (thiếu ngữ cảnh, mã lỗi lạ) thì gắn cờ human_review; còn lại fallback về retrieval_worker. Cách này ưu tiên tính ổn định, dễ debug, và giải thích được lý do route qua route_reason/log của supervisor.
_________________

**MCP tools đã tích hợp:**
- `search_kb`: Tìm đoạn tri thức liên quan theo truy vấn.
- `get_ticket_info`: Tra cứu thông tin ticket (priority/status/SLA/escalation).
- `create_ticket`: Tạo ticket hỗ trợ mới.
> User hỏi: “Ticket IT-1234 (P1) còn trong SLA không?” → Supervisor route sang worker phù hợp → worker gọi get_ticket_info("IT-1234") → nhận dữ liệu SLA/priority/status → Synthesis worker trả lời kết quả kèm nguồn/citation.
---

## 2. Quyết định kỹ thuật quan trọng nhất (200–250 từ)

> Chọn **1 quyết định thiết kế** mà nhóm thảo luận và đánh đổi nhiều nhất.
> Phải có: (a) vấn đề gặp phải, (b) các phương án cân nhắc, (c) lý do chọn phương án đã chọn.

**Quyết định:** Lựa chọn cơ chế supervisor routing theo rule-based kết hợp keyword matching, thay vì sử dụng LLM classifier làm bộ định tuyến chính.

**Bối cảnh vấn đề:** Bài toán đặt ra là các yêu cầu trong hệ thống helpdesk rất đa dạng: có câu hỏi mang tính tra cứu tài liệu (SLA, escalation), có câu cần kiểm tra policy hoặc permission, và có trường hợp mơ hồ cần chuyển sang human review. Nếu định tuyến sai, các worker phía sau vẫn xử lý được nhưng dễ dẫn đến thiếu bằng chứng hoặc gọi MCP tool không cần thiết, làm tăng độ trễ và giảm độ tin cậy của hệ thống.

_________________

**Các phương án đã cân nhắc:**

| Phương án | Ưu điểm | Nhược điểm |
|-----------|---------|-----------|
| Rule-based + keyword matching | Nhanh, ổn định, dễ debug, route_reason rõ ràng | Bao phủ ngôn ngữ hạn chế, dễ miss câu diễn đạt lạ |
| LLM classifier cho supervisor | Linh hoạt với câu hỏi tự nhiên, bắt ngữ nghĩa tốt hơn | Tăng latency/chi phí, khó tái lập kết quả, khó kiểm soát lỗi route|

**Phương án đã chọn và lý do:** Nhóm chọn Rule-based + keyword matching làm baseline vì phù hợp mục tiêu Day 09: cần orchestration minh bạch, dễ quan sát qua log, và dễ kiểm chứng khi demo/chấm điểm. Với phạm vi lab, ưu tiên độ ổn định và khả năng giải thích quyết định route quan trọng hơn độ “thông minh” của classifier. Kiến trúc hiện tại vẫn mở để nâng cấp hybrid (rule trước, LLM cho ca mơ hồ) ở vòng cải tiến tiếp theo.

_________________

**Bằng chứng từ trace/code:**
> Dẫn chứng cụ thể (VD: route_reason trong trace, đoạn code, v.v.)

Query chứa “ticket P1 / SLA” → supervisor route retrieval/policy → worker gọi `get_ticket_info` → synthesis trả lời kèm nguồn.

```
# Path: day09/lab/workers/policy_tool.py
# supervisor: rule-based routing bằng keyword
def route_task(task: str) -> str:
    t = task.lower()
    policy_keys = ["hoàn tiền", "refund", "flash sale", "access", "cấp quyền"]
    sla_keys = ["p1", "sla", "ticket", "escalation", "sự cố"]

    if any(k in t for k in policy_keys):
        return "policy_tool_worker"
    if any(k in t for k in sla_keys):
        return "retrieval_worker"
    return "retrieval_worker"  # fallback

# policy worker: gọi MCP tool khi cần ticket data
def handle_policy_task(task: str, mcp_dispatch):
    worker = route_task(task)
    if "ticket" in task.lower():
        ticket = mcp_dispatch("get_ticket_info", {"ticket_id": "IT-1234"})
        return {
            "route_reason": "keyword=ticket",
            "workers_called": [worker],
            "tool_called": "get_ticket_info",
            "tool_result": ticket,
        }
    return {"route_reason": "policy/default", "workers_called": [worker]}
```

---

## 3. Kết quả grading questions (150–200 từ)

> Sau khi chạy pipeline với grading_questions.json (public lúc 17:00):
> - Nhóm đạt bao nhiêu điểm raw?
> - Câu nào pipeline xử lý tốt nhất?
> - Câu nào pipeline fail hoặc gặp khó khăn?

**Tổng điểm raw ước tính:** ___ / 96

**Câu pipeline xử lý tốt nhất:**
- ID: ___ — Lý do tốt: ___________________

**Câu pipeline fail hoặc partial:**
- ID: ___ — Fail ở đâu: ___________________  
  Root cause: ___________________

**Câu gq07 (abstain):** Nhóm xử lý thế nào?

_________________

**Câu gq09 (multi-hop khó nhất):** Trace ghi được 2 workers không? Kết quả thế nào?

_________________

---

## 4. So sánh Day 08 vs Day 09 — Điều nhóm quan sát được (150–200 từ)

> Dựa vào `docs/single_vs_multi_comparison.md` — trích kết quả thực tế.

**Metric thay đổi rõ nhất (có số liệu):**

_________________

**Điều nhóm bất ngờ nhất khi chuyển từ single sang multi-agent:**

_________________

**Trường hợp multi-agent KHÔNG giúp ích hoặc làm chậm hệ thống:**

_________________

---

## 5. Phân công và đánh giá nhóm (100–150 từ)

> Đánh giá trung thực về quá trình làm việc nhóm.

**Phân công thực tế:**

| Thành viên | Phần đã làm | Sprint |
|------------|-------------|--------|
| Phạm Đoàn Phương Anh  | MCP, policy tools | sprint 03 |
| Trương Mình Tiền |sprint 01 | sprint 01 |
| Nguyễn Đức Dũng |Grounded answer theo evidence, Abstain khi thiếu thông tin,Trích dẫn nguồn, Tính confidence, Ghi trace/log worker  | sprint 03 |
| Huỳnh Thái Bảo | embedding cho query,Truy vấn ChromaDB (dense retrieval), Lấy top-k chunks liên quan  | sprint 04
| Nguyễn Đức Trí | Tổng hợp và viết báo cáo |  |

**Điều nhóm làm tốt:**
- Tách kiến trúc supervisor–worker rõ vai, dễ debug.
- Routing rule-based ổn định, có route_reason để giải thích quyết định.
- Tích hợp MCP tools đúng luồng (search/tra cứu ticket/kiểm quyền).
- Synthesis có cơ chế grounded + abstain, giảm hallucination.
- Trace/log theo worker đầy đủ, thuận tiện đánh giá và so sánh Day 08 vs Day 09.

_________________

**Điều nhóm làm chưa tốt hoặc gặp vấn đề về phối hợp:**
- Phối hợp ban đầu chưa đồng bộ contract I/O giữa các worker, phải sửa lại field name nhiều lần.
- Routing keyword còn cứng, gặp câu hỏi mơ hồ dễ route chưa tối ưu.
- Chia việc test tích hợp muộn, nên lỗi ghép pipeline phát hiện trễ.
- Trace format giữa các thành viên lúc đầu chưa thống nhất, tốn thời gian chuẩn hóa.
- Phân chia thời gian chưa đều: tập trung code nhiều, phần docs/report bị dồn cuối

_________________

**Nếu làm lại, nhóm sẽ thay đổi gì trong cách tổ chức?**
- Chốt contract state/schema ngay từ đầu và review chéo trước khi code.
- Chia sprint rõ hơn: mỗi sprint có owner + checklist DoD + mốc tích hợp sớm.
- Thiết lập trace format thống nhất từ đầu để tránh sửa ngược.
- Dành thời gian cố định cho integration test giữa các worker, không để dồn cuối.
- Song song hóa viết docs/report theo tiến độ code thay vì làm sau cùng.
_________________

---

## 6. Nếu có thêm 1 ngày, nhóm sẽ làm gì? (50–100 từ)
> Nếu có thêm 1 ngày, nhóm sẽ tập trung 2 cải thiện. Thứ nhất, tối ưu retrieval (hybrid/rerank + ưu tiên nguồn theo intent) vì q08 lấy sai source dù route đúng; đây là lỗi còn lại trực tiếp kéo source_hit_rate xuống 92%. Thứ hai, tinh chỉnh supervisor routing cho câu policy như q10 (store credit) vì đã route nhầm sang retrieval; điều này cho thấy keyword/rule hiện tại chưa bao phủ đủ. Mục tiêu là tăng route accuracy từ 93% lên ổn định hơn và giảm lỗi nguồn trong các câu medium.

- Route đúng nhưng source sai (q08): route=retrieval_worker(exp=retrieval_worker) nhưng sources=['access_control_sop.txt','hr_leave_policy.txt','policy_refund_v4.txt'] thay vì exp=['sla_p1_2026.txt'].
- Route sai (q10): route=retrieval_worker(exp=policy_tool_worker) và kéo theo source sai sources=['access_control_sop.txt','hr_leave_policy.txt','policy_refund_v4.txt'].
- Chỉ số tổng hợp liên quan: route_accuracy=14/15 (93%), source_hit_rate=13/14 (92%), avg_source_recall=0.929.
- MCP còn dùng thấp: mcp_usage_rate=12/84 (14%), là dấu hiệu policy/tool path chưa được kích hoạt đủ rộng.
- Độ chắc chắn còn thấp: avg_confidence=0.406 dù 15/15 succeeded, cho thấy còn khoảng trống tối ưu chất lượng trả lời.

_________________

---

*File này lưu tại: `reports/group_report.md`*  
*Commit sau 18:00 được phép theo SCORING.md*
