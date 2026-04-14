"""
mcp_ui.py — Simple UI for MCP Server (Gradio)

Run:
    python mcp_ui.py
"""

import gradio as gr
import json

from mcp_server import dispatch_tool, list_tools


# ─────────────────────────────────────────────
# Helper: call tool
# ─────────────────────────────────────────────

def call_mcp_tool(tool_name, tool_input_str):
    try:
        tool_input = json.loads(tool_input_str) if tool_input_str else {}
    except Exception as e:
        return f"❌ Invalid JSON input: {e}"

    result = dispatch_tool(tool_name, tool_input)

    return json.dumps(result, indent=2, ensure_ascii=False)


# ─────────────────────────────────────────────
# Tool list (for dropdown)
# ─────────────────────────────────────────────

tool_names = [t["name"] for t in list_tools()]


# ─────────────────────────────────────────────
# Example presets (super useful for demo)
# ─────────────────────────────────────────────

EXAMPLES = {
    "search_kb": {
        "query": "SLA P1 resolution time",
        "top_k": 2
    },
    "get_ticket_info": {
        "ticket_id": "P1-LATEST"
    },
    "check_access_permission": {
        "access_level": 2,
        "requester_role": "employee",
        "is_emergency": True
    },
    "create_ticket": {
        "priority": "P2",
        "title": "Login API slow",
        "description": "Users report slow login response"
    }
}


def load_example(tool_name):
    example = EXAMPLES.get(tool_name, {})
    return json.dumps(example, indent=2)


# ─────────────────────────────────────────────
# UI Layout
# ─────────────────────────────────────────────

with gr.Blocks(title="MCP Tool UI") as app:
    gr.Markdown("# 🧠 MCP Server Playground")
    gr.Markdown("Test your tools (search_kb, ticket, access control, etc.)")

    with gr.Row():
        tool_dropdown = gr.Dropdown(
            choices=tool_names,
            label="Select Tool",
            value=tool_names[0]
        )

        load_btn = gr.Button("📦 Load Example")

    tool_input = gr.Code(
        label="Tool Input (JSON)",
        language="json",
        value=json.dumps(EXAMPLES[tool_names[0]], indent=2)
    )

    run_btn = gr.Button("🚀 Run Tool")

    output = gr.Code(
        label="Output",
        language="json"
    )

    # Actions
    load_btn.click(
        fn=load_example,
        inputs=tool_dropdown,
        outputs=tool_input
    )

    run_btn.click(
        fn=call_mcp_tool,
        inputs=[tool_dropdown, tool_input],
        outputs=output
    )


# ─────────────────────────────────────────────
# Run app
# ─────────────────────────────────────────────

if __name__ == "__main__":
    app.launch()