# Annotated Binary Frame Hex Dump Analysis

This document provides a byte-by-byte visual hex breakdown of one complete request and response exchange captured directly from the execution of `./bcurl -v localhost:9000/hello.txt` against `./bserve ./www 9000`.

---

## 1. Request HEADERS Frame (Client to Server)

### Summary Metrics
* **Total Frame Bytes**: 59 bytes (9 bytes frame header + 50 bytes payload)
* **Stream ID**: 1
* **Frame Type**: `HEADERS` (`0x02`)
* **Flags**: `0x05` (`FLAG_END_HEADERS` | `FLAG_END_STREAM`)

### Raw Hex Dump
```
0000  00 00 32 02 05 00 00 00 01 00 04 01 00 03 47 45 |..2...........GE|
0010  54 02 00 0A 2F 68 65 6C 6C 6F 2E 74 78 74 04 00 |T.../hello.txt..|
0020  0E 6C 6F 63 61 6C 68 6F 73 74 3A 39 30 30 30 05 |.localhost:9000.|
0030  00 09 62 63 75 72 6C 2F 31 2E 30                |..bcurl/1.0|
```

### Detailed Field Breakdown

| Byte Offset | Hex Bytes | Interpretation | Field Description |
|---|---|---|---|
| `0000 - 0002` | `00 00 32` | 50 (24-bit uint) | **Payload Length**: 50 bytes follow the header. |
| `0003` | `02` | `0x02` | **Frame Type**: `HEADERS` frame. |
| `0004` | `05` | `0x05` | **Flags**: `FLAG_END_HEADERS` (0x04) + `FLAG_END_STREAM` (0x01). |
| `0005 - 0008` | `00 00 00 01` | 1 (32-bit uint) | **Stream ID**: Stream 1. |
| `0009 - 000A` | `00 04` | 4 (16-bit uint) | **Header Field Count**: 4 header fields present. |
| `000B` | `01` | Index 1 | **Header 1 Name Index**: Index 1 maps to `:method`. |
| `000C - 000D` | `00 03` | 3 (16-bit uint) | **Header 1 Value Length**: 3 bytes. |
| `000E - 0010` | `47 45 54` | "GET" | **Header 1 Value**: ASCII string "GET". |
| `0011` | `02` | Index 2 | **Header 2 Name Index**: Index 2 maps to `:path`. |
| `0012 - 0013` | `00 0A` | 10 (16-bit uint) | **Header 2 Value Length**: 10 bytes. |
| `0014 - 001D` | `2F 68 65 6C 6C 6F 2E 74 78 74` | "/hello.txt" | **Header 2 Value**: ASCII string "/hello.txt". |
| `001E` | `04` | Index 4 | **Header 3 Name Index**: Index 4 maps to `host`. |
| `001F - 0020` | `00 0E` | 14 (16-bit uint) | **Header 3 Value Length**: 14 bytes. |
| `0021 - 002E` | `6C 6F 63 61 6C 68 6F 73 74 3A 39 30 30 30` | "localhost:9000" | **Header 3 Value**: Target host string. |
| `002F` | `05` | Index 5 | **Header 4 Name Index**: Index 5 maps to `user-agent`. |
| `0030 - 0031` | `00 09` | 9 (16-bit uint) | **Header 4 Value Length**: 9 bytes. |
| `0032 - 003A` | `62 63 75 72 6C 2F 31 2E 30` | "bcurl/1.0" | **Header 4 Value**: Client agent identifier. |

---

## 2. Response HEADERS Frame (Server to Client)

### Summary Metrics
* **Total Frame Bytes**: 35 bytes (9 bytes frame header + 26 bytes payload)
* **Stream ID**: 1
* **Frame Type**: `HEADERS` (`0x02`)
* **Flags**: `0x04` (`FLAG_END_HEADERS`)

### Raw Hex Dump
```
0000  00 00 1A 02 04 00 00 00 01 00 03 03 00 03 32 30 |..............20|
0010  30 07 00 02 37 33 06 00 0A 74 65 78 74 2F 70 6C |0...73...text/pl|
0020  61 69 6E                                        |ain|
```

### Detailed Field Breakdown

| Byte Offset | Hex Bytes | Interpretation | Field Description |
|---|---|---|---|
| `0000 - 0002` | `00 00 1A` | 26 (24-bit uint) | **Payload Length**: 26 bytes follow the header. |
| `0003` | `02` | `0x02` | **Frame Type**: `HEADERS` frame. |
| `0004` | `04` | `0x04` | **Flags**: `FLAG_END_HEADERS` (0x04). |
| `0005 - 0008` | `00 00 00 01` | 1 (32-bit uint) | **Stream ID**: Stream 1. |
| `0009 - 000A` | `00 03` | 3 (16-bit uint) | **Header Field Count**: 3 header fields. |
| `000B` | `03` | Index 3 | **Header 1 Name Index**: Index 3 maps to `:status`. |
| `000C - 000D` | `00 03` | 3 (16-bit uint) | **Header 1 Value Length**: 3 bytes. |
| `000E - 0010` | `32 30 30` | "200" | **Header 1 Value**: HTTP status code 200 OK. |
| `0011` | `07` | Index 7 | **Header 2 Name Index**: Index 7 maps to `content-length`. |
| `0012 - 0013` | `00 02` | 2 (16-bit uint) | **Header 2 Value Length**: 2 bytes. |
| `0014 - 0015` | `37 33` | "73" | **Header 2 Value**: File length 73 bytes. |
| `0016` | `06` | Index 6 | **Header 3 Name Index**: Index 6 maps to `content-type`. |
| `0017 - 0018` | `00 0A` | 10 (16-bit uint) | **Header 3 Value Length**: 10 bytes. |
| `0019 - 0022` | `74 65 ... 6E` | "text/plain" | **Header 3 Value**: MIME type string. |

---

## 3. Response DATA Frame (Server to Client)

### Summary Metrics
* **Total Frame Bytes**: 82 bytes (9 bytes frame header + 73 bytes payload)
* **Stream ID**: 1
* **Frame Type**: `DATA` (`0x01`)
* **Flags**: `0x01` (`FLAG_END_STREAM`)

### Raw Hex Dump
```
0000  00 00 49 01 01 00 00 00 01 48 65 6C 6C 6F 20 66 |..I......Hello f|
0010  72 6F 6D 20 42 69 6E 61 72 79 20 48 54 54 50 20 |rom Binary HTTP |
0020  50 72 6F 74 6F 63 6F 6C 20 73 65 72 76 65 72 21 |Protocol server!|
0030  0A 45 76 65 72 79 74 68 69 6E 67 20 69 73 20 77 |.Everything is w|
0040  6F 72 6B 69 6E 67 20 63 6F 72 72 65 63 74 6C 79 |orking correctly|
0050  2E 0A                                           |..|
```

### Detailed Field Breakdown

| Byte Offset | Hex Bytes | Interpretation | Field Description |
|---|---|---|---|
| `0000 - 0002` | `00 00 49` | 73 (24-bit uint) | **Payload Length**: 73 bytes of file payload. |
| `0003` | `01` | `0x01` | **Frame Type**: `DATA` frame. |
| `0004` | `01` | `0x01` | **Flags**: `FLAG_END_STREAM` (0x01) signals end of response. |
| `0005 - 0008` | `00 00 00 01` | 1 (32-bit uint) | **Stream ID**: Stream 1. |
| `0009 - 0051` | `48 65 ... 0A` | Text Bytes | **Payload Content**: ASCII content of `/hello.txt`. |
