"""The FT-TS600 CIP registration and digital join framing."""
import asyncio

HELLO = bytes.fromhex("0f000102")
ACCEPT = bytes.fromhex("0200040000201f")
UPDATE = bytes.fromhex("0500050000020300")
INIT = bytes.fromhex("05000b000008080e0237271122260500050000020316050005000002031c")
READY = bytes.fromhex("050005000002031d")
PING = bytes.fromhex("0d00020000")
MAX_PAYLOAD = 4096


async def read_frame(reader: asyncio.StreamReader) -> bytes:
    header = await reader.readexactly(3)
    size = int.from_bytes(header[1:], "big")
    if size > MAX_PAYLOAD:
        raise ValueError("CIP frame exceeds the supported payload size")
    return header + await reader.readexactly(size)


def signon_matches(frame: bytes, ip_id: int) -> bool:
    return len(frame) >= 5 and frame[0] == 0x0A and frame[4] == ip_id


def digital_joins(frame: bytes):
    """Decode standard and button-style digital records in one data frame."""
    if len(frame) < 9 or frame[0] != 5 or frame[3:5] != b"\x00\x00":
        return
    pos = 5
    while pos < len(frame):
        size = frame[pos]
        end = pos + 1 + size
        if size == 0 or end > len(frame):
            return
        if size == 3 and frame[pos + 1] in (0x00, 0x27):
            value = int.from_bytes(frame[pos + 2:end], "little")
            yield (value & 0x7FFF) + 1, not bool(value & 0x8000)
        pos = end


def digital_feedback(join: int, value: bool) -> bytes:
    raw = (join - 1) | (0 if value else 0x8000)
    return bytes.fromhex("05000600000300") + raw.to_bytes(2, "little")
