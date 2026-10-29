# AEB Insight Agent 开发进度

## 当前阶段
Day07：本地 MCAP 解码、字段画像与 AEB 候选事件链路

## 已完成
- Day01：AEB TTC 分析工具
- Day02：GLM Tool Calling
- Day03：Agent 基础评测
- Day04：FastAPI 接口
- Day05：Middleware 请求追踪与异常日志
- Day06：环境配置检查与 `/ready` 接口

## Day07 已实现
- [x] 保留 CSV/JSON 文件解析、Pydantic 校验及 Day01 集成
- [x] Protobuf / ROS1 消息流式解码及可选本地 JSONL 导出
- [x] SQLite 精确字段画像、默认值/边界值标记和信号初筛
- [x] 重复帧审计、原始码切换候选、可配置跨 Topic 时间匹配
- [x] 本地报告及输出目录 Git 忽略保护
- [x] 全量 pytest：29 个测试通过（模拟数据；2 条既有依赖弃用警告）

运行命令、文件说明与统计口径见 `day07_batch/README.md`。
实车统计和报告只保存在忽略目录 `local_outputs/`，不写入版本库。

## Day07 剩余确认

- [ ] 状态码、请求枚举、单位、坐标方向和目标有效性协议
- [ ] 源时间戳单位、跨 Topic 时钟偏差与 frame_id 复用规则
- [ ] 在协议确认后合并独立制动事件并验证车辆响应；当前只输出候选

## 下一阶段
Day08：FastAPI 文件上传与批量 AEB 分析接口

## 备注
以 GitHub 最新代码和测试结果为准，未完成的任务不得跳过。
