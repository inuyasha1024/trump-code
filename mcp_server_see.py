#!/usr/bin/env python3
"""SSE 版 MCP Server — 供远程访问用"""

import json
import os
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import uvicorn

# 直接复用原来的逻辑
from mcp_server import handle_request

app = FastAPI()

@app.post("/mcp")
async def mcp_endpoint(request: Request):
    body = await request.json()
    response = handle_request(body)
    return response or {}

@app.get("/sse")
async def sse_endpoint(request: Request):
    """SSE 长连接入口"""
    async def event_stream():
        # 发送初始化握手
        init = handle_request({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {}
        })
        yield f"data: {json.dumps(init)}\n\n"
        
        # 保持连接
        while True:
            if await request.is_disconnected():
                break
            await asyncio.sleep(15)
            yield ": ping\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
