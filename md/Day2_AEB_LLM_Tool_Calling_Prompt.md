# Day 2｜LLM Tool Calling：AEB Analysis Agent v0.1

## 核心目标

在 Day 1 的 AEB Python Analyzer 基础上，把 `analyze_case()` 接入原生 LLM
Tool Calling。今天不引入
LangChain、LangGraph、MCP、RAG、数据库、FastAPI、前端、Multi-Agent 或
Memory。

最终跑通：

``` text
用户自然语言 → LLM → 判断是否调用工具 → analyze_aeb_case()
→ Day 1 Python 业务逻辑 → TTC/Risk/abnormal
→ 结构化 Tool Result → LLM 最终解释
```

验收标准：输入自然语言 AEB 场景后，LLM 能自行决定是否调用 Python
Tool；需要分析时调用，不需要工具时直接回答。

## 必须理解的原理

LLM 不会直接执行 Python 函数。模型负责理解请求、判断是否调用 Tool、选择
Tool、生成符合 Schema 的参数；Python
程序负责解析调用请求、真正执行函数、获得结果并把 Tool Result 返回给
LLM。

``` text
User → LLM → Function Call Request → Python Program
→ Execute Function → Function Result → LLM → Final Answer
```

核心认知：

> Tool Calling =
> 模型负责"决定调用什么以及传什么参数"，程序负责"真正执行"。

## 项目结构

``` text
AEB_agent/
├── .env
├── .gitignore
├── README.md
├── day01_python/
│   ├── main.py
│   ├── cases.json
│   └── test_main.py
└── day02_tool_calling/
    └── agent.py
```

## API 环境配置

安装：

``` bash
pip install openai python-dotenv
```

根目录 `.env`：

``` text
OPENAI_API_KEY=你的真实API_Key
```

真实 Key 不得写入代码、发给他人、截图公开或上传 GitHub。

`.gitignore` 至少包含：

``` text
.env
__pycache__/
.venv/
```

执行 `git status`，确认 `.env` 没有进入待提交文件。

Python 初始化：

``` python
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()
```

## 建立 Tool Interface

Day 1 已有内部函数：

``` python
analyze_case(case)
```

Day 2 建立面向 LLM 的接口，例如：

``` python
def analyze_aeb_case(
    distance_m: float,
    relative_speed_mps: float,
    brake_triggered: bool,
) -> dict:
    ...
```

内部继续调用 Day 1 `analyze_case()`：

``` text
LLM → analyze_aeb_case() → Day 1 analyze_case()
→ calculate_ttc()/classify_risk()/detect_abnormal()
→ 结构化结果
```

需要理解：Tool Interface 与内部业务实现不一定相同。保持 Tool
接口稳定，可以减少内部代码变化对 LLM 调用方式的影响。

## Tool Schema

为 `analyze_aeb_case` 定义 Schema，例如：

``` python
tools = [
    {
        "type": "function",
        "name": "analyze_aeb_case",
        "description": "Analyze an AEB scenario using TTC and braking status.",
        "parameters": {
            "type": "object",
            "properties": {
                "distance_m": {
                    "type": "number",
                    "description": "Distance to the target in meters"
                },
                "relative_speed_mps": {
                    "type": "number",
                    "description": "Closing relative speed in meters per second"
                },
                "brake_triggered": {
                    "type": "boolean",
                    "description": "Whether AEB braking was triggered"
                }
            },
            "required": [
                "distance_m",
                "relative_speed_mps",
                "brake_triggered"
            ],
            "additionalProperties": False
        },
        "strict": True
    }
]
```

必须能解释
`name`、`description`、`parameters`、`properties`、`required`、`additionalProperties`、`strict`
的作用，不能只复制代码。

## Tool Calling 闭环

### Step 1：发送自然语言请求

例如：

``` text
请分析这个 AEB 场景：
目标距离 8 米，相对速度 10 m/s，目前没有触发制动。
```

请求模型时同时提供 `tools`。

### Step 2：检查 Function Call

检查模型输出是否包含 Function Call，概念上类似：

``` python
for item in response.output:
    if item.type == "function_call":
        ...
```

获取 `tool name`、`arguments`、`call_id`。

Function Call Request 只是模型请求调用函数，不代表函数已经执行。

### Step 3：Python 真正执行 Tool

``` python
args = json.loads(item.arguments)
result = analyze_aeb_case(**args)
```

真正计算：

``` text
8m / 10m/s → TTC 0.8s → HIGH
→ brake_triggered=False → abnormal=True
```

### Step 4：把 Tool Result 返回 LLM

把 Python 的结构化结果作为 Function Call Output / Tool Result 返回模型：

``` text
LLM 请求调用 analyze_aeb_case
→ Python 执行
→ {"ttc":0.8,"risk":"HIGH","abnormal":true}
→ LLM 读取真实结果
→ 生成最终解释
```

TTC、Risk、abnormal 必须来自 Python Tool 的真实计算，而不是让 LLM
自己心算或猜测。

## 必做三个测试

### Test A：HIGH Risk，应调用 Tool

``` text
距离 8m，相对速度 10m/s，没有制动，请分析风险。
```

预期：

``` text
Tool Called = Yes
TTC = 0.8
Risk = HIGH
Abnormal = True
```

### Test B：LOW Risk，应调用 Tool

``` text
距离 50m，相对速度 5m/s，没有制动，请分析风险。
```

预期：

``` text
Tool Called = Yes
TTC = 10
Risk = LOW
Abnormal = False
```

### Test C：普通知识问题，不应调用 Tool

``` text
AEB 是什么意思？
```

预期：

``` text
Tool Called = No
LLM 直接回答
```

必须理解：Agent
不仅要会调用工具，也要知道什么时候不应该调用工具。该测试也是后续 Agent
Eval / Reliability 的基础。

## README 记录

增加：

``` text
## Day 2 - LLM Tool Calling

完成：
- 定义 analyze_aeb_case Tool
- 使用 JSON Schema 描述 Tool 参数
- LLM 可以自行决定是否调用 Tool
- Python 执行 Tool
- Tool Result 返回 LLM
- LLM 根据真实计算结果生成最终回答

测试：
1. HIGH risk case
2. LOW risk case
3. No-tool question

新理解：
- LLM 本身不会执行 Python Function
- Tool Calling 是模型决策 + 程序执行的协作
- Tool Interface 和内部业务代码可以分离
```

## Git 提交

完成后：

``` bash
git status
git add .
git commit -m "Day2 implement AEB tool calling"
git push
```

提交前必须确认 `.env` 和 API Key 没有进入 Git。保留 Commit ID 用于 Code
Review。

## 最终验收材料

1.  `day02_tool_calling/agent.py`
2.  至少一次真实 Tool Call 运行结果
3.  HIGH / LOW / No-Tool 三个测试结果
4.  README Day 2 记录
5.  Git Commit ID

## Day 2 学习重点

彻底理解并实现：

``` text
Prompt → LLM → Function Call → Python
→ Function Result → LLM → Final Answer
```

Day 2 完成之前不要扩展其他框架。优先得到一个真实、可运行、可测试、可提交
Git 的 AEB Tool Calling Demo。
