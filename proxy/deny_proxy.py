#!/usr/bin/env python3
"""Deny-by-default egress proxy.

Purpose: turn "the sandbox cannot reach the network" into evidence. With
--network none an attempt is only a socket error inside the container. Here the
attempt arrives at this process first, so the log can record *what was tried*
and *what we decided* -- that pair is the demo artifact.

Every decision is appended as one JSON line to $AR_PROXY_LOG (and stdout).

    AR_ALLOW        comma separated. "example.com" exact, ".example.com" suffix.
                    empty (default) = deny everything
    AR_PROXY_LOG    path to JSONL file; omit to log to stdout only
    AR_TASK_ID      recorded on every line
    AR_PROXY_PORT   default 8899

Python stdlib only, so it runs unchanged on the VM and on a laptop.
"""

import argparse
import json
import os
import socket
import socketserver
import sys
import threading
import time

ALLOW = tuple(h.strip().lower() for h in os.environ.get("AR_ALLOW", "").split(",") if h.strip())
LOG_PATH = os.environ.get("AR_PROXY_LOG", "")
TASK_ID = os.environ.get("AR_TASK_ID", "")
_log_lock = threading.Lock()


def host_allowed(host: str) -> bool:
    host = (host or "").lower().rstrip(".")
    for pattern in ALLOW:
        if pattern == host:
            return True
        if pattern.startswith(".") and (host == pattern[1:] or host.endswith(pattern)):
            return True
    return False


def record(kind: str, host: str, port, decision: str, **extra) -> None:
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "task_id": TASK_ID,
        "kind": kind,
        "host": host,
        "port": port,
        "decision": decision,
    }
    entry.update(extra)
    line = json.dumps(entry, ensure_ascii=False)
    with _log_lock:
        if LOG_PATH:
            with open(LOG_PATH, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        sys.stdout.write(line + "\n")
        sys.stdout.flush()


class Handler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        sock = self.request
        sock.settimeout(15)
        try:
            head = sock.recv(8192)
        except OSError:
            return
        if not head:
            return

        try:
            request_line = head.split(b"\r\n", 1)[0].decode("latin-1")
        except Exception:
            return
        parts = request_line.split()
        if len(parts) < 2:
            return
        method, target = parts[0].upper(), parts[1]

        host, port, kind = None, None, "connect" if method == "CONNECT" else "http"

        if method == "CONNECT":
            if ":" in target:
                host, port_s = target.rsplit(":", 1)
                port = int(port_s) if port_s.isdigit() else 443
            else:
                host, port = target, 443
        else:
            # absolute-form request: GET http://host:port/path
            if "://" in target:
                rest = target.split("://", 1)[1]
                authority = rest.split("/", 1)[0]
                if ":" in authority:
                    host, port_s = authority.rsplit(":", 1)
                    port = int(port_s) if port_s.isdigit() else 80
                else:
                    host, port = authority, 80
            else:
                host, port = (target.split("/", 1)[0] or "?"), 80

        if host_allowed(str(host)):
            record(kind, str(host), port, "allow", method=method)
            self._forward(kind, host, port, head)
        else:
            record(kind, str(host), port, "deny", method=method,
                   reason="default-deny", allowlist=list(ALLOW))
            body = json.dumps({
                "error": "blocked by egress policy",
                "host": host,
                "policy": "default-deny",
            }).encode()
            try:
                sock.sendall(
                    b"HTTP/1.1 403 Forbidden\r\n"
                    b"Content-Type: application/json\r\n"
                    b"Connection: close\r\n"
                    b"X-Blocked-By: ar-deny-proxy\r\n"
                    b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body
                )
            except OSError:
                pass

    def _forward(self, kind, host, port, head) -> None:
        try:
            upstream = socket.create_connection((host, port), timeout=15)
        except OSError as exc:
            record(kind, str(host), port, "allow-upstream-failed", error=str(exc))
            return
        with upstream:
            if kind == "connect":
                self.request.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            else:
                upstream.sendall(head)
            # Both directions must run at once, otherwise a CONNECT tunnel deadlocks
            # as soon as one side is waiting for the other.
            back = threading.Thread(target=self._pump, args=(upstream, self.request), daemon=True)
            back.start()
            self._pump(self.request, upstream)
            back.join(timeout=60)

    @staticmethod
    def _pump(src, dst) -> None:
        try:
            while True:
                chunk = src.recv(65536)
                if not chunk:
                    return
                dst.sendall(chunk)
        except OSError:
            return


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> int:
    ap = argparse.ArgumentParser(description="deny-by-default egress proxy")
    ap.add_argument("--port", type=int, default=int(os.environ.get("AR_PROXY_PORT", "8899")))
    ap.add_argument("--host", default=os.environ.get("AR_PROXY_BIND", "0.0.0.0"))
    ap.add_argument("--allow", default=None, help="comma separated allowlist (overrides AR_ALLOW)")
    args = ap.parse_args()

    global ALLOW
    if args.allow is not None:
        ALLOW = tuple(h.strip().lower() for h in args.allow.split(",") if h.strip())

    record("start", "-", args.port, "listening", allowlist=list(ALLOW))
    print(f"[deny-proxy] listening on {args.host}:{args.port} "
          f"allow={list(ALLOW) or 'NOTHING'}", file=sys.stderr)
    with Server((args.host, args.port), Handler) as srv:
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
