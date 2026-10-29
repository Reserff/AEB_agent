"""Run: python -m day07_batch.summarize_mcap FILE --output local_outputs/RUN"""
import argparse
import csv
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

from day07_batch.decode_mcap import iter_decoded
from day07_batch.events import prepare, add_sample, extract, export_events, scalar_fields
from day07_batch.field_profile import Profiler, dumps, write_csv
from day07_batch.signal_catalog import classify, EVENT_SIGNALS


def analyze(source: Path, output: Path, export_jsonl=False, tolerance_ms=100.0,
            window_ms=1000.0, max_gap_ms=500.0):
    if not source.is_file():
        raise FileNotFoundError(source)
    if not all(0 <= x < float("inf") for x in (tolerance_ms,window_ms,max_gap_ms)):
        raise ValueError("Time settings must be finite and nonnegative")
    # Output must be a fresh directory to prevent stale or accidentally overwritten results.
    output.mkdir(parents=True, exist_ok=False)
    (output / ".gitignore").write_text("*\n", encoding="utf-8")
    db = sqlite3.connect(output / "analysis.sqlite3")
    db.execute("PRAGMA cache_size=-32000")
    profiler = Profiler(db)
    prepare(db)
    overview = {}
    totals = Counter()
    presence = Counter()
    export = (output / "all_topics.jsonl").open("w", encoding="utf-8") if export_jsonl else None
    complete = False
    try:
        for row in iter_decoded(source):
            key = (row["topic"],row["schema_id"],row["channel_id"])
            info = overview.setdefault(key, dict(topic=row["topic"],schema_id=row["schema_id"],
                channel_id=row["channel_id"],schema=row["schema"],encoding=row["encoding"],
                message_count=0,decoded=0,failed=0,first_time_ns=row["log_time_ns"],
                last_time_ns=row["log_time_ns"],out_of_order=0,errors=Counter()))
            info["message_count"] += 1
            info["out_of_order"] += row["log_time_ns"] < info["last_time_ns"]
            info["first_time_ns"] = min(info["first_time_ns"],row["log_time_ns"])
            info["last_time_ns"] = max(info["last_time_ns"],row["log_time_ns"])
            totals[(row["topic"],row["schema_id"])] += 1
            if row.get("error"):
                info["failed"] += 1
                info["errors"][row["error"]] += 1
            else:
                info["decoded"] += 1
                profiler.add(row)
                presence.update((row["topic"],row["schema_id"],path,kind) for path,kind in row["presence"].items())
            add_sample(db,row)
            if export:
                export.write(dumps(row) + "\n")
            if (row["index"]+1) % 2000 == 0:
                db.commit()
                print(f"Processed {row['index']+1} messages", flush=True)
        db.commit()
        for info in overview.values():
            info["errors"] = dumps(info["errors"])
            duration = (info["last_time_ns"]-info["first_time_ns"])/1e9
            info["observed_hz"] = (info["message_count"]-1)/duration if duration else ""
        write_csv(output / "topic_overview.csv", overview.values())
        write_csv(output / "field_profile.csv", profiler.rows(totals))
        write_csv(output / "field_presence.csv", (dict(topic=t,schema_id=s,field_path=p,
            presence_status=k,message_count=n) for (t,s,p,k),n in sorted(presence.items())),
            ["topic","schema_id","field_path","presence_status","message_count"])
        metrics = extract(db,int(max_gap_ms*1e6))
        export_events(db,output,int(tolerance_ms*1e6),int(window_ms*1e6))
        evidence = window_evidence(output)
        def catalog():
            for row in profiler.rows(totals):
                item = classify(row)
                values = evidence.get((row["topic"],row["field_path"]), Counter())
                item["matched_window_samples"] = sum(values.values())
                item["window_distinct_values"] = len(values)
                item["window_top_values"] = dumps(values.most_common(5))
                yield item
        write_csv(output / "signal_catalog.csv", catalog())
        report(output, overview, profiler, totals, metrics, tolerance_ms,window_ms,max_gap_ms,db)
        complete = True
        return dict(messages=sum(totals.values()),topics=len({k[0] for k in overview}),
                    decoded=sum(x["decoded"] for x in overview.values()),
                    failed=sum(x["failed"] for x in overview.values()),**metrics)
    finally:
        if export:
            export.close()
        db.close()
        (output / "run_status.json").write_text(dumps(dict(complete=complete,
            source=str(source.resolve()),time_basis="MCAP log_time nanoseconds",
            tolerance_ms=tolerance_ms,window_ms=window_ms,max_gap_ms=max_gap_ms)),encoding="utf-8")


