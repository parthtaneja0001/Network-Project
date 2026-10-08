#!/usr/bin/env python3
import subprocess
import time
import socket
import sys
import os
import threading
from protocol import (
    FRAME_HEADER_SIZE,
    FRAME_TYPE_DATA,
    FRAME_TYPE_HEADERS,
    FRAME_TYPE_UNKNOWN,
    FLAG_END_STREAM,
    FLAG_END_HEADERS,
    FrameHeader,
    read_exact,
    encode_headers,
    decode_headers
)

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
WWW_DIR = os.path.join(PROJECT_DIR, "www")

def find_free_port():
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port

def recv_response(sock):
    headers = {}
    body = bytearray()

    while True:
        hdr_bytes = read_exact(sock, FRAME_HEADER_SIZE)
        assert len(hdr_bytes) == FRAME_HEADER_SIZE, "Connection closed before a complete response frame"
        hdr = FrameHeader.unpack(hdr_bytes)
        payload = read_exact(sock, hdr.length)
        assert len(payload) == hdr.length, "Connection closed during response payload"

        if hdr.type not in (FRAME_TYPE_DATA, FRAME_TYPE_HEADERS):
            continue
        if hdr.type == FRAME_TYPE_HEADERS:
            headers.update(dict(decode_headers(payload)))
        elif hdr.type == FRAME_TYPE_DATA:
            body.extend(payload)

        if hdr.flags & FLAG_END_STREAM:
            return headers, bytes(body)

def send_get(sock, path, stream_id):
    headers = [
        (":method", "GET"),
        (":path", path),
        ("host", "127.0.0.1")
    ]
    payload = encode_headers(headers)
    req_hdr = FrameHeader(len(payload), FRAME_TYPE_HEADERS, FLAG_END_HEADERS | FLAG_END_STREAM, stream_id)
    sock.sendall(req_hdr.pack() + payload)

