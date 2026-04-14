# System Architecture — Lab Day 09

**Nhóm:** E402 - 01  
**Ngày:** 14/04/2026  
**Version:** 1.0

---

## 1. Tổng quan kiến trúc

> Mô tả ngắn hệ thống của nhóm: chọn pattern gì, gồm những thành phần nào.

**Pattern đã chọn:** Supervisor-Worker  
**Lý do chọn pattern này (thay vì single agent):**

Kiến trúc gồm: Supervisor (route theo rule/keyword và gắn cờ rủi ro), Retrieval Worker (lấy evidence từ ChromaDB), Policy Tool Worker (phân tích policy + gọi MCP tools), Synthesis Worker (tổng hợp câu trả lời grounded kèm nguồn), và MCP Server (các tool `search_kb`, `get_ticket_info`, `check_access_permission`, `create_ticket`). Toàn bộ pipeline dùng shared state + trace logs (`route_reason`, `workers_called`, `mcp_tools_used`) để dễ debug, đánh giá, và mở rộng capability theo từng worker.

---

## 2. Sơ đồ Pipeline

> Vẽ sơ đồ pipeline dưới dạng text, Mermaid diagram, hoặc ASCII art.
> Yêu cầu tối thiểu: thể hiện rõ luồng từ input → supervisor → workers → output.

**Ví dụ (ASCII art):**
```
User Request
     │
     ▼
┌──────────────┐
│  Supervisor  │  ← route_reason, risk_high, needs_tool
└──────┬───────┘
       │
   [route_decision]
       │
  ┌────┴────────────────────┐
  │                         │
  ▼                         ▼
Retrieval Worker     Policy Tool Worker
  (evidence)           (policy check + MCP)
  │                         │
  └─────────┬───────────────┘
            │
            ▼
      Synthesis Worker
        (answer + cite)
            │
            ▼
         Output
```

**Sơ đồ thực tế của nhóm:**

```
User Query
   |
   v
[Supervisor Router]
   |-- policy/refund/access --> [Policy Tool Worker] --> [MCP Tools]
   |-- SLA/P1/ticket ---------> [Retrieval Worker] ---> [KB/Vector DB]
   |-- ambiguous/high-risk ---> [Human Review Flag]
   `-- default ---------------> [Retrieval Worker]

[All evidence/results] ---> [Synthesis Worker] ---> [Final Answer + Sources]
                                         |
                                         `--> [Trace Logs]
```

---

## 3. Vai trò từng thành phần

### Supervisor (`graph.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Điều phối luồng xử lý: phân loại yêu cầu, chọn worker phù hợp, và kiểm soát rủi ro trước khi tổng hợp trả lời. |
| **Input** | task/query của user + context trạng thái hiện tại (history, retrieved_chunks nếu có, cờ rủi ro/tool). |
| **Output** | supervisor_route, route_reason, risk_high, needs_tool |
| **Routing logic** | Rule-based + keyword matching: policy/refund/access → policy_tool_worker; SLA/P1/ticket/escalation → retrieval_worker; mặc định fallback retrieval_worker; trường hợp mơ hồ gắn cờ review. |
| **HITL condition** | Bật HITL khi risk_high=true: thiếu bằng chứng, xung đột nguồn, query mơ hồ/ngoài phạm vi, hoặc liên quan quyết định nhạy cảm cần xác nhận thủ công. |

### Retrieval Worker (`workers/retrieval.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Nhận task từ state, chạy dense retrieval trên ChromaDB và trả về retrieved_chunks + retrieved_sources. |
| **Embedding model** | Mặc định sentence-transformers/all-MiniLM-L6-v2; fallback OpenAI text-embedding-3-small (nếu có API key). |
| **Top-k** | Mặc định 3 (DEFAULT_TOP_K), có thể override qua state["retrieval_top_k"]. |
| **Stateless?** | Yes (xử lý theo từng request, không giữ session state nội bộ).
 |

### Policy Tool Worker (`workers/policy_tool.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Phân tích policy từ task + retrieved_chunks, xác định policy áp dụng/ngoại lệ, và gọi MCP khi thiếu context hoặc cần thêm dữ liệu ticket. |
| **MCP tools gọi** | search_kb (khi chưa có chunks và needs_tool=true), get_ticket_info (khi task chứa ticket/p1/jira). |
| **Exception cases xử lý** | Flash Sale không hoàn tiền; sản phẩm số (license key/subscription) không hoàn tiền; sản phẩm đã kích hoạt/đăng ký không hoàn tiền; đơn trước 01/02/2026 được gắn note áp dụng policy v3. |

