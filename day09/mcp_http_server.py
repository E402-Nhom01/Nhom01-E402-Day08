"""
mcp_http_server.py — MCP HTTP Server (FastAPI)

Expose:
    GET  /tools        → list available tools
    POST /tools/call   → call a tool

Run:
    uvicorn mcp_http_server:app --reload
"""

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any

from mcp_server import dispatch_tool, list_tools

app = FastAPI(title="Mock MCP Server", version="1.0")


# ─────────────────────────────────────────────
# Request Schema
# ─────────────────────────────────────────────

class ToolCallRequest(BaseModel):
    tool_name: str
    tool_input: Dict[str, Any]


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "message": "MCP Server is running",
        "endpoints": {
            "GET /tools": "List available tools",
            "POST /tools/call": "Execute a tool",
        },
    }


@app.get("/tools")
def get_tools():
    return {
        "tools": list_tools(verbose=True)
    }


@app.post("/tools/call")
def call_tool(req: ToolCallRequest):
    result = dispatch_tool(req.tool_name, req.tool_input)
    return result


# ─────────────────────────────────────────────
# Health check (nice for demo)
# ─────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}