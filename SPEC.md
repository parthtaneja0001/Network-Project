# Binary HTTP Protocol Specification (Version 1.0)

## 1. Protocol Overview

The Binary HTTP Protocol (BHTTP) is a light binary application-layer protocol designed to multiplex request-response streams over a single persistent TCP connection. Standard text-based HTTP/1.1 relies on line-delimited ASCII headers, which require expensive string parsing and delimiter scanning. BHTTP replaces string delimiters with fixed-width binary frame headers and static header index tables.

### Design Goals
* **Deterministic Parsing**: Fixed 9-byte frame header enables direct binary decoding into fields without string scanning.
* **Stream Persistence**: A single TCP connection handles multiple sequential or concurrent request-response exchanges.
* **Extensibility**: Receiver rules enforce safe skipping of unrecognized frame types, preserving backward and forward compatibility for future protocol versions.

---

## 2. Binary Frame Header Specification

Every frame transmitted over the network starts with a mandatory 9-byte (72-bit) fixed header, followed by a payload of length $N$ bytes (where $N \ge 0$).

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                       Length (24 bits)                        |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|   Type (8)    |   Flags (8)   |       Stream ID (32 bits)     |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                       Stream ID (cont)                        |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                     Payload Bytes (Length B) ...              |
```

### Field Width Defense and Rationale

1. **Payload Length (24 bits / 3 bytes)**:
   Allows payload sizes up to $2^{24} - 1 = 16,777,215$ bytes (16 Megabytes).
   *Rationale*: 24 bits strikes an optimal balance. A smaller 16-bit field limits frames to 64KB, forcing large files to be fragmented into thousands of frames. A larger 32-bit length allows single frames up to 4GB, which introduces buffer exhaustion vulnerabilities and head-of-line blocking on single connections. HTTP/2 selected 24 bits for this exact reason.

2. **Frame Type (8 bits / 1 byte)**:
   Provides 256 distinct frame type identifiers.
   *Rationale*: 8 bits allocates space for core protocol frames (DATA=0x01, HEADERS=0x02, PING=0x03, GOAWAY=0x04) while leaving over 240 frame type codes available for experimental and future extensions (v2).

3. **Flags (8 bits / 1 byte)**:
   Bitmask providing 8 control flags per frame.
   *Rationale*: 8 bits provides boolean toggles for stream termination (`END_STREAM` = 0x01), header block completion (`END_HEADERS` = 0x04), and control frame acknowledgements (`ACK` = 0x08).

4. **Stream Identifier (32 bits / 4 bytes)**:
   Unsigned 32-bit integer identifying the logical request-response stream.
   *Rationale*: A 32-bit field supports over 4 billion unique stream IDs over the lifetime of a long-lived persistent TCP connection, preventing stream identifier exhaustion without requiring connection resets.

---

## 3. Frame Types and Control Flags

### Frame Types
| Type Code | Name | Description |
|---|---|---|
| `0x01` | `DATA` | Carries arbitrary binary or text payload content (e.g. file content or response body). |
| `0x02` | `HEADERS` | Carries compressed header blocks containing metadata (:method, :path, :status, etc.). |
| `0x03` | `PING` | Measures round-trip time and verifies connection liveness. |
| `0x04` | `GOAWAY` | Initiates graceful connection shutdown. |
| `0x99` | `UNKNOWN` | Used for extensibility testing. |

### Control Flags
* **`FLAG_END_STREAM` (`0x01`)**: Indicates that this frame is the final frame sent by the sender for the designated stream.
* **`FLAG_END_HEADERS` (`0x04`)**: Indicates that the HEADERS frame contains the complete set of headers for the stream.
* **`FLAG_ACK` (`0x08`)**: Set in response to a received PING frame.

---

## 4. Header Compression (HPACK-Lite)

To minimize frame overhead, BHTTP implements HPACK static table indexing combined with length-prefixed literal encoding.

### Static Header Index Table (Top 10 Common Headers)
The protocol pre-defines indices 1 through 10 for the most frequently transmitted header names:

| Index | Header Name |
|---|---|
| 1 | `:method` |
| 2 | `:path` |
| 3 | `:status` |
| 4 | `host` |
| 5 | `user-agent` |
| 6 | `content-type` |
| 7 | `content-length` |
| 8 | `accept` |
| 9 | `server` |
| 10 | `date` |

### Header Field Encoding Format
A HEADERS frame payload starts with a 2-byte unsigned integer indicating the total count of header fields ($N$). It is followed by $N$ field entries formatted as follows:

1. **Indexed Header Name (Index Byte $1 \le I \le 10$)**:
   * Byte 0: Static Index ($I$)
   * Bytes 1-2: Value Length ($V_{len}$, 16-bit Big-Endian uint)
   * Bytes 3 to $3 + V_{len} - 1$: Value String (ASCII/UTF-8)

2. **Literal Header Name (Index Byte $I = 0$)**:
   * Byte 0: `0x00`
   * Bytes 1-2: Name Length ($N_{len}$, 16-bit Big-Endian uint)
   * Bytes 3 to $3 + N_{len} - 1$: Name String
   * Bytes $3 + N_{len}$ to $3 + N_{len} + 1$: Value Length ($V_{len}$, 16-bit Big-Endian uint)
   * Remaining Bytes: Value String

---

## 5. Extensibility Rule: Unknown Frame Handling

**Mandatory Rule**: A receiver encountering a frame type that it does not recognize MUST cleanly skip the frame by reading and discarding exactly $N$ bytes from the socket (where $N$ is the payload length specified in the 9-byte header).

The receiver MUST NOT terminate the TCP connection, MUST NOT close the socket, and MUST NOT emit a protocol error. Processing continues normally for subsequent frames on the same connection. This rule leaves room for Version 2 extensions without breaking Version 1 endpoints.

---

## 6. Client and Server Behavioral Requirements

### Server (`bserve`) Requirements
* Command syntax: `./bserve <root_dir> <port>`
* Bind to TCP port and accept client connections.
* **Connection Persistence**: Maintain the TCP connection open across multiple request-response cycles until client disconnects.
* Safely resolve requested paths relative to `<root_dir>` to prevent path traversal attacks.
* Return HTTP status 200 OK with file bytes on success.
* Return HTTP status 404 Not Found if requested file does not exist.
* Return HTTP status 400 Bad Request if frame format is invalid.

### Client (`bcurl`) Requirements
* Command syntax: `./bcurl [-v] host:port/path`
* Connect to target host and port via TCP.
* **Single Connection Rule**: Execute the request and read response frames over a single TCP connection; never open a second connection.
* Output response body bytes directly to `stdout`.
* When `-v` flag is supplied: print annotated hex dumps of every transmitted request frame and received response frame to `stderr`.
* Exit with code 0 on status 2xx/3xx, and exit non-zero (code 1) on status 4xx/5xx.
