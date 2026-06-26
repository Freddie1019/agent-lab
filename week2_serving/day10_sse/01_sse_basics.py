"""
任务 1：最简 SSE 服务
理解 SSE 的事件帧格式
"""
import asyncio
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()

async def number_stream():
    """每秒产出一个数字"""
    for i in range(10):
        # ★ SSE 事件帧格式：data: xxx\n\n
        yield f"data: {i} \n\n"
        await asyncio.sleep(1)

async def event_stream():
    """ 带事件类型的流 """
    event = [
        ("thought", "我开始思考问题..."),
        ("tool_call", "调用 web_search"),
        ("tool_result", "找到 3 个结果"),
        ("answer", "基于搜索结果..."),
        ("done", "[DONE]"),
    ]
    for event_type, content in event:
        yield f"event: {event_type}\ndata: {content}\n\n"
        await asyncio.sleep(0.8)
    
@app.get("/stream/numbers")
async def stream_number():
    return StreamingResponse(
        number_stream(),
        media_type="text/event-stream",
    )

@app.get("/stream/events")
async def stream_event():
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
    )