def window_evidence(output):
    evidence = defaultdict(Counter)
    with (output / "event_context.csv").open(encoding="utf-8-sig",newline="") as stream:
        for row in csv.DictReader(stream):
            if row["matched"] == "True":
                for path,value in scalar_fields(json.loads(row["values"])).items():
                    evidence[(row["topic"],path)][dumps(value)] += 1
    return evidence


def window_report(output):
    """Small human-readable before/during/after table; retains raw units."""
    lines = ["", "### 事件窗口实际观测", "", "数值顺序为事件前窗口 / 事件时刻 / 事件后窗口；均为原值，单位待确认。窗口间变化不能替代连续波形判断。", "",
             "| 候选ID | Topic:字段 | 前 / 当时 / 后 |", "|---|---|---|"]
    observations = defaultdict(dict)
    with (output / "event_context.csv").open(encoding="utf-8-sig",newline="") as stream:
        for row in csv.DictReader(stream):
            if row["matched"] != "True":
                continue
            for path,value in scalar_fields(json.loads(row["values"])).items():
                name = path.split(".")[-1]
                selected = (row["topic"] == "/mcu_decision_data" and name in
                    {"Obstacle_PosX","Obstacle_TTC","vehspd_mps","FVC_AEBReq"})
                selected |= (row["topic"] in {"/vse_data","/func_output"} and
                    any(token in name.lower() for token in ("aeb", "ax", "accel", "vehspd")))
                if selected and isinstance(value,(int,float,bool)):
                    observations[(int(row["event_id"]),row["topic"],path)][int(row["offset_ns"])] = value
    for (event,topic,path), values in sorted(observations.items()):
        # Include all principal target traces, and only changing response/output traces.
        if topic != "/mcu_decision_data" and len(set(values.values())) <= 1:
            continue
        texts = []
        for offset in (-1,0,1):
            matches = [v for k,v in values.items() if (k > 0)-(k < 0) == offset]
            texts.append(format(matches[0],".6g") if matches else "无匹配")
        lines.append(f"| {event} | {topic}:{path} | {' / '.join(texts)} |")
    return lines


