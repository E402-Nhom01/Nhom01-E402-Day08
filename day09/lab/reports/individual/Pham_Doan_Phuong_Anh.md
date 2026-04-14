# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Phạm Đoàn Phương Anh 
**Vai trò trong nhóm:** Worker Owner
**Ngày nộp:** 14/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

> **Lưu ý quan trọng:**
> - Viết ở ngôi **"tôi"**, gắn với chi tiết thật của phần bạn làm
> - Phải có **bằng chứng cụ thể**: tên file, đoạn code, kết quả trace, hoặc commit
> - Nội dung phân tích phải khác hoàn toàn với các thành viên trong nhóm
> - Deadline: Được commit **sau 18:00** (xem SCORING.md)
> - Lưu file với tên: `reports/individual/[ten_ban].md` (VD: `nguyen_van_a.md`)

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

1. Tôi phụ trách phần nào?

Trong lab này, tôi đảm nhận vai trò Worker Owner, chịu trách nhiệm chính cho việc triển khai, chạy thử và debug các worker trong pipeline gồm: policy_tool_worker, retrieval_worker và synthesis_worker.

Module/file tôi chịu trách nhiệm chính là:

File chính: workers/policy_tool.py
Ngoài ra có tham gia debug: workers/retrieval.py, workers/synthesis.py

Các function tôi trực tiếp implement:

analyze_policy(): logic hybrid giữa LLM và rule-based
_analyze_policy_llm(): gọi LLM để phân tích policy
_analyze_policy_rules(): fallback rule-based
run(): entry point của worker, xử lý state và gọi MCP khi cần

Worker của tôi nhận input từ retrieval_worker (retrieved_chunks) và trả về policy_result để synthesis_worker tổng hợp câu trả lời cuối.

Ngoài ra, tôi cũng viết thêm:

HTTP server cho MCP (mcp_server.py)
UI đơn giản bằng Gradio để visualize pipeline và log

Cách phần của tôi kết nối với team:

Nhận state["retrieved_chunks"] từ retrieval
Trả state["policy_result"] cho synthesis
Khi thiếu dữ liệu → gọi MCP (search_kb, get_ticket_info)

Bằng chứng:

File workers/policy_tool.py có toàn bộ logic worker
Log debug:
[DEBUG] LLM RAW OUTPUT:
{ "policy_applies": false, "exceptions_found": [...] }
worker_io_logs trong state:
{
  "worker": "policy_tool_worker",
  "output": {
    "policy_applies": false,
    "exceptions_count": 1
  }
}

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

Tôi chọn thiết kế hybrid policy analysis (LLM + rule-based fallback) thay vì chỉ dùng LLM.

Các lựa chọn thay thế:

Chỉ dùng LLM → dễ implement nhưng không ổn định
Chỉ dùng rule-based → nhanh nhưng thiếu linh hoạt
Hybrid (LLM + rule) → phức tạp hơn nhưng robust hơn

Lý do tôi chọn hybrid:

LLM có thể hiểu context phức tạp nhưng:
đôi khi hallucinate
đôi khi trả JSON sai format
Rule-based giúp:
enforce các luật cứng (Flash Sale, digital product)
đảm bảo không vi phạm policy critical

Trade-off đã chấp nhận:

Code phức tạp hơn (2 layer logic)
Phải maintain consistency giữa LLM và rules
Tăng latency nhẹ (LLM call + fallback check)

Bằng chứng từ code:

# HARD RULE: 
```
exceptions → NO refund
if llm_result.get("exceptions_found"):
    llm_result["policy_applies"] = False
    llm_result["confidence"] = max(llm_result.get("confidence", 0), 0.85)

# Fallback if LLM weak
if llm_result.get("confidence", 0) < 0.6:
    rule_result = _analyze_policy_rules(task, chunks)

    if rule_result["exceptions_found"]:
        llm_result["exceptions_found"] = rule_result["exceptions_found"]
        llm_result["policy_applies"] = False
        llm_result["confidence"] = 0.8
```

Effect trong trace:

Các case như “Flash Sale” luôn bị chặn đúng:
exception: flash_sale_exception — Đơn hàng Flash Sale không được hoàn tiền.
policy_applies: False
Khi LLM không chắc → rule override giúp tăng accuracy

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

Lỗi: MCP không được gọi trong pipeline → mcp_hit_rate = 0

Symptom:

Khi chạy test_questions.json, log cho thấy:
mcp_hit_rate = 0
mcp_tools_used = []
Pipeline vẫn chạy và trả lời đúng nhiều câu, nhưng:
không sử dụng external tool
không đúng yêu cầu multi-agent + MCP

Root cause:

Trong policy_tool_worker.run():
needs_tool = state.get("needs_tool", False)
Nhưng upstream (supervisor) không set needs_tool = True
→ dẫn đến block này không bao giờ chạy:
if not chunks and needs_tool:
    mcp_result = dispatch_tool("search_kb", ...)

Cách sửa:

Fix 1: Update logic để gọi MCP khi thiếu chunks, không phụ thuộc hoàn toàn vào needs_tool
Fix 2: Debug cùng teammate (Trương Minh Tiền) để đảm bảo supervisor set đúng flag

Ví dụ fix:

if not chunks:
    from mcp_server import dispatch_tool
    mcp_result = dispatch_tool("search_kb", {"query": task, "top_k": 3})

Bằng chứng trước/sau:

Trước:

mcp_hit_rate = 0
mcp_tools_used = []

Sau:

mcp_tools_used = [
  {"tool": "search_kb", "status": "success"}
]
Trace cho thấy worker đã gọi MCP:
"MCP calls: 1"


---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

Tôi làm tốt nhất ở việc debug end-to-end pipeline. Tôi không chỉ viết policy worker mà còn chạy toàn bộ hệ thống, đọc trace và phát hiện lỗi liên quan đến integration (MCP không được gọi). Ngoài ra, tôi chủ động viết thêm UI bằng Gradio để quan sát pipeline, giúp debug nhanh hơn.

Điểm tôi chưa tốt là phụ thuộc vào upstream (supervisor) khá nhiều. Khi supervisor không set đúng flag (needs_tool), worker của tôi không hoạt động đúng, cho thấy tôi chưa thiết kế đủ defensive.

Nhóm phụ thuộc vào tôi ở phần:

Policy reasoning (nếu sai → output sai toàn bộ)
MCP integration (nếu không chạy → mất điểm phần orchestration)

Phần tôi phụ thuộc vào người khác:

Supervisor phải route đúng + set state đúng
Retrieval phải trả chunks chất lượng

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Tôi sẽ cải thiện MCP trigger logic trong supervisor thay vì để worker tự quyết định.

Lý do:

Trace cho thấy mcp_hit_rate = 0 ban đầu → vấn đề nằm ở orchestration, không phải worker
Nếu supervisor detect tốt khi nào cần tool (ví dụ: thiếu context, low confidence), pipeline sẽ đúng nghĩa multi-agent hơn

Cụ thể: thêm rule như:

if retrieval_score < threshold → needs_tool = True

Điều này sẽ giúp tăng mcp_hit_rate và improve score phần orchestration.


---
