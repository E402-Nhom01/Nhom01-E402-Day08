from openai import OpenAI
import json

client = OpenAI()

WORKER_NAME = "policy_tool_worker"


# ─────────────────────────────────────────────
# Rule-based fallback (guardrail)
# ─────────────────────────────────────────────

def _analyze_policy_rules(task: str, chunks: list) -> dict:
    task_lower = task.lower()
    context_text = " ".join([c.get("text", "") for c in chunks]).lower()

    exceptions_found = []

    # Flash Sale
    if "flash sale" in task_lower or "flash sale" in context_text:
        exceptions_found.append({
            "type": "flash_sale_exception",
            "rule": "Đơn hàng Flash Sale không được hoàn tiền.",
            "source": "policy_refund_v4.txt",
        })

    # Digital product
    if any(kw in task_lower for kw in ["license", "license key", "subscription", "kỹ thuật số"]):
        exceptions_found.append({
            "type": "digital_product_exception",
            "rule": "Sản phẩm kỹ thuật số không được hoàn tiền.",
            "source": "policy_refund_v4.txt",
        })

    # Activated
    if any(kw in task_lower for kw in ["đã kích hoạt", "đã sử dụng", "đã đăng ký"]):
        exceptions_found.append({
            "type": "activated_exception",
            "rule": "Sản phẩm đã kích hoạt không được hoàn tiền.",
            "source": "policy_refund_v4.txt",
        })

    return {
        "policy_applies": len(exceptions_found) == 0,
        "policy_name": "refund_policy_v4",
        "exceptions_found": exceptions_found,
        "policy_version_note": "",
        "confidence": 0.6 if exceptions_found else 0.4,
        "explanation": "Rule-based fallback triggered.",
        "source": list({c.get("source", "unknown") for c in chunks if c}),
    }


# ─────────────────────────────────────────────
# LLM-based analysis
# ─────────────────────────────────────────────

