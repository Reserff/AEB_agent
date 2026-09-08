# Day 1｜60～80 分钟任务：将 AEB Analyzer 改造成 Agent 可调用的结构化工具

## 目标

在前一阶段已经能够完成 AEB Case 分析的基础上，对程序进行一次关键改造：

> **将业务分析结果与终端打印展示分离，让 `analyze_case()`
> 返回结构化数据，而不是直接负责 `print()`。**

这样做的目的，是让今天编写的 Python 分析函数具备未来被 LLM / Agent 作为
Tool 调用的基础。

## 为什么要改造

如果未来由 LLM 调用 AEB 分析程序，仅返回或打印：

``` python
print("HIGH")
```

并不适合作为 Agent 的工具接口。

Agent 更适合接收结构清晰、字段明确的数据，例如：

``` python
{
    "case_id": "AEB_002",
    "ttc": 0.8,
    "risk": "HIGH",
    "abnormal": True
}
```

结构化结果便于 LLM
理解每个字段，并根据工具执行结果继续进行判断、解释或后续工具调用。

## 核心改造要求

修改此前实现的 `analyze_case()`，使其：

1.  接收一个 AEB Case 作为输入。
2.  调用已有的 TTC、风险等级和异常检测逻辑。
3.  **返回结构化数据（如 `dict`）**。
4.  **不要在 `analyze_case()` 内直接负责最终的人类可读输出。**

推荐返回的数据至少包含：

``` python
{
    "case_id": "...",
    "ttc": ...,
    "risk": "...",
    "abnormal": ...
}
```

## 分离业务逻辑与展示逻辑

程序结构应逐渐形成：

``` text
输入 case
    ↓
analyze_case()
    ↓
返回结构化 dict
    ↓
display_result()
    ↓
打印人类可读结果
```

也就是说：

-   `analyze_case()`：负责分析和返回数据。
-   `display_result()`：负责将分析结果展示给人。

不要让核心业务分析函数和终端打印逻辑过度耦合。

## 需要建立的工程意识

这一阶段需要开始理解：

> **业务逻辑、数据接口、展示层应该尽量分离。**

这样设计不仅是为了代码整洁，更是在为后续 Agent Tool 做准备。

未来的调用链大致会变成：

``` text
LLM
 ↓
判断是否需要调用 Tool
 ↓
向 Tool 传入结构化参数
 ↓
执行 Python Function
 ↓
Function 返回结构化结果
 ↓
LLM 读取结果并继续决策或生成最终回答
```

因此，今天实现的 `analyze_case()` 后续可以进一步封装为真正的 **Agent
Tool**。

## 本阶段验收标准

完成 60～80 分钟任务时，应至少满足：

-   `analyze_case()` 不再只通过 `print()` 输出分析结果。
-   `analyze_case()` 能返回一个结构化结果。
-   返回结果至少包含 `case_id`、`ttc`、`risk`、`abnormal`。
-   TTC、风险判断、异常判断仍然由已有业务逻辑完成。
-   人类可读输出与分析逻辑分离。
-   可以单独使用 `display_result()`（或类似函数）负责打印结果。
-   程序整体仍然能够正常运行并得到与改造前一致的业务判断结果。
-   能解释为什么 Agent Tool 更适合返回结构化数据，而不是只进行
    `print()`。

## 本阶段真正学习的内容

重点不是增加新的 AEB 算法，而是完成一次从普通脚本向 Agent Tool
接口思维的转换：

``` text
普通脚本思维
函数 → print 给人看

        ↓

Agent 工程思维
函数 → 返回结构化数据 → 其他程序/LLM 使用
```

这一步是后续学习 **LLM Tool Calling / Function Calling** 的直接基础。

## 与下一阶段的关系

完成本阶段后，`analyze_case()` 已经具备一个 Agent Tool 的雏形。

后续可以继续推进：

``` text
用户自然语言请求
        ↓
       LLM
        ↓
决定是否调用 analyze_case Tool
        ↓
传入 AEB Case 参数
        ↓
Python 执行实际分析
        ↓
返回结构化结果
        ↓
LLM 根据结果生成解释或继续决策
```

因此，本阶段不要急着加入 LangChain、LangGraph、MCP
等框架。当前重点是先理解并实现一个清晰、可复用、可被其他程序调用的
Python 工具接口。
