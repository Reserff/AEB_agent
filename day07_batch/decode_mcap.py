"""Local-only streaming decoding. No Agent/API imports or network calls."""
import base64
import math
from pathlib import Path
from typing import Any, Iterator

from google.protobuf.message import Message
from mcap.reader import NonSeekingReader
from mcap_protobuf.decoder import DecoderFactory as ProtobufFactory
from mcap_ros1.decoder import DecoderFactory as Ros1Factory


def plain(value: Any, path: str = "", presence: dict | None = None) -> Any:
    """Preserve protobuf field names, enum numbers, defaults and presence uncertainty."""
    if isinstance(value, Message):
        result = {}
        for field in value.DESCRIPTOR.fields:
            key = f"{path}.{field.name}".lstrip(".")
            item = getattr(value, field.name)
            if field.is_repeated:
                if presence is not None:
                    presence[key] = "repeated_length_known"
                if field.message_type and field.message_type.GetOptions().map_entry:
                    result[field.name] = {str(k): plain(v, key + "{}", presence) for k, v in item.items()}
                else:
                    result[field.name] = [plain(v, key + "[]", presence) for v in item]
            elif field.has_presence:
                if presence is not None:
                    presence[key] = "present" if value.HasField(field.name) else "absent"
                if value.HasField(field.name):
                    result[field.name] = plain(item, key, presence)
            else:
                if presence is not None:
                    presence[key] = "implicit_default_or_set_unknown"
                result[field.name] = plain(item, key, presence)
        return result
    if hasattr(value, "__slots__"):
        return {k: plain(getattr(value, k), f"{path}.{k}", presence) for k in value.__slots__}
    if isinstance(value, (list, tuple)):
        return [plain(v, path + "[]", presence) for v in value]
    if isinstance(value, bytes):
        return {"__bytes_base64__": base64.b64encode(value).decode("ascii")}
    if isinstance(value, float) and not math.isfinite(value):
        return {"__nonfinite__": str(value)}
    return value


def iter_decoded(path: str | Path) -> Iterator[dict]:
    factories = [ProtobufFactory(), Ros1Factory()]
    decoders = {}
    with Path(path).open("rb") as stream:
        # Physical order guarantees bounded memory even for files without an index.
        for index, (schema, channel, message) in enumerate(
            NonSeekingReader(stream).iter_messages(log_time_order=False)
        ):
            row = dict(index=index, topic=channel.topic, channel_id=channel.id,
                       schema_id=channel.schema_id, schema=schema.name if schema else "",
                       encoding=channel.message_encoding, log_time_ns=message.log_time,
                       publish_time_ns=message.publish_time, sequence=message.sequence)
            try:
                key = (channel.message_encoding, channel.schema_id)
                if key not in decoders:
                    decoders[key] = next((d for factory in factories
                        if (d := factory.decoder_for(channel.message_encoding, schema)) is not None), None)
                decoder = decoders[key]
                if decoder is None:
                    raise ValueError("Unsupported message/schema encoding")
                presence = {}
                row.update(data=plain(decoder(message.data), presence=presence), presence=presence)
            except Exception as exc:
                # Failure of one message does not hide later messages; framing errors still abort.
                row.update(data=None, error=f"{type(exc).__name__}: {exc}")
            yield row
