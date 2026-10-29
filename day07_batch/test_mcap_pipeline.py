"""Synthetic fixtures only: no company recordings or protocols."""
import csv
import json
import sqlite3
import struct

import pytest
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from mcap.writer import Writer

from day07_batch.decode_mcap import iter_decoded, plain
from day07_batch.events import prepare, add_sample, extract, export_events
from day07_batch.field_profile import Profiler
from day07_batch.signal_catalog import classify
from day07_batch.summarize_mcap import analyze


def proto_fixture():
    fd = descriptor_pb2.FileDescriptorProto(name="synthetic.proto",package="test",syntax="proto3")
    msg = fd.message_type.add(name="Sample")
    msg.field.add(name="frame_id",number=1,type=5)
    child = msg.nested_type.add(name="Child")
    child.field.add(name="value",number=1,type=5)
    msg.field.add(name="children",number=2,type=11,type_name=".test.Sample.Child",label=3)
    msg.field.add(name="optional_child",number=3,type=11,type_name=".test.Sample.Child")
    pool = descriptor_pool.DescriptorPool()
    pool.Add(fd)
    cls = message_factory.GetMessageClass(pool.FindMessageTypeByName("test.Sample"))
    fds = descriptor_pb2.FileDescriptorSet()
    fds.file.add().CopyFrom(fd)
    return cls, fds.SerializeToString()


def test_dynamic_decode_both_encodings_and_failure(tmp_path):
    cls, schema = proto_fixture()
    msg = cls()
    msg.children.add(value=7)
    path = tmp_path / "synthetic.mcap"
    with path.open("wb") as stream:
        writer = Writer(stream)
        writer.start()
        ps = writer.register_schema("test.Sample","protobuf",schema)
        pc = writer.register_channel("/proto","protobuf",ps)
        rs = writer.register_schema("test/Example","ros1msg",b"int32 code\nfloat64[] values\n")
        rc = writer.register_channel("/ros","ros1",rs)
        writer.add_message(pc,10,msg.SerializeToString(),10)
        writer.add_message(rc,20,struct.pack("<iI2d",3,2,1.5,2.5),20)
        writer.add_message(pc,30,b"\xff",30)
        writer.add_message(pc,40,msg.SerializeToString(),40)
        writer.finish()
    rows = list(iter_decoded(path))
    assert rows[0]["data"] == {"frame_id":0,"children":[{"value":7}]}
    assert rows[0]["presence"]["frame_id"] == "implicit_default_or_set_unknown"
    assert rows[0]["presence"]["optional_child"] == "absent"
    assert rows[1]["data"] == {"code":3,"values":[1.5,2.5]}
    assert "DecodeError" in rows[2]["error"]
    assert rows[3]["data"]["children"][0]["value"] == 7
    result = analyze(path,tmp_path / "output",export_jsonl=True)
    assert result["messages"] == 4 and result["decoded"] == 3 and result["failed"] == 1
    assert json.loads((tmp_path / "output/run_status.json").read_text())["complete"]
    assert len((tmp_path / "output/all_topics.jsonl").read_text().splitlines()) == 4
    with pytest.raises(FileExistsError):
        analyze(path,tmp_path / "output")


def test_profile_boundaries_arrays_and_missing():
    db = sqlite3.connect(":memory:")
    profiler = Profiler(db)
    for data in ({"Obstacle_PosX":200,"Obstacle_TTC":20,"arr":[0,1],"optional":3},
                 {"Obstacle_PosX":10,"Obstacle_TTC":20,"arr":[]}):
        profiler.add(dict(topic="/x",schema_id=1,data=data))
    rows = {r["field_path"]:r for r in profiler.rows({("/x",1):2})}
    assert rows["Obstacle_PosX"]["changed"]
    assert "200：1次" in rows["Obstacle_PosX"]["flags"]
    assert "20：2次" in rows["Obstacle_TTC"]["flags"]
    assert rows["optional"]["messages_present"] == 1
    assert rows["arr[]"]["occurrence_count"] == 2
    assert rows["arr[]"]["messages_present"] == 1
    assert rows["arr[]"]["nonzero_ratio"] == .5
    assert rows["arr.__length__"]["minimum"] == 0


def sample(db, index, frame, value=None, t=None, topic="/mcu_decision_data", error=None):
    data = {"frame_id":frame}
    if value is not None:
        data["AEB_Sts"] = value
    add_sample(db,dict(index=index,topic=topic,schema_id=1,log_time_ns=index*10 if t is None else t,
                      data=data if error is None else None,error=error))


def test_duplicates_missing_conflicts_and_reset(tmp_path):
    db = sqlite3.connect(":memory:")
    prepare(db)
    for i,(frame,value) in enumerate([(1,0),(1,0),(2,1),(2,1),(3,2),(3,3),(4,4),
                                      (5,None),(6,5),(1,6),(7,7)]):
        sample(db,i,frame,value)
    metrics = extract(db)
    transitions = db.execute("SELECT old,new FROM events").fetchall()
    assert transitions == [("0","1"),("6","7")]
    assert metrics["duplicate_messages"] == 3
    assert metrics["reappeared_frame_runs"] == 1
    assert metrics["conflicting_frame_runs"] == 1
    export_events(db,tmp_path,5,10)
    rows = list(csv.DictReader((tmp_path / "event_context.csv").open(encoding="utf-8-sig")))
    assert any(r["matched"] == "False" for r in rows)
    assert any(r["matched"] == "True" and r["delta_ns"] == "0" for r in rows)


def test_decode_gap_long_gap_sorting_and_initial_nonzero():
    db = sqlite3.connect(":memory:")
    prepare(db)
    sample(db,0,1,8,t=10)
    sample(db,1,2,9,t=30)
    sample(db,2,0,error="bad",t=20)
    sample(db,3,3,10,t=1000)
    sample(db,4,4,11,t=1010)
    extract(db,max_gap_ns=50)
    assert db.execute("SELECT old,new FROM events").fetchall() == [("10","11")]


def test_signal_screening_requires_observation_and_ignores_objvalid():
    base = dict(topic="/mcu_decision_data",field_path="AEB_Sts",data_type="int",changed=False)
    assert classify(base)["category"] == "待确认信号"
    assert classify(dict(base,changed=True))["category"] == "核心信号"
    assert classify(dict(base,field_path="FVC_ObjValid",changed=True))["category"] == "暂不使用信号"


def test_nonfinite_json_safe():
    assert plain(float("nan")) == {"__nonfinite__":"nan"}


def test_uint64_bounds_remain_exact():
    db = sqlite3.connect(":memory:")
    profiler = Profiler(db)
    for value in (2**64-2,2**64-1):
        profiler.add(dict(topic="/x",schema_id=1,data={"value":value}))
    row = next(profiler.rows({("/x",1):2}))
    assert row["minimum"] == 2**64-2
    assert row["maximum"] == 2**64-1
