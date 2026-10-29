
import sys

from mcap.reader import make_reader
from google.protobuf import descriptor_pb2


def iter_message_types(message, prefix):
    """递归遍历 Protobuf 消息定义。"""

    full_name = (
        f"{prefix}.{message.name}"
        if prefix
        else message.name
    )

    yield full_name, message

    for nested in message.nested_type:
        yield from iter_message_types(
            nested,
            full_name,
        )


def print_message_fields(message_name, message):
    """打印指定消息的字段。"""

    print(f"\n消息类型：{message_name}")
    print("字段定义：")

    for field in message.field:

        field_type = (
            field.type_name
            if field.type_name
            else descriptor_pb2.FieldDescriptorProto.Type.Name(
                field.type
            )
        )

        print(
            f"  {field.number}. "
            f"{field.name} "
            f"| 类型: {field_type}"
        )


def inspect_schema(file_path, topic_name):

    with open(file_path, "rb") as f:

        reader = make_reader(f)
        summary = reader.get_summary()

        if summary is None:
            raise ValueError("MCAP 没有可用的 Summary")

        # 1. 根据 Topic 找到 Channel
        channel = next(
            (
                ch
                for ch in summary.channels.values()
                if ch.topic == topic_name
            ),
            None,
        )

        if channel is None:
            raise ValueError(
                f"找不到 Topic: {topic_name}"
            )

        # 2. 根据 Channel 找到 Schema
        schema = summary.schemas.get(channel.schema_id)

        if schema is None:
            raise ValueError("找不到对应的 Schema")

        if schema.encoding != "protobuf":
            raise ValueError(
                f"不支持的 Schema 编码: {schema.encoding}"
            )

        # 3. 解析 Protobuf Schema
        descriptor_set = descriptor_pb2.FileDescriptorSet()
        descriptor_set.ParseFromString(schema.data)

        print("Topic:", topic_name)
        print("Schema:", schema.name)

        # 4. 指定需要查看的消息类型
        # 注意：这段代码仍在 inspect_schema 函数内部
        target_messages = [
            schema.name.lstrip("."),
            "AebDecisionSpiDebug.AEB_FunDebug_Info",
            "AebDecisionSpiDebug.AEB_Decision_Info",
        ]

        # 5. 收集所有消息定义
        message_types = {}

        for proto_file in descriptor_set.file:

            for message in proto_file.message_type:

                for name, definition in iter_message_types(
                    message,
                    proto_file.package,
                ):
                    message_types[name] = definition

        # 6. 查找并打印目标消息
        for target in target_messages:

            message = message_types.get(target)

            if message is None:
                print(f"\n未找到消息定义：{target}")
                continue

            print_message_fields(target, message)


if __name__ == "__main__":

    if len(sys.argv) != 3:
        print(
            "用法: python inspect_proto_schema.py "
            "<mcap文件> <topic>"
        )
        sys.exit(1)

    inspect_schema(sys.argv[1], sys.argv[2])
