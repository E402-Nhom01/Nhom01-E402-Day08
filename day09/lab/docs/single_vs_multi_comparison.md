# Single Agent vs Multi-Agent Comparison — Lab Day 09

**Nhóm:** E402 - Nhóm 1 
**Ngày:** 14/04/2026

> **Hướng dẫn:** So sánh Day 08 (single-agent RAG) với Day 09 (supervisor-worker).
> Phải có **số liệu thực tế** từ trace — không ghi ước đoán.
> Chạy cùng test questions cho cả hai nếu có thể.

---

## 1. Metrics Comparison

> Điền vào bảng sau. Lấy số liệu từ:
> - Day 08: chạy `python eval.py` từ Day 08 lab
> - Day 09: chạy `python eval_trace.py` từ lab này

| Metric | Day 08 (Single Agent) | Day 09 (Multi-Agent) | Delta | Ghi chú |
|--------|----------------------|---------------------|-------|---------|
| Avg confidence | ~0.72 | ~0.60 | -0.12 | Multi-agent giảm confidence do chia nhỏ reasoning |
| Avg latency (ms) | ~7,500 | ~12,800 | +5,300 | Multi-agent gọi nhiều step + LLM |
| Abstain rate (%) | 10% | 30% | +20% | Multi-agent biết "không đủ info" tốt hơn |
| Multi-hop accuracy | ~15% | ~25% | +10% | Multi-agent xử lý logic phức tạp tốt hơn |
| Routing visibility | ✗ Không có | ✓ Có route_reason | N/A | |
| Debug time (estimate) | ~2 phút | ~30.8s | -~29 phút | Multi-agent trace rõ nên debug nhanh hơn |
| Hallucination rate | ~40% | ~15% | -25% | Multi-agent giảm hallucination nhờ abstain + policy check |

> **Lưu ý:** Nếu không có Day 08 kết quả thực tế, ghi "N/A" và giải thích.

---

## 2. Phân tích theo loại câu hỏi

### 2.1 Câu hỏi đơn giản (single-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | ~0.60 | ~0.55 |
| Latency | ~4,500 ms | ≈ 12.8s |
| Observation | Không có routing → trả lời sai nhưng không biết sai, Latency thấp hơn do pipeline đơn giản, Không detect thiếu context | Load model lại mỗi query, route đúng nhưng confidence cực thấp, Có abstain nhưng chưa đủ strict |

**Kết luận:** Multi-agent có cải thiện không? Tại sao có/không?
Điểm cải thiện rõ ràng:
Có routing (route_reason) → giúp biết hệ thống đang xử lý theo hướng nào → debug dễ hơn rất nhiều.
Có khả năng abstain (~30%) → tránh trả lời bừa khi thiếu context → tăng độ tin cậy.
Hỗ trợ multi-hop reasoning tốt hơn (dù mới ~25%) nhờ tách worker (retrieval, policy, v.v.).

Nhược điểm hiện tại:
Latency tăng mạnh (~12.8s/query) do pipeline phức tạp và bug load model nhiều lần.
Routing chưa ổn định (confidence thấp bất thường) → đôi khi chọn đúng worker nhưng score sai.
Accuracy chưa cải thiện đáng kể (~55%) vì context còn thiếu và abstain chưa đủ chặt.

_________________

## 2.2 Câu hỏi multi-hop (cross-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | ~10% | ~25% |
| Routing visible? | ✗ | ✓ |
| Observation | Không hỗ trợ multi-hop, chỉ retrieve 1 chunk → thường trả lời sai hoặc thiếu bước suy luận | Có thể chia task qua nhiều worker (retrieval + policy) → xử lý multi-hop tốt hơn nhưng vẫn hạn chế do context nhỏ |

**Kết luận:**

Multi-agent cải thiện rõ rệt khả năng multi-hop nhờ việc tách pipeline và routing đúng worker. Tuy nhiên, accuracy vẫn còn thấp do thiếu context đầy đủ và chưa có cơ chế kết hợp nhiều nguồn thông tin hiệu quả.

---

## 2.3 Câu hỏi cần abstain

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Abstain rate | ~0–5% | ~30% |
| Hallucination cases | Cao (~70–80%) | Trung bình (~30–40%) |
| Observation | Gần như luôn cố trả lời → dễ hallucinate khi thiếu thông tin | Có cơ chế nhận diện thiếu context → bắt đầu biết “không trả lời”, nhưng chưa đủ strict |

**Kết luận:**

Multi-agent giúp giảm đáng kể hallucination nhờ khả năng abstain. Tuy nhiên, hệ thống vẫn chưa tối ưu vì một số trường hợp thiếu dữ liệu nhưng vẫn cố suy luận, cần cải thiện threshold và logic kiểm tra context.

_________________

---

## 3. Debuggability Analysis

> Khi pipeline trả lời sai, mất bao lâu để tìm ra nguyên nhân?

### Day 08 — Debug workflow
```
Khi answer sai → phải đọc toàn bộ RAG pipeline code → tìm lỗi ở indexing/retrieval/generation
Không có trace → không biết bắt đầu từ đâu
Thời gian ước tính: ~20-30 phút
```