def report(output,overview,profiler,totals,metrics,tolerance,window,gap,db):
    lines = ["# Day07 本地 MCAP 分析", "", "## 已验证的读取结果", "",
        f"- 实际读取 {sum(totals.values())} 条消息，{len({k[0] for k in overview})} 个 Topic，{len(overview)} 个 Channel/Schema 组合。",
        f"- 解码成功 {sum(x['decoded'] for x in overview.values())} 条；失败 {sum(x['failed'] for x in overview.values())} 条。",
        "- 逐条解码，无网络调用；完整 JSONL 按需导出。SQLite 保存统计及业务 Topic 数据，供本地按时间检索。",
        "", "## 帧与候选事件", "",f"- 帧审计：`{dumps(metrics)}`。",
        "- 候选数是原始信号切换记录数，不是独立制动次数；同一时刻多个信号切换分别记录。",
        "- 按记录时间排序；连续相同 frame_id 合并为帧段。帧内有冲突的信号不参与该帧切换判断，缺失/解码失败中断连续性。",
        f"- 重现帧号视为可能复用/复位并断开连续性；超过 {gap} ms 的间隔不跨越推断切换。首个非零值不算切换。",
        "", "| 信号 | 切换候选数 |", "|---|---:|"]
    lines.extend(f"| {field} | {n} |" for field,n in db.execute("SELECT field,count(*) FROM events GROUP BY field"))
    lines += ["", "## 信号筛选依据", "", "核心候选要求观测到状态/请求取值变化；辅助候选要求实际变化且能提供目标、阈值、车辆上下文。仅名称相关但含义不明的字段列为待确认。所有分类为初筛。", "",
              "| Topic | 画像字段数 | 有变化字段数 | 核心信号数 |", "|---|---:|---:|---:|"]
    topic_stats = defaultdict(Counter)
    notable, boundaries = [], []
    for row in profiler.rows(totals):
        cat = classify(row)
        topic_stats[row["topic"]]["fields"] += 1
        topic_stats[row["topic"]]["changed"] += row["changed"]
        topic_stats[row["topic"]]["core"] += cat["category"] == "核心信号"
        name = row["field_path"].split(".")[-1]
        if name in EVENT_SIGNALS or "可能边界" in row["flags"]:
            notable.append(f"- `{row['topic']}:{row['field_path']}`：范围 {row['minimum']}～{row['maximum']}，不同值 {row['distinct_values']}，非零出现 {row['nonzero_count']} 次，常见值 `{row['top_values']}`。{row['flags']}")
        if row["distinct_values"] == 1 and row["data_type"] not in ("array","object") and "[]" not in row["field_path"]:
            boundaries.append(f"- `{row['topic']}:{row['field_path']}`：`{row['top_values']}`。")
    lines.extend(f"| {topic} | {s['fields']} | {s['changed']} | {s['core']} |" for topic,s in sorted(topic_stats.items()))
    lines += ["", "优先使用 `/mcu_decision_data` 的实际变化建立候选，再关联 `/mcu_environment_data`、`/vse_data`、`/func_output`、`/func_event_info`、`/jac_mcm_callback`；可视化 Topic 已解码，其数组统计以 [] 路径汇总，不据此识别独立目标。", "", *notable,
        "", "## 时间关联与事件前后核查", "",
        f"以 MCAP log_time（格式定义为纳秒）为唯一对齐基准，容差 {tolerance} ms；在事件前 {window} ms、事件时刻、后 {window} ms 各取每个业务 Topic 最近样本。",
        "`event_context.csv` 提供实际样本时间、带符号偏差、匹配成功与否及标量原值（包括距离、TTC、速度、加速度候选）；没有样本则明确留空。",
        "这只是记录时间关联，不是内部算法执行时序。内部 timestamp、ROS header 时间、速度/加速度/距离单位及枚举尚未校准。不能认定车辆已执行请求，也不能据此做误触发/漏触发分类。",
        "", "## 固定值及数据限制", "",
        f"共有 {len(boundaries)} 个非数组标量字段在本段固定。固定值不等于无用，完整条目见 field_profile.csv；以下展示前 20 项：", *boundaries[:20],
        "", "- Obstacle_PosX=200、Obstacle_TTC=20 仅标记可能边界/占位，未删除，也不以此推断无风险。",
        "- FVC_ObjValid 不用于核心过滤。",
        "- Protobuf 隐式标量的显式设置/默认值无法从解码值区分；有 presence 的字段按实际 presence 保留，详见 field_presence.csv。",
        "- 数组路径 [] 汇总所有元素，occurrence_count 可大于消息数；changed 代表有不同取值，不保证同一目标随时间变化。",
        "- 本版本画像覆盖实际出现的结构、数组长度、叶字段；未出现的可选子消息不凭空生成其叶字段。",
        "- signal_catalog.csv 的窗口取值统计来自实际匹配样本；同一物理消息可能被多个候选窗口引用，不能把窗口样本数当独立消息数。",
        *window_report(output),
        "", "## 下一步", "", "1. 用协议确认状态码、制动请求枚举、单位、坐标系、目标身份和有效性规则。",
        "2. 查看 frame_audit.csv 的重复/冲突帧；确认 frame_id 复用规则及源时间戳单位，校准 Topic 时钟偏差。",
        "3. 以 event_candidates.csv 和 event_context.csv 构建本地事件窗口工具；协议确认后再合并制动事件并核对车辆响应。",
        "4. 保持实车数据与已有大模型调用入口隔离；本次没有向模型服务发送数据。"]
    (output / "analysis_summary.md").write_text("\n".join(lines)+"\n",encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--export-jsonl",action="store_true")
    parser.add_argument("--tolerance-ms",type=float,default=100)
    parser.add_argument("--window-ms",type=float,default=1000)
    parser.add_argument("--max-gap-ms",type=float,default=500)
    args = parser.parse_args()
    print(dumps(analyze(args.file,args.output,args.export_jsonl,args.tolerance_ms,args.window_ms,args.max_gap_ms)))


if __name__ == "__main__":
    main()
