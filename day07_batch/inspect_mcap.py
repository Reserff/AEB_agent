import sys
from itertools import islice
from pathlib import Path

from mcap.reader import make_reader


def inspect_mcap(file_path: str):

    path = Path(file_path)

    print("========== 文件信息 ==========")
    print("文件大小(MB):", round(path.stat().st_size / 1024**2, 2))

    with path.open("rb") as f:

        reader = make_reader(f)
        summary = reader.get_summary()

        print("\n========== Topic 信息 ==========")

        if summary is not None:

            print("Channel 数量:", len(summary.channels))
            print("Schema 数量:", len(summary.schemas))

            stats = summary.statistics

            if stats is not None:
                print("消息总数:", stats.message_count)

            for channel in summary.channels.values():

                schema = summary.schemas.get(channel.schema_id)

                count = "未知"

                if stats is not None:
                    count = stats.channel_message_counts.get(
                        channel.id, 0
                    )

                print("\nTopic:", channel.topic)
                print("Encoding:", channel.message_encoding)
                print(
                    "Schema:",
                    schema.name if schema else "N/A"
                )
                print(
                    "Schema Encoding:",
                    schema.encoding if schema else "N/A"
                )
                print("消息数量:", count)

        else:
            print("没有可用的 Summary")

        print("\n========== 前 10 条消息 ==========")

        for schema, channel, message in islice(
            reader.iter_messages(), 10
        ):
            print(
                "Topic:", channel.topic,
                "| 时间戳(ns):", message.log_time,
                "| 数据大小(bytes):", len(message.data),
            )


if __name__ == "__main__":
    inspect_mcap(sys.argv[1])