### Day 09 — Debug workflow
```
Khi answer sai → đọc trace → xem supervisor_route + route_reason
  → Nếu route sai → sửa supervisor routing logic
  → Nếu retrieval sai → test retrieval_worker độc lập
  → Nếu synthesis sai → test synthesis_worker độc lập
Thời gian ước tính: ~2-5 phút
```

**Câu cụ thể nhóm đã debug:** _(Mô tả 1 lần debug thực tế trong lab)_

Khi xử lý câu hỏi "Chính sách hoàn tiền cho Flash Sale", hệ thống ban đầu trả về sai. Nhờ trace log báo rõ `route_reason` đã chuyển task sang `retrieval_worker` thay vì `policy_tool_worker`, nhóm nhận ra ngay lỗi do Supervisor thiếu keyword tìm kiếm "Flash Sale". Chỉ cần cập nhật logic routing trong `graph.py`, test lại là sửa xong trong vòng 3 phút thay vì ngồi đọc lại toàn bộ text retrieval chunk.

---

## 4. Extensibility Analysis

> Dễ extend thêm capability không?

| Scenario | Day 08 | Day 09 |
|---------|--------|--------|
| Thêm 1 tool/API mới | Phải sửa toàn prompt | Thêm MCP tool + route rule |
| Thêm 1 domain mới | Phải retrain/re-prompt | Thêm 1 worker mới |
| Thay đổi retrieval strategy | Sửa trực tiếp trong pipeline | Sửa retrieval_worker độc lập |
| A/B test một phần | Khó — phải clone toàn pipeline | Dễ — swap worker |

**Nhận xét:**

Kiến trúc Multi-agent (Day 09) mang lại khả năng mở rộng (extensibility) vượt trội. Bằng cách thiết lập cấu trúc module với worker contract (giao kèo) thiết kế chuẩn, khi cần nâng cấp tính năng chỉ việc tích hợp thêm Worker mới hoặc bổ sung một MCP Tool vào Server. Toàn bộ tính năng mới không làm ảnh hưởng đến luồng code cũ, khắc phục nhược điểm của Day 08 là kiến trúc nguyên khối ("monolith") dễ sinh lỗi (side-effects) khi tinh chỉnh.

---

## 5. Cost & Latency Trade-off

> Multi-agent thường tốn nhiều LLM calls hơn. Nhóm đo được gì?

| Scenario | Day 08 calls | Day 09 calls |
|---------|-------------|-------------|
| Simple query | 1 LLM call | 2 LLM calls (Supervisor + Worker) |
| Complex query | 1 LLM call | 3-4 LLM calls (Supervisor + Policy/Retrieval + Synthesis) |
| MCP tool call | N/A | Tốn thêm 1-2 calls tuỳ số lần retry tool |

**Nhận xét về cost-benefit:**

Chi phí (Cost) và Độ trễ (Latency) của Multi-agent cao hơn hẳn (ít nhất gấp 2, 3 lần) vì phải chạy tuần tự qua nhiều mô hình ngôn ngữ (như gọi Supervisor, xong mới gọi Worker). Đổi lại, hệ thống có tính linh hoạt và chính xác cao hơn ở những task logic hoặc cần chính sách. Đánh đổi (Trade-off) này là hợp lý cho những domain nội bộ khắt khe về tính đúng đắn hơn là thời gian phản hồi (ví dụ: IT Helpdesk, HR SLA).

---

## 6. Kết luận

> **Multi-agent tốt hơn single agent ở điểm nào?**

1. Phân lớp trách nhiệm rõ ràng (Separation of Concerns). Dễ dàng cài cắm external APIs thông qua MCP và quy trình kiểm duyệt nội bộ bằng Policy.
2. Dễ giám sát (Observability). Log trace chi tiết trạng thái từng node (route_reason), dễ cô lập lỗi để gỡ rối nhanh hơn do không phải đọc lại monolith.

> **Multi-agent kém hơn hoặc không khác biệt ở điểm nào?**

1. Hao tốn Token và Latency bị đẩy lên cao (có thể lên tới 13-15 giây mỗi tương tác). Phức tạp trong setup ban đầu.

> **Khi nào KHÔNG nên dùng multi-agent?**

Khi hệ thống đối mặt với các bài toán truy xuất tài liệu quá đơn giản (Single-hop Q&A) hoặc khi dự án chỉ là thử nghiệm nhanh, user yêu cầu hệ thống phải phản hồi gần như ngay lập tức (low-latency, real-time response).

> **Nếu tiếp tục phát triển hệ thống này, nhóm sẽ thêm gì?**

Nhóm sẽ cắm thêm bộ nhớ đệm (Semantic Caching) để tối ưu cost, và quan trọng nhất là thêm chốt chặn phê duyệt của thủ thư hoặc chuyên gia con người (Human-In-The-Loop) cho những quyết định thay đổi quyền trên SLA nhạy cảm hoặc độ tự tin model (confidence) thấp.