def run_tests():
    print("=== STARTING BINARY HTTP PROTOCOL INTEGRATION TESTS ===")

    port = find_free_port()
    server_proc = subprocess.Popen(
        ["./bserve", WWW_DIR, str(port)],
        cwd=PROJECT_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True
    )
    time.sleep(0.5)
    if server_proc.poll() is not None:
        err = server_proc.stderr.read() if server_proc.stderr else ""
        raise RuntimeError(f"Server failed to start:\n{err}")

    try:
        # Test 1: Basic GET index.html via bcurl
        print("\n[Test 1] Fetching /index.html via bcurl...")
        res = subprocess.run(["./bcurl", f"127.0.0.1:{port}/index.html"], cwd=PROJECT_DIR, capture_output=True, text=True)
        assert res.returncode == 0, f"bcurl failed with code {res.returncode}: {res.stderr}"
        assert "Welcome to Binary HTTP Server" in res.stdout, "Unexpected stdout content"
        print("PASS: Basic GET request succeeded.")

        # Test 2: Verbose Hex Dump flag -v
        print("\n[Test 2] Fetching /hello.txt with -v flag...")
        res_v = subprocess.run(["./bcurl", "-v", f"127.0.0.1:{port}/hello.txt"], cwd=PROJECT_DIR, capture_output=True, text=True)
        assert res_v.returncode == 0, f"bcurl -v failed with code {res_v.returncode}"
        assert "HEX DUMP: REQUEST FRAME SENT" in res_v.stderr, "Missing request hexdump"
        assert "HEX DUMP: RESPONSE FRAME RECEIVED" in res_v.stderr, "Missing response hexdump"
        assert "Hello from Binary HTTP Protocol server!" in res_v.stdout, "Unexpected body output"
        print("PASS: Verbose hexdump output verified.")

        # Test 3: 404 Not Found returns non-zero exit code
        print("\n[Test 3] Requesting missing file /missing.html...")
        res_404 = subprocess.run(["./bcurl", f"127.0.0.1:{port}/missing.html"], cwd=PROJECT_DIR, capture_output=True, text=True)
        assert res_404.returncode != 0, "Expected non-zero exit code on 404 response!"
        assert "404 Not Found" in res_404.stdout, "Missing 404 error message body"
        print("PASS: 404 status correctly produced non-zero exit code.")

        # Test 4: Single TCP Connection Persistent Multi-Request Test
        print("\n[Test 4] Persistent Connection - 3 Sequential Requests on Single Socket...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", port))

        paths = ["/index.html", "/hello.txt", "/index.html"]
        for stream_id, path in enumerate(paths, start=1):
            send_get(sock, path, stream_id)
            resp_headers, resp_body = recv_response(sock)
            assert resp_headers.get(":status") == "200", f"Expected status 200, got {resp_headers}"
            assert len(resp_body) > 0, "Empty DATA payload"

        sock.close()
        print("PASS: Single connection successfully handled 3 sequential requests.")

        # Test 5: Unknown Frame Type (0x99) Extensibility Rule
        print("\n[Test 5] Sending Unknown Extension Frame (0x99) followed by GET...")
        sock_ext = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock_ext.connect(("127.0.0.1", port))

        # Send Unknown Frame type 0x99 with 12 bytes payload
        unk_payload = b"VERSION_2_EXT"
        unk_hdr = FrameHeader(len(unk_payload), FRAME_TYPE_UNKNOWN, 0x00, 99)
        sock_ext.sendall(unk_hdr.pack() + unk_payload)

        # Immediately send standard GET request frame on the exact same socket
        send_get(sock_ext, "/hello.txt", 100)

        # Read response to standard GET request
        resp_headers, _ = recv_response(sock_ext)
        assert resp_headers.get(":status") == "200", "Failed to process valid request after unknown frame"
        sock_ext.close()
        print("PASS: Unknown frame type 0x99 was cleanly skipped without dropping connection.")

        # Test 6: Malformed HEADERS frame returns 400 and keeps the socket usable
        print("\n[Test 6] Malformed HEADERS frame returns 400 without closing connection...")
        sock_bad = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock_bad.connect(("127.0.0.1", port))
        bad_payload = b"\x00\x01\x7F"  # one header with an invalid static index
        bad_hdr = FrameHeader(len(bad_payload), FRAME_TYPE_HEADERS, FLAG_END_HEADERS | FLAG_END_STREAM, 7)
        sock_bad.sendall(bad_hdr.pack() + bad_payload)
        bad_headers, bad_body = recv_response(sock_bad)
        assert bad_headers.get(":status") == "400", f"Expected malformed frame status 400, got {bad_headers}"
        assert b"Malformed HEADERS" in bad_body, "Missing malformed-frame body"

        send_get(sock_bad, "/hello.txt", 8)
        ok_headers, ok_body = recv_response(sock_bad)
        assert ok_headers.get(":status") == "200", "Connection did not survive malformed frame"
        assert b"Hello from Binary HTTP Protocol server!" in ok_body
        sock_bad.close()
        print("PASS: Malformed HEADERS gets 400 and connection remains open.")

        # Test 7: Path traversal is rejected
        print("\n[Test 7] Path traversal request is rejected...")
        res_traversal = subprocess.run(["./bcurl", f"127.0.0.1:{port}/../SPEC.md"], cwd=PROJECT_DIR, capture_output=True, text=True)
        assert res_traversal.returncode != 0, "Expected non-zero exit code on traversal attempt"
        assert "400 Bad Request" in res_traversal.stdout, "Traversal attempt did not return 400"
        print("PASS: Path traversal attempt is rejected with status 400.")

        # Test 8: bcurl skips unknown response frames before the real response
        print("\n[Test 8] bcurl skips unknown response frames on one connection...")
        fake_port = find_free_port()
        ready = threading.Event()

        def fake_server():
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("127.0.0.1", fake_port))
            srv.listen(1)
            ready.set()
            conn, _ = srv.accept()
            req_hdr = FrameHeader.unpack(read_exact(conn, FRAME_HEADER_SIZE))
            read_exact(conn, req_hdr.length)

            unknown_payload = b"ignored extension"
            conn.sendall(FrameHeader(len(unknown_payload), FRAME_TYPE_UNKNOWN, 0x00, 1).pack() + unknown_payload)
            resp_headers = encode_headers([(":status", "200"), ("content-type", "text/plain")])
            conn.sendall(FrameHeader(len(resp_headers), FRAME_TYPE_HEADERS, FLAG_END_HEADERS, 1).pack() + resp_headers)
            body = b"client skipped unknown frame\n"
            conn.sendall(FrameHeader(len(body), FRAME_TYPE_DATA, FLAG_END_STREAM, 1).pack() + body)
            conn.close()
            srv.close()

        thread = threading.Thread(target=fake_server, daemon=True)
        thread.start()
        assert ready.wait(2), "Fake server did not start"
        res_unknown = subprocess.run(["./bcurl", f"127.0.0.1:{fake_port}/x"], cwd=PROJECT_DIR, capture_output=True, text=True)
        thread.join(2)
        assert res_unknown.returncode == 0, f"bcurl failed after unknown response frame: {res_unknown.stderr}"
        assert "client skipped unknown frame" in res_unknown.stdout
        print("PASS: bcurl skipped an unknown response frame and read the real body.")

        print("\nALL INTEGRATION TESTS PASSED SUCCESSFULLY!")

    finally:
        server_proc.terminate()
        server_proc.wait(timeout=5)

if __name__ == "__main__":
    run_tests()
