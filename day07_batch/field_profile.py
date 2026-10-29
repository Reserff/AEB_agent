"""Exact disk-backed value histograms; array elements use [] paths."""
import csv
import json
import sqlite3
from collections import Counter


def dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def flatten(data, path=""):
    if isinstance(data, dict):
        if path:
            yield path, "object", "<object>"
        for key, value in data.items():
            yield from flatten(value, f"{path}.{key}".lstrip("."))
    elif isinstance(data, list):
        yield path, "array", "<array>"
        yield path + ".__length__", "int", len(data)
        for value in data:
            yield from flatten(value, path + "[]")
    else:
        yield path, type(data).__name__, data


def write_csv(path, rows, fields=None):
    rows = iter(rows)
    first = next(rows, None)
    with open(path, "w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(first or {}))
        writer.writeheader()
        if first is not None:
            writer.writerow(first)
        writer.writerows(rows)


class Profiler:
    def __init__(self, db: sqlite3.Connection):
        self.db = db
        db.executescript('''
          CREATE TABLE counts(topic TEXT, schema_id INT, path TEXT, type TEXT, value TEXT,
            n INT, PRIMARY KEY(topic,schema_id,path,type,value));
          CREATE TABLE fields(topic TEXT,schema_id INT,path TEXT,type TEXT,messages INT,
            occurrences INT,numeric INT,nonzero INT,minimum REAL,maximum REAL,
            PRIMARY KEY(topic,schema_id,path,type));
        ''')

    def add(self, row):
        values = Counter((p, t, dumps(v)) for p, t, v in flatten(row["data"]))
        self.db.executemany('''INSERT INTO counts VALUES(?,?,?,?,?,?)
          ON CONFLICT(topic,schema_id,path,type,value) DO UPDATE SET n=n+excluded.n''',
          ((row["topic"], row["schema_id"], p, t, v, n) for (p, t, v), n in values.items()))
        stats = {}
        for (p, t, v), n in values.items():
            s = stats.setdefault((p, t), [0, 0, 0, None, None])
            s[0] += n
            if t in ("int", "float", "bool"):
                number = json.loads(v)
                s[1] += n
                s[2] += n if number != 0 else 0
                s[3] = number if s[3] is None else min(s[3], number)
                s[4] = number if s[4] is None else max(s[4], number)
        self.db.executemany('''INSERT INTO fields VALUES(?,?,?,?,1,?,?,?,?,?)
          ON CONFLICT(topic,schema_id,path,type) DO UPDATE SET
          messages=messages+1,occurrences=occurrences+excluded.occurrences,
          numeric=numeric+excluded.numeric,nonzero=nonzero+excluded.nonzero,
          minimum=min(minimum,excluded.minimum),maximum=max(maximum,excluded.maximum)''',
          ((row["topic"], row["schema_id"], p, t, *s[:3],
            float(s[3]) if s[3] is not None else None,
            float(s[4]) if s[4] is not None else None) for (p, t), s in stats.items()))

    def rows(self, totals):
        for topic, sid, path, typ, msgs, occ, numeric, nz, low, high in self.db.execute(
            "SELECT * FROM fields ORDER BY topic,schema_id,path,type"
        ):
            key = (topic, sid, path, typ)
            distinct = self.db.execute("SELECT count(*) FROM counts WHERE topic=? AND schema_id=? AND path=? AND type=?", key).fetchone()[0]
            top = self.db.execute("SELECT value,n FROM counts WHERE topic=? AND schema_id=? AND path=? AND type=? ORDER BY n DESC,value LIMIT 5", key).fetchall()
            if typ == "int":
                # SQLite REAL cannot exactly represent uint64 timestamps; recover exact bounds.
                exact = (json.loads(v) for (v,) in self.db.execute(
                    "SELECT value FROM counts WHERE topic=? AND schema_id=? AND path=? AND type=?",key))
                low = high = None
                for value in exact:
                    low = value if low is None else min(low,value)
                    high = value if high is None else max(high,value)
            flags = []
            if distinct == 1:
                flags.append("固定值；是否默认/占位需确认")
            elif top and top[0][1] / occ >= .95:
                flags.append("95%以上为同一值")
            boundary = 200 if path.endswith("Obstacle_PosX") else 20 if path.endswith("Obstacle_TTC") else None
            if boundary is not None:
                count = sum(n for value, n in self.db.execute("SELECT value,n FROM counts WHERE topic=? AND schema_id=? AND path=? AND type=?", key) if json.loads(value) == boundary)
                flags.append(f"可能边界/占位值{boundary}：{count}次；保留不删除")
            yield dict(topic=topic, schema_id=sid, field_path=path, data_type=typ,
                       message_count=totals[(topic, sid)], messages_present=msgs,
                       occurrence_count=occ, distinct_values=distinct, minimum=low, maximum=high,
                       nonzero_count=nz if numeric else "", nonzero_ratio=nz / numeric if numeric else "",
                       top_values=dumps(top), changed=distinct > 1, flags="；".join(flags),
                       complex_or_array=typ in ("object", "array") or "[]" in path,
                       presence_note="Protobuf隐式标量：默认值与显式设置无法区分；出现不等于显式设置")
