import sys
import struct

FRAME_HEADER_SIZE = 9
MAX_FRAME_PAYLOAD = (1 << 24) - 1

FRAME_TYPE_DATA = 0x01
FRAME_TYPE_HEADERS = 0x02
FRAME_TYPE_PING = 0x03
FRAME_TYPE_GOAWAY = 0x04
FRAME_TYPE_UNKNOWN = 0x99

FLAG_END_STREAM = 0x01
FLAG_END_HEADERS = 0x04
FLAG_ACK = 0x08

STATIC_HEADER_TABLE = [
    "",
    ":method",
    ":path",
    ":status",
    "host",
    "user-agent",
    "content-type",
    "content-length",
    "accept",
    "server",
    "date"
]

def get_header_index(name: str) -> int:
    name_lower = name.lower()
    for idx, table_name in enumerate(STATIC_HEADER_TABLE):
        if idx > 0 and table_name.lower() == name_lower:
            return idx
    return 0

class FrameHeader:
    def __init__(self, length: int, frame_type: int, flags: int, stream_id: int):
        self.length = length
        self.type = frame_type
        self.flags = flags
        self.stream_id = stream_id

    def pack(self) -> bytes:
        if not 0 <= self.length <= MAX_FRAME_PAYLOAD:
            raise ValueError("Frame payload length must fit in 24 bits")
        if not 0 <= self.type <= 0xFF:
            raise ValueError("Frame type must fit in 8 bits")
        if not 0 <= self.flags <= 0xFF:
            raise ValueError("Frame flags must fit in 8 bits")
        if not 0 <= self.stream_id <= 0xFFFFFFFF:
            raise ValueError("Stream ID must fit in 32 bits")
        b0 = (self.length >> 16) & 0xFF
        b1 = (self.length >> 8) & 0xFF
        b2 = self.length & 0xFF
        return struct.pack(">BBBBBI", b0, b1, b2, self.type, self.flags, self.stream_id)

    @classmethod
    def unpack(cls, data: bytes) -> 'FrameHeader':
        if len(data) < FRAME_HEADER_SIZE:
            raise ValueError("Buffer too short for frame header")
        b0, b1, b2, f_type, flags, stream_id = struct.unpack(">BBBBBI", data[0:9])
        length = (b0 << 16) | (b1 << 8) | b2
        return cls(length, f_type, flags, stream_id)

def read_exact(sock, n: int) -> bytes:
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            break
        data.extend(packet)
    return bytes(data)

def encode_headers(headers: list) -> bytes:
    if len(headers) > 0xFFFF:
        raise ValueError("Too many headers for one HEADERS frame")

    buf = bytearray()
    buf.extend(struct.pack(">H", len(headers)))
    for name, value in headers:
        idx = get_header_index(name)
        name_bytes = str(name).encode('utf-8')
        val_bytes = str(value).encode('utf-8')
        if len(name_bytes) > 0xFFFF or len(val_bytes) > 0xFFFF:
            raise ValueError("Header name/value is too long")

        if idx > 0:
            buf.append(idx)
            buf.extend(struct.pack(">H", len(val_bytes)))
            buf.extend(val_bytes)
        else:
            buf.append(0)
            buf.extend(struct.pack(">H", len(name_bytes)))
            buf.extend(name_bytes)
            buf.extend(struct.pack(">H", len(val_bytes)))
            buf.extend(val_bytes)
    return bytes(buf)

def decode_headers(payload: bytes) -> list:
    if len(payload) < 2:
        raise ValueError("Payload too short for header block")
    count = struct.unpack(">H", payload[0:2])[0]
    pos = 2
    headers = []
    for _ in range(count):
        if pos >= len(payload):
            raise ValueError("Unexpected end of header payload")
        idx = payload[pos]
        pos += 1
        if idx > 0:
            if idx >= len(STATIC_HEADER_TABLE):
                raise ValueError(f"Invalid static header index {idx}")
            name = STATIC_HEADER_TABLE[idx]
            if pos + 2 > len(payload):
                raise ValueError("Truncated header value length")
            val_len = struct.unpack(">H", payload[pos:pos+2])[0]
            pos += 2
            if pos + val_len > len(payload):
                raise ValueError("Truncated header value string")
            val = payload[pos:pos+val_len].decode('utf-8', errors='replace')
            pos += val_len
            headers.append((name, val))
        else:
            if pos + 2 > len(payload):
                raise ValueError("Truncated header name length")
            name_len = struct.unpack(">H", payload[pos:pos+2])[0]
            pos += 2
            if pos + name_len > len(payload):
                raise ValueError("Truncated header name string")
            name = payload[pos:pos+name_len].decode('utf-8', errors='replace')
            pos += name_len

            if pos + 2 > len(payload):
                raise ValueError("Truncated header value length")
            val_len = struct.unpack(">H", payload[pos:pos+2])[0]
            pos += 2
            if pos + val_len > len(payload):
                raise ValueError("Truncated header value string")
            val = payload[pos:pos+val_len].decode('utf-8', errors='replace')
            pos += val_len
            headers.append((name, val))

    if pos != len(payload):
        raise ValueError("Trailing bytes after header block")

    return headers

def print_hexdump(label: str, data: bytes, header: FrameHeader = None):
    sys.stderr.write(f"\n=== HEX DUMP: {label} ===\n")
    if header:
        type_names = {
            FRAME_TYPE_DATA: "DATA",
            FRAME_TYPE_HEADERS: "HEADERS",
            FRAME_TYPE_PING: "PING",
            FRAME_TYPE_GOAWAY: "GOAWAY"
        }
        t_name = type_names.get(header.type, "UNKNOWN")
        sys.stderr.write(f"[Header Breakdown] Length: {header.length} bytes | Type: 0x{header.type:02X} ({t_name}) | Flags: 0x{header.flags:02X} | Stream ID: {header.stream_id}\n")
    sys.stderr.write(f"[Raw Bytes Total: {len(data)}]\n")
    
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_str = " ".join(f"{b:02X}" for b in chunk)
        ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
        sys.stderr.write(f"{i:04X}  {hex_str:<47} |{ascii_str}|\n")
    sys.stderr.write("=================================\n\n")
