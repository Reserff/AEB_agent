import sys
import os
import json

from pathlib import Path

from dotenv import load_dotenv
# from openai import OpenAI
from zai import ZhipuAiClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from day01_python.main import analyze_case

load_dotenv()

# 初始化客户端
client = ZhipuAiClient(
    api_key=os.getenv("GLM_API_KEY"),  
    base_url=os.getenv("GLM_API_BASE_URL"),
    

)

MODEL=os.getenv("GLM_MODEL") # 模型名称


def analyze_aeb_case(
    distance_m: float,
    relative_speed_mps: float,
    brake_triggered: bool,
) -> dict:
    """Expose the Day 1 AEB analyzer through an LLM-friendly interface."""

    result = analyze_case(
        {
            "case_id": "AEB_TOOL_INPUT",
            "distance_m": distance_m,
            "relative_speed_mps": relative_speed_mps,
            "brake_triggered": brake_triggered,
        }
    )

    return {
        "ttc": result["ttc"],
        "risk": result["risk"],
        "abnormal": result["abnormal"],
    }
    
def run_agent(user_input: str) -> dict:

    if not MODEL:
        raise RuntimeError("GLM_MODEL is not configured")

    messages = [
        {
            "role": "user",
            "content": user_input,
        }
    ]

    # Step 1：把自然语言和 Tool Schema 发给模型
    first_response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=tools,
        tool_choice="auto",
    )

    assistant_message = first_response.choices[0].message
    tool_calls = assistant_message.tool_calls or []

    # 模型认为不需要工具，直接返回回答
    if not tool_calls:
        return {
            "tool_called": False,
            "tool_results": [],
            "answer": assistant_message.content or "",
        }

    # 把模型产生的 assistant/tool_calls 消息保留到上下文
    messages.append(
        assistant_message.model_dump(exclude_none=True)
    )

    tool_results = []

    # Step 2：检查模型请求调用的函数
    for tool_call in tool_calls:
        function_name = tool_call.function.name

        if function_name != "analyze_aeb_case":
            raise ValueError(
                f"Unsupported tool: {function_name}"
            )

        arguments = json.loads(
            tool_call.function.arguments
        )

        # Step 3：Python 真正执行工具
        result = analyze_aeb_case(**arguments)
        tool_results.append(result)

        # Step 4：把真实计算结果返回给模型
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(
                    result,
                    ensure_ascii=False,
                ),
            }
        )

    # 让模型读取 Python 的计算结果并生成最终解释
    final_response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=tools,
        tool_choice="auto",
    )

    final_message = final_response.choices[0].message

    return {
        "tool_called": True,
        "tool_results": tool_results,
        "answer": final_message.content or "",
    }
    
    
    
    

# 定义函数工具
tools = [
    {
        "type": "function",
        "function": {
            "name": "analyze_aeb_case",
            "description": (
                "Analyze an AEB scenario using distance, "
                "closing relative speed, and braking status."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "distance_m": {
                        "type": "number",
                        "description": "Distance to the target in meters",
                    },
                    "relative_speed_mps": {
                        "type": "number",
                        "description": (
                            "Closing relative speed in meters per second"
                        ),
                    },
                    "brake_triggered": {
                        "type": "boolean",
                        "description": "Whether AEB braking was triggered",
                    },
                },
                "required": [
                    "distance_m",
                    "relative_speed_mps",
                    "brake_triggered",
                ],
                "additionalProperties": False,
            },
         
        },
    }
]

def main() -> None:
    user_input = input("请输入问题：").strip()

    if not user_input:
        print("问题不能为空")
        return

    result = run_agent(user_input)

    print(
        "Tool Called:",
        "Yes" if result["tool_called"] else "No",
    )

    if result["tool_results"]:
        print(
            "Tool Result:",
            json.dumps(
                result["tool_results"],
                ensure_ascii=False,
                indent=2,
            ),
        )

    print("Final Answer:", result["answer"])


if __name__ == "__main__":
    main()