### Synthesis Worker (`workers/synthesis.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **LLM model** | Ưu tiên gpt-4o-mini (OpenAI); fallback gemini-1.5-flash nếu dùng Google API. |
| **Temperature** | 0.1 (thiết lập thấp để tăng tính grounded/ổn định). |
| **Grounding strategy** | Dựng context chỉ từ retrieved_chunks + policy_result và ràng buộc prompt “chỉ dùng tài liệu được cung cấp”, kèm citation nguồn. |
| **Abstain condition** | Khi context rỗng/không đủ bằng chứng thì trả lời theo mẫu “Không đủ thông tin trong tài liệu nội bộ” (không suy đoán ngoài context). |

### MCP Server (`mcp_server.py`)

| Tool | Input | Output |
|------|-------|--------|
| search_kb | query, top_k | chunks, sources |
| get_ticket_info | ticket_id | ticket details |
| check_access_permission | access_level, requester_role | can_grant, approvers |
| create_ticket | priority, title, description | ticket_id, status, message |

---

## 4. Shared State Schema

> Liệt kê các fields trong AgentState và ý nghĩa của từng field.

| Field | Type | Mô tả | Ai đọc/ghi |
|-------|------|-------|-----------|
| task | str | Câu hỏi đầu vào | supervisor đọc |
| supervisor_route | str | Worker được chọn | supervisor ghi |
| route_reason | str | Lý do route | supervisor ghi |
| retrieved_chunks | list | Evidence từ retrieval | retrieval ghi, synthesis đọc |
| policy_result | dict | Kết quả kiểm tra policy | policy_tool ghi, synthesis đọc |
| mcp_tools_used | list | Tool calls đã thực hiện | policy_tool ghi |
| final_answer | str | Câu trả lời cuối | synthesis ghi |
| confidence | float | Mức tin cậy | synthesis ghi |
| worker_io_logs | list[dict] | Log I/O theo từng worker (input, output, error) để trace/debug | retrieval/policy_tool/synthesis ghi, eval/trace đọc |

---

## 5. Lý do chọn Supervisor-Worker so với Single Agent (Day 08)

| Tiêu chí | Single Agent (Day 08) | Supervisor-Worker (Day 09) |
|----------|----------------------|--------------------------|
| Debug khi sai | Khó — không rõ lỗi ở đâu | Dễ hơn — test từng worker độc lập |
| Thêm capability mới | Phải sửa toàn prompt | Thêm worker/MCP tool riêng |
| Routing visibility | Không có | Có route_reason trong trace |
| Khả năng kiểm soát rủi ro (HITL) | Hạn chế, xử lý trong một luồng chung | Rõ ràng hơn, có cờ risk_high và nhánh human review |

**Nhóm điền thêm quan sát từ thực tế lab:**
Trong run evaluation gần nhất, nhóm thấy lợi ích của Supervisor-Worker khá rõ: route accuracy đạt mức cao (93%), source hit rate cũng ổn định (92%), và các case policy phức tạp được tách riêng qua policy_tool_worker nên dễ phân tích hơn thay vì trộn chung trong một prompt lớn. Khi xảy ra sai lệch (như q08, q10), trace giúp khoanh vùng nhanh lỗi nằm ở retrieval/routing thay vì phải debug toàn pipeline. Tuy vậy, nhóm cũng ghi nhận chi phí orchestration cao hơn single-agent: latency trung bình còn lớn (~12.7s), confidence trung bình thấp (0.406), và tỷ lệ gọi MCP còn thấp (14%) nên chưa khai thác hết lợi thế tool-use. Kết luận của nhóm là kiến trúc Day 09 phù hợp cho mở rộng và kiểm soát rủi ro, nhưng cần thêm một vòng tuning cho retrieval + routing để cải thiện chất lượng thực chiến.

_________________

---

## 6. Giới hạn và điểm cần cải tiến
- Routing hiện tại chủ yếu rule-based/keyword, dễ ổn định nhưng còn yếu với câu hỏi diễn đạt tự do hoặc đa ý.
- `policy_tool_worker` mới dùng rule đơn giản; phần LLM policy analysis chưa bật đầy đủ nên độ bao phủ exception còn hạn chế.
- MCP đang ở mức mock/in-process, chưa có cơ chế auth, retry, timeout và quan sát lỗi chuẩn như production.
- Retrieval phụ thuộc một embedding pipeline; chưa có hybrid/rerank nên recall ở câu hỏi khó có thể chưa tối ưu.
- Confidence hiện là heuristic, chưa có calibration hoặc LLM-as-judge, nên chưa phản ánh chính xác mức độ chắc chắn.

->`Hướng cải tiến ưu tiên:` nâng router thành hybrid (rule + LLM classifier cho ca mơ hồ), chuẩn hóa MCP client (timeout/retry/auth), thêm rerank/hybrid retrieval, và mở rộng trace metrics để đánh giá sai lệch route theo từng loại câu hỏi.
