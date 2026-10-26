import logging
from typing import Any

import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from day02_tool_calling.agent import run_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# web应用本身
app = FastAPI(
    title="AEB Agent API",
    version="0.1.0",
)

@app.middleware("http")
async def trace_request(
    request: Request,
    call_next,
):
    # 每次请求生成唯一编号
    request_id = str(uuid.uuid4())

    # 将编号保存在当前请求对象中
    request.state.request_id = request_id

    # 记录开始时间
    start_time = time.perf_counter()

    # 继续执行后续接口逻辑
    response = await call_next(request)

    # 计算耗时，单位毫秒
    duration_ms = (
        time.perf_counter() - start_time
    ) * 1000

    # 将追踪信息放入响应头
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = (
        f"{duration_ms:.2f}"
    )

    logger.info(
        "request_id=%s method=%s path=%s "
        "status=%s duration_ms=%.2f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )

    return response

# 创建一个“请求数据模板”,所有传给 /analyze 的 JSON，保证请求至少包含合法的 prompt 字符串，都要按照这个模板检查。
class AnalyzeRequest(BaseModel):
    
    #表示 JSON 中必须有 prompt 字段，并且它应该是字符串。
    prompt: str = Field(
        # 字符串长度不能小于 1
        min_length=1,
        # description 不参与业务处理，主要显示在 FastAPI 自动生成的接口文档中
        max_length=4000,
        description="用户输入的 AEB 案例分析问题",
    ) 
    
    @field_validator("prompt", mode="before")
    @classmethod
    def strip_prompt(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

class AnalyzeResponse(BaseModel):
    tool_called: bool
    tool_results: list[dict]
    answer: str

 
# get——http方法；health——api路径
@app.get("/health")
def health() -> dict:
    return {
        "status": "ok"
    }
    
@app.post("/analyze", response_model=AnalyzeResponse)
@app.post(
    "/analyze",
    response_model=AnalyzeResponse,
)
def analyze(
    request: AnalyzeRequest,
    http_request: Request,
) -> AnalyzeResponse:

    try:
        result = run_agent(request.prompt)

        return AnalyzeResponse(**result)

    except Exception as exc:

        logger.exception(
            "AEB Agent analysis failed, request_id=%s",
            http_request.state.request_id,
        )

        raise HTTPException(
            status_code=500,
            detail="分析服务执行失败，请查看服务端日志",
        ) from exc