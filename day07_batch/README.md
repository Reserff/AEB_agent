# Day07：本地 MCAP 解码、画像和候选事件

此流程与 Day01–Day06 的 API/大模型入口独立，不调用外部模型，也不推断制动已经执行。
原有 `loader.py` 的 CSV/JSON 接口保留；原有两个 inspect 脚本继续用于快速查目录、看字段定义。

## PowerShell 运行

在仓库根目录执行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-day07.txt

$runDir = "local_outputs/day07_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
.\.venv\Scripts\python.exe -m day07_batch.summarize_mcap `
  "..\data_ev\2026_10_14\mcu_2026-10-14_10-43-22_data.mcap" `
  --output $runDir `
  --tolerance-ms 100 `
  --window-ms 1000 `
  --max-gap-ms 500

.\.venv\Scripts\python.exe -m pytest -q
```

需要完整解码导出时，在运行命令最后增加 `--export-jsonl`。
统计不依赖 JSONL。输出目录必须尚不存在，避免误覆盖旧结果。检查 `run_status.json` 中的 `complete`；
它表示流程完成，不代表所有消息成功解码，失败数应查看 `topic_overview.csv`。
遇到 MCAP 容器损坏无法继续读取时会报错并留下 `complete=false`，不把部分读取冒充完整结果。

## 通俗理解整个流程

1. **逐条打开包裹**：`decode_mcap.py` 根据消息对应的 Schema 选择 Protobuf 或 ROS1 解码器。
   Protobuf 使用独立描述符池，支持依赖和嵌套类型；ROS1 使用 MCAP 官方支持包内的动态消息实现。
   一条消息解码失败会记录原因并继续处理下一条。读文件按物理顺序，不要求 Summary 索引。
2. **给每个字段做账本**：`field_profile.py` 把嵌套字段写成完整路径，精确记录取值次数。
   账本存到本地 SQLite，避免在内存保存全部消息或高基数取值集合。
3. **合并同一帧的重复记录**：`events.py` 用 SQLite 按记录时间排序，连续相同帧号形成一个帧段。
   相同帧内有冲突则跳过该信号的切换判断；缺失、解码失败、Schema 变化、长时间断档不跨越推断。
   帧号重现可能是复用/复位，单独审计并中断连续性。首次观测非零值不是一次切换。
4. **找原始码变化**：比较相邻有效帧的状态/请求值。一次状态切换就是一条候选，多个候选可能属于同一制动过程。
5. **查前后上下文**：在候选前后指定窗口时间，按容差匹配六个业务 Topic 的最近样本。
   保留匹配样本的实际时间和偏差，包括嵌套数组原值。记录时间接近不代表因果关系。
6. **初筛信号**：`signal_catalog.py` 结合实际变化、候选业务用途分为四类；
   目录还附有真实事件窗口中的取值统计，支持人工核查关联。
   `summarize_mcap.py` 串起上述步骤并生成报告。

## 输出含义

| 文件 | 用途 |
|---|---|
| `topic_overview.csv` | 每个 Topic/Channel/Schema 的消息数、解码成败、时间范围、观测频率 |
| `field_profile.csv` | 所有观测字段的精确画像，包括结构节点和数组长度 |
| `field_presence.csv` | Protobuf 的 presence 信息；隐式标量明确标记无法区分默认和显式设置 |
| `signal_catalog.csv` | 信号分类、依据、待确认项、事件窗口取值证据 |
| `event_candidates.csv` | 原始状态码/请求码切换；不是已执行制动的事件次数 |
| `event_context.csv` | 每个候选的前/当时/后跨 Topic 原始数据、时间偏差、匹配状态 |
| `frame_audit.csv` | 帧段、重复条数、帧内冲突、重现帧号 |
| `analysis_summary.md` | 实际统计、筛选依据、事件窗口对照、限制和下一步 |
| `all_topics.jsonl` | 可选；含 Topic、时间、Schema、解码值及 presence/错误 |
| `analysis.sqlite3` | 本地精确直方图和按时间检索业务消息的中间库 |
| `run_status.json` | 完成状态及本次时间参数 |

CSV 使用 UTF-8 BOM；纳秒时间戳建议按文本导入 Excel，以免表格软件损失整数精度。
如果公司终端对不同程序实施透明加密，读取程序须具有相应权限；不要通过重命名等手段绕过保护。

## 统计口径与限制

- `message_count` 包含解码失败消息；`messages_present` 只计成功解码且包含字段的消息。
- `occurrence_count` 是字段值出现次数；数组字段路径用 `[]` 汇总，可能远大于消息数。
  数组中值不同不等于同一目标发生变化，不自动按数组下标认定目标身份。
- `nonzero_ratio` 分母是数值出现次数；不同取值、最常见值在 SQLite 中精确统计，不抽样。
  整数字段最小/最大值从原始直方图恢复，保留 64 位整数精度。
- 不会凭空补出从未出现的可选子消息的叶字段；数组长度为零也会留下结构信息。
- Protobuf 枚举保留数字，bytes 用 base64，非有限浮点用显式标记对象，JSONL 不输出非法 NaN。
- `changed` 表示出现不同取值；它不代表时间变化次数，更不代表实际制动次数。
- `window_*` 统计是候选窗口引用数，重叠窗口可能引用同一条消息，不可当独立样本数。
- `Obstacle_PosX=200`、`Obstacle_TTC=20` 保留并标记，不自动过滤；`FVC_ObjValid` 不作核心条件。
- 对齐基准只用 MCAP `log_time`，按格式定义为纳秒。源 timestamp、单位、枚举、方向和坐标系待协议确认。
- 容差默认 100 ms 是可配置的初始分析参数，不代表已测得传输延迟或时钟精度。
- 帧合并依赖记录中 frame_id 的可信度，隐式默认帧号与真实零帧号无法仅凭 Protobuf 区分。
- 完整 JSONL、精确取值账本可能明显大于 MCAP；默认关闭 JSONL。内存主要随单条消息大小及字段种类增长。
- 本地结果和原始数据受 `.gitignore` 保护，输出目录自身也生成忽略规则；不要强制添加或对外上传。

测试只动态构造虚拟协议和数据，覆盖两种编码、坏消息、默认值、嵌套数组、边界值、缺失、重复帧、
帧内冲突、帧号复用、时间断档、时间匹配和可选 JSONL。没有提交实车夹具。
