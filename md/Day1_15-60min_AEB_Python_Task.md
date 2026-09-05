# Day 1｜15～60 分钟任务：AEB Python 基础分析器

## 目标

完成一个最小可运行的 AEB Case 分析程序，用于检验并训练 Python
基础工程能力。当前阶段先不要直接获取完整答案，优先自己实现；允许查资料或使用
AI 辅助，但需要理解最终代码。


## 程序流程

在 `main.py` 中实现以下流程：

``` text
读取 cases.json
    ↓
遍历每个 case
    ↓
计算 TTC
    ↓
判断风险等级
    ↓
检测异常 Case
    ↓
打印分析结果
```

### 1. TTC 计算

公式：

``` text
TTC = distance / relative_speed
```

同时必须考虑 `relative_speed <= 0`
的情况，不能让程序因除零或不合理输入直接崩溃。

### 2. 风险等级

按照 TTC 判断：

``` text
TTC < 1.5          → HIGH
1.5 <= TTC < 3     → MEDIUM
TTC >= 3           → LOW
```

### 3. 异常 Case 判断

满足以下条件时标记为异常：

``` text
Risk == HIGH
且
brake_triggered == false
    ↓
ABNORMAL
```

其他情况标记为正常。

## 预期输出示例

``` text
Case: AEB_001
TTC: 2.33 s
Risk: MEDIUM
Status: NORMAL

Case: AEB_002
TTC: 0.80 s
Risk: HIGH
Status: ABNORMAL

Case: AEB_003
TTC: 10.00 s
Risk: LOW
Status: NORMAL
```

## 代码结构要求

不能把所有逻辑全部写进 `main()`。

至少拆分出以下函数：

``` python
def load_cases(...):
    ...

def calculate_ttc(...):
    ...

def classify_risk(...):
    ...

def detect_abnormal(...):
    ...

def analyze_case(...):
    ...
```

尽量为函数加入 Python Type Hints，例如：

``` python
def calculate_ttc(distance: float, relative_speed: float) -> float:
    ...
```

## 本阶段验收标准

完成后至少应满足：

-   `cases.json` 可以被程序正确读取。
-   能遍历所有 AEB Case。
-   能正确计算 TTC。
-   能按照规定阈值划分 `HIGH / MEDIUM / LOW`。
-   能识别 `HIGH + brake_triggered == false` 的异常 Case。
-   能输出每个 Case 的 `case_id`、TTC、风险等级和状态。
-   代码进行了函数拆分，而不是把全部逻辑堆在 `main()` 中。
-   尽量使用 Type Hints。
-   已处理 `relative_speed <= 0` 的边界情况，程序不会因此直接崩溃。

## 学习原则

本任务的重点不是 TTC 算法本身，而是通过一个熟悉的 AEB 场景检验 Python
基础，包括 JSON 处理、函数设计、条件判断、异常/边界处理、Type Hints
和模块化思维。

先自己实现，不要直接照抄完整答案。可以查资料、询问
AI，但最终需要知道代码为什么这样写，以及出现问题时能够定位。