def _analyze_policy_llm(task: str, chunks: list) -> dict:
    context_text = "\n\n".join([
        f"[SOURCE: {c.get('source','unknown')}]\n{c.get('text','')}"
        for c in chunks
    ])

    prompt = f"""
Bạn là policy analyst chuyên nghiệp.

Nhiệm vụ:
- Xác định policy có áp dụng không
- Tìm tất cả exceptions
- Xác định đúng version policy (v3 vs v4 nếu có)
- CHỈ sử dụng thông tin từ context
- Nếu thiếu thông tin → phải nói rõ

---

Task:
{task}

---

Context:
{context_text}

---

Rules cần check:
1. Flash Sale → không hoàn tiền
2. Digital product (license key, subscription) → không hoàn tiền
3. Sản phẩm đã kích hoạt → không hoàn tiền
4. Đơn trước 01/02/2026 → policy v3 (nếu không có data → note rõ)

---

Output JSON:
{{
  "policy_applies": true/false,
  "policy_name": "...",
  "exceptions_found": [
    {{
      "type": "...",
      "rule": "...",
      "source": "..."
    }}
  ],
  "policy_version_note": "...",
  "confidence": 0.0,
  "explanation": "..."
}}

---

Yêu cầu:
- confidence:
    0.9–1.0 → chắc chắn
    0.7–0.8 → suy luận hợp lý
    0.5–0.6 → thiếu context
    <0.5 → rất không chắc
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "You are a strict policy analysis engine. Return ONLY valid JSON."
                },
                {"role": "user", "content": prompt}
            ],
        )

        content = response.choices[0].message.content.strip()
        print("\n[DEBUG] LLM RAW OUTPUT:\n", content, "\n")

        try:
            result = json.loads(content)
        except:
            start = content.find("{")
            end = content.rfind("}") + 1
            result = json.loads(content[start:end])

        # attach sources
        result["source"] = list({c.get("source", "unknown") for c in chunks if c})

        return result

    except Exception as e:
        return {
            "policy_applies": False,
            "policy_name": "unknown",
            "exceptions_found": [],
            "policy_version_note": "",
            "confidence": 0.0,
            "explanation": f"LLM failed: {str(e)}",
            "source": [],
        }


# ─────────────────────────────────────────────
# Hybrid logic (FIXED)
# ─────────────────────────────────────────────

def analyze_policy(task: str, chunks: list) -> dict:
    llm_result = _analyze_policy_llm(task, chunks)

    # ❗ Invalid structure → fallback
    if not isinstance(llm_result, dict) or "policy_applies" not in llm_result:
        return _analyze_policy_rules(task, chunks)

    # ❗ HARD RULE: exceptions → NO refund
    if llm_result.get("exceptions_found"):
        llm_result["policy_applies"] = False
        llm_result["confidence"] = max(llm_result.get("confidence", 0), 0.85)

    # ❗ Fallback if LLM weak
    if llm_result.get("confidence", 0) < 0.6:
        rule_result = _analyze_policy_rules(task, chunks)

        if rule_result["exceptions_found"]:
            llm_result["exceptions_found"] = rule_result["exceptions_found"]
            llm_result["policy_applies"] = False
            llm_result["confidence"] = 0.8
            llm_result["explanation"] += " | Rule-based override applied."

    # ✅ Normalize exception types
    for ex in llm_result.get("exceptions_found", []):
        if "type" in ex:
            ex["type"] = ex["type"].lower().replace(" ", "_")

    return llm_result


# ─────────────────────────────────────────────
# Worker Entry Point
# ─────────────────────────────────────────────

def run(state: dict) -> dict:
    task = state.get("task", "")
    chunks = state.get("retrieved_chunks", [])
    needs_tool = state.get("needs_tool", False)

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state.setdefault("mcp_tools_used", [])

    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {
            "task": task,
            "chunks_count": len(chunks),
            "needs_tool": needs_tool,
        },
        "output": None,
        "error": None,
    }

    try:
        # Step 1: Retrieve if needed
        if not chunks and needs_tool:
            from mcp_server import dispatch_tool

            mcp_result = dispatch_tool("search_kb", {"query": task, "top_k": 3})
            state["mcp_tools_used"].append(mcp_result)

            if mcp_result.get("data", {}).get("chunks"):
                chunks = mcp_result["data"]["chunks"]
                state["retrieved_chunks"] = chunks

        # Step 2: Analyze
        policy_result = analyze_policy(task, chunks)
        state["policy_result"] = policy_result

        # Step 3: Optional ticket lookup
        if needs_tool and any(kw in task.lower() for kw in ["ticket", "p1", "jira"]):
            from mcp_server import dispatch_tool

            mcp_result = dispatch_tool("get_ticket_info", {"ticket_id": "P1-LATEST"})
            state["mcp_tools_used"].append(mcp_result)

        worker_io["output"] = {
            "policy_applies": policy_result["policy_applies"],
            "exceptions_count": len(policy_result.get("exceptions_found", [])),
        }

    except Exception as e:
        worker_io["error"] = {"code": "POLICY_CHECK_FAILED", "reason": str(e)}
        state["policy_result"] = {"error": str(e)}

    state.setdefault("worker_io_logs", []).append(worker_io)
    return state

# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Policy Tool Worker — Standalone Test")
    print("=" * 50)

    test_cases = [
        {
            "task": "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?",
            "retrieved_chunks": [
                {"text": "Ngoại lệ: Đơn hàng Flash Sale không được hoàn tiền.", "source": "policy_refund_v4.txt", "score": 0.9}
            ],
        },
        {
            "task": "Khách hàng muốn hoàn tiền license key đã kích hoạt.",
            "retrieved_chunks": [
                {"text": "Sản phẩm kỹ thuật số (license key, subscription) không được hoàn tiền.", "source": "policy_refund_v4.txt", "score": 0.88}
            ],
        },
        {
            "task": "Khách hàng yêu cầu hoàn tiền trong 5 ngày, sản phẩm lỗi, chưa kích hoạt.",
            "retrieved_chunks": [
                {"text": "Yêu cầu trong 7 ngày làm việc, sản phẩm lỗi nhà sản xuất, chưa dùng.", "source": "policy_refund_v4.txt", "score": 0.85}
            ],
        },
    ]

    for tc in test_cases:
        print(f"\n▶ Task: {tc['task'][:70]}...")
        result = run(tc.copy())
        pr = result.get("policy_result", {})
        print(f"  policy_applies: {pr.get('policy_applies')}")
        if pr.get("exceptions_found"):
            for ex in pr["exceptions_found"]:
                print(f"  exception: {ex['type']} — {ex['rule'][:60]}...")
        print(f"  MCP calls: {len(result.get('mcp_tools_used', []))}")

    print("\n✅ policy_tool_worker test done.")
