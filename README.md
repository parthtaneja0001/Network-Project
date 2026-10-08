# Binary HTTP Project

This project implements both tracks from the course prompt:

* `bserve`: a binary HTTP-style file server.
* `bcurl`: a binary HTTP-style client.

The protocol is described in [`SPEC.md`](SPEC.md), and one complete annotated request/response exchange is documented in [`HEXDUMP.md`](HEXDUMP.md).

## Requirements

* Python 3.8 or newer
* macOS/Linux terminal

No third-party packages are required.

## Files

| File | Purpose |
|---|---|
| `protocol.py` | Shared binary frame, header encoding, parsing, and hexdump helpers. |
| `bserve` | Track 1 server implementation. |
| `bcurl` | Track 2 client implementation. |
| `test_protocol.py` | Integration tests for both tracks and required edge cases. |
| `SPEC.md` | Two-page protocol specification and field-width rationale. |
| `HEXDUMP.md` | Annotated hexdump of one full request and response. |
| `www/` | Sample document root served by `bserve`. |

## Quick Start

Make the scripts executable:

```sh
make
```

Run the server:

```sh
./bserve ./www 9000
```

In another terminal, run the client:

```sh
./bcurl localhost:9000/index.html
```

Verbose mode prints every frame as an annotated hexdump to `stderr` while keeping the response body on `stdout`:

```sh
./bcurl -v localhost:9000/hello.txt
```

## Tests

Run:

```sh
make test
```

The tests verify:

* successful file fetches through `bcurl`
* verbose request and response hexdumps
* non-zero client exit status for `404`
* multiple sequential requests on one TCP connection
* required clean skipping of unknown frame types
* `400 Bad Request` for malformed HEADERS frames
* path traversal rejection
* client-side skipping of unknown response frames

## Protocol Summary

Every frame has a fixed 9-byte header:

```text
24-bit payload length | 8-bit type | 8-bit flags | 32-bit stream id
```

Known frame types are:

| Type | Name | Use |
|---|---|---|
| `0x01` | `DATA` | Response body bytes. |
| `0x02` | `HEADERS` | Request/response metadata. |
| `0x03` | `PING` | Liveness check; receiver replies with `ACK`. |
| `0x04` | `GOAWAY` | Graceful connection close. |

The important extensibility rule is implemented by both endpoints:

> A receiver that sees an unknown frame type reads and discards exactly the declared payload length, keeps the connection open, and continues with the next frame.

That rule is what allows a future version of the protocol to add frames without breaking version 1 clients and servers.
