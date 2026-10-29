"""Frame-run grouping and raw transitions, followed by disk-indexed alignment."""
import json
from collections import Counter

from day07_batch.field_profile import dumps, flatten, write_csv
from day07_batch.signal_catalog import EVENT_SIGNALS, BUSINESS_TOPICS


def scalar_fields(data):
    return {p: v for p, t, v in flatten(data) if t not in ("object", "array") and "[]" not in p}


def prepare(db):
    db.executescript('''CREATE TABLE samples(id INTEGER PRIMARY KEY,topic TEXT,schema_id INT,
        t INTEGER,frame TEXT,data TEXT,error TEXT);
        CREATE INDEX sample_time ON samples(topic,t,id);
        CREATE TABLE frames(id INTEGER PRIMARY KEY,topic TEXT,schema_id INT,t INTEGER,last_t INTEGER,
        frame TEXT,messages INT,conflicts TEXT,data TEXT,reappeared INT);
        CREATE TABLE seen_frames(topic TEXT,schema_id INT,frame TEXT,PRIMARY KEY(topic,schema_id,frame));
        CREATE TABLE events(id INTEGER PRIMARY KEY,t INTEGER,field TEXT,old TEXT,new TEXT,
        frame TEXT,frame_messages INT,previous_t INTEGER,kind TEXT);
    ''')


def add_sample(db, row):
    if row["topic"] not in BUSINESS_TOPICS:
        return
    data = row.get("data")
    frame = None if data is None else data.get("frame_id")
    db.execute("INSERT INTO samples VALUES(?,?,?,?,?,?,?)", (row["index"], row["topic"], row["schema_id"],
        row["log_time_ns"], None if frame is None else dumps(frame),
        None if data is None else dumps(data), row.get("error")))


def extract(db, max_gap_ns=500_000_000):
    """Collapse consecutive equal frame IDs. Conflicts break that signal's continuity.

    Reappearing IDs may indicate reset/reuse, so start a new run, flag and break continuity.
    Missing frame IDs remain individual observations. No initial nonzero value is an event.
    """
    metrics = Counter()
    current = None
    previous = {}

    def flush(group):
        if group is None:
            return
        frame_key = (group["topic"], group["schema_id"], group["frame"])
        reappeared = bool(group["frame"] is not None and db.execute(
            "SELECT 1 FROM seen_frames WHERE topic=? AND schema_id=? AND frame=?", frame_key).fetchone())
        if group["frame"] is not None:
            db.execute("INSERT OR IGNORE INTO seen_frames VALUES(?,?,?)", frame_key)
        metrics["frame_runs"] += 1
        metrics["duplicate_messages"] += group["messages"] - 1
        metrics["conflicting_frame_runs"] += bool(group["conflicts"])
        metrics["reappeared_frame_runs"] += reappeared
        db.execute("INSERT INTO frames(topic,schema_id,t,last_t,frame,messages,conflicts,data,reappeared) VALUES(?,?,?,?,?,?,?,?,?)",
            (group["topic"],group["schema_id"],group["t"],group["last_t"],group["frame"],group["messages"],
             dumps(sorted(group["conflicts"])),dumps(group["data"]),reappeared))
        if reappeared:
            previous.clear()
        for field in sorted(set(previous) | set(group["data"])):
            if field.split(".")[-1] not in EVENT_SIGNALS:
                continue
            value = group["data"].get(field)
            if field in group["conflicts"] or value is None:
                previous.pop(field, None)
                continue
            if field in previous:
                old, old_t, sid = previous[field]
                if old != value and sid == group["schema_id"] and group["t"] - old_t <= max_gap_ns:
                    db.execute("INSERT INTO events(t,field,old,new,frame,frame_messages,previous_t,kind) VALUES(?,?,?,?,?,?,?,?)",
                        (group["t"],field,dumps(old),dumps(value),group["frame"],group["messages"],old_t,
                         "state_transition" if field.endswith("AEB_Sts") else "request_value_transition"))
                    metrics["candidate_transitions"] += 1
            previous[field] = (value, group["last_t"],group["schema_id"])

    for _, topic, sid, t, frame, encoded, error in db.execute(
        "SELECT * FROM samples WHERE topic='/mcu_decision_data' ORDER BY t,id"
    ):
        if error:
            flush(current)
            current = None
            previous.clear()
            metrics["decode_gaps"] += 1
            continue
        data = scalar_fields(json.loads(encoded))
        same = current and frame is not None and (frame,sid) == (current["frame"],current["schema_id"]) and t-current["last_t"] <= max_gap_ns
        if same:
            current["conflicts"].update(k for k in set(data) | set(current["data"]) if data.get(k) != current["data"].get(k))
            current["data"] = data
            current["last_t"] = t
            current["messages"] += 1
        else:
            flush(current)
            current = dict(topic=topic,schema_id=sid,t=t,last_t=t,frame=frame,messages=1,conflicts=set(),data=data)
    flush(current)
    db.commit()
    return metrics


def export_events(db, directory, tolerance_ns, window_ns):
    def events():
        for eid,t,field,old,new,frame,n,previous_t,kind in db.execute("SELECT * FROM events ORDER BY t,id"):
            yield dict(event_id=eid,log_time_ns=t,event_type=kind,field_path=field,
                previous_value=old,current_value=new,frame_id=frame,frame_message_count=n,
                previous_log_time_ns=previous_t,observation_interval_ns=t-previous_t,
                interpretation="原始码变化候选；不是已执行制动或独立制动事件")
    write_csv(directory / "event_candidates.csv", events(), ["event_id","log_time_ns","event_type","field_path",
        "previous_value","current_value","frame_id","frame_message_count","previous_log_time_ns","observation_interval_ns","interpretation"])
    def contexts():
        for eid,t,*_ in db.execute("SELECT * FROM events ORDER BY t,id"):
            for offset in (-window_ns, 0, window_ns):
                target = t + offset
                for topic in sorted(BUSINESS_TOPICS):
                    # Indexed predecessor/successor lookup, bounded memory and explicit signed delta.
                    choices = []
                    for op, order in (("<=", "DESC"), (">=", "ASC")):
                        row = db.execute(f"SELECT t,frame,data,error FROM samples WHERE topic=? AND t {op} ? ORDER BY t {order},id {order} LIMIT 1", (topic,target)).fetchone()
                        if row:
                            choices.append(row)
                    match = min(choices, key=lambda r: (abs(r[0]-target),r[0])) if choices else None
                    valid = match is not None and abs(match[0]-target) <= tolerance_ns
                    yield dict(event_id=eid,event_time_ns=t,offset_ns=offset,topic=topic,
                        matched=valid and not match[3],sample_time_ns=match[0] if valid else "",
                        delta_ns=match[0]-target if valid else "",frame_id=match[1] if valid else "",
                        values=match[2] if valid and not match[3] else "",
                        note=(match[3] or "MCAP记录时间近邻；设备时钟偏移与传输延迟未校准") if valid else "容差内无样本")
    write_csv(directory / "event_context.csv", contexts(), ["event_id","event_time_ns","offset_ns","topic","matched","sample_time_ns","delta_ns","frame_id","values","note"])
    write_csv(directory / "frame_audit.csv", (dict(zip(["frame_run_id","topic","schema_id","first_time_ns","last_time_ns","frame_id","message_count","conflicting_fields","last_values","reappeared"], row)) for row in db.execute("SELECT * FROM frames")))
