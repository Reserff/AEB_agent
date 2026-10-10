from fastapi import FastAPI
from pydantic import BaseModel, Field

# web应用本身
app = FastAPI(
    title="AEB Agent API",
    version="0.1.0",
)

# 创建一个“请求数据模板”,所有传给 /analyze 的 JSON，都要按照这个模板检查。
class AnalyzeRequest(BaseModel):
    
    #表示 JSON 中必须有 prompt 字段，并且它应该是字符串。
    prompt: str = Field(
        # 字符串长度不能小于 1
        min_length=1,
        # description 不参与业务处理，主要显示在 FastAPI 自动生成的接口文档中
        description="用户输入的 AEB 案例分析问题",
    )
# get——http方法；health——api路径
@app.get("/health")
def health() -> dict:
    return {
        "status": "ok"
    }
    
@app.post("/analyze")
# 收到 JSON 后，先按照 AnalyzeRequest 检查；校验通过后，才执行 analyze()
def analyze(request: AnalyzeRequest):
    return {
        "message": "请求参数校验通过",
        "prompt": request.prompt,
    }