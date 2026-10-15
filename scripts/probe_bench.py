#!/usr/bin/env python3
"""Encoding + latency + schema-scaling bench for nano-mcp-termux.

Three measurements, all reproducible on-device:

A. Wire-size comparison: the SAME tool call encoded as JSON-RPC vs a
   hand-rolled protobuf wire format (varint, no protobuf dependency). This
   tests the widely-quoted claim that "a tool call costs 2-5 KB in JSON-RPC
   but only ~200 bytes in protobuf".

B. Long-lived session latency: one server process, N sequential requests,
   measuring per-request round-trip. This is the realistic MCP case (a
   persistent stdio pipe), not one-process-per-call.

C. Schema scaling: measured per-tool schema cost extrapolated to the tool
   counts of real Termux MCP servers (19/29/38/52/72). Extrapolation is
   labelled as such -- only the 4-tool figure is measured. The token column
   here is the chars/4 heuristic; the report section 2.5 figures come from
   scripts/token_probe.py (real BPE) and are lower.

Byte conventions: the JSON-RPC sizes below are *compact* re-serialisations
("," / ":" separators), not the bytes the server writes to stdio (default
", " / ": " separators, which are larger). See report section 1.

Usage:
    python3 probe_bench.py
    python3 probe_bench.py --json
"""
import json
import os
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def resolve_server():
    """Locate the server under test.

    Order: first positional CLI argument -> $MCP_SERVER -> ./nano_mcp_termux.py
    -> /tmp/nano-mcp-termux/nano_mcp_termux.py. This repo does not vendor the
    server (it lives in Lmeng486/nano-mcp-termux), so a bare invocation needs
    either a clone at /tmp/nano-mcp-termux or an explicit path.
    """
    for a in sys.argv[1:]:
        if not a.startswith("-"):
            return a
    cands = [os.environ.get("MCP_SERVER"),
             os.path.join(HERE, "nano_mcp_termux.py"),
             "/tmp/nano-mcp-termux/nano_mcp_termux.py"]
    for cand in cands:
        if cand and os.path.isfile(cand):
            return cand
    # nothing found -- return the first non-empty candidate so the caller can
    # report the most likely intended path
    for cand in cands:
        if cand:
            return cand
    return ""


SERVER = resolve_server()
PY = sys.executable


# ---------------------------------------------------------------- protobuf
def _varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _pb_str(field, s):
    data = s.encode("utf-8")
    return _varint((field << 3) | 2) + _varint(len(data)) + data


def _pb_int(field, v):
    return _varint((field << 3) | 0) + _varint(v)


def protobuf_tool_call(method, name, req_id):
    """message ToolCall { string method=1; string name=2; uint32 id=3; }"""
    return _pb_str(1, method) + _pb_str(2, name) + _pb_int(3, req_id)


# ---------------------------------------------------------------- helpers
def rpc_once(lines, timeout=20):
    payload = "".join(json.dumps(m) + "\n" for m in lines)
    proc = subprocess.run([PY, SERVER], input=payload.encode(),
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          timeout=timeout)
    return proc.stdout.decode("utf-8", "replace")


def find(raw, want_id):
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if obj.get("id") == want_id:
            return obj
    return None


def tok(text):
    """chars/4 heuristic -- NOT a tokenizer count.

    Kept only for the schema-scaling column below. The figures quoted in
    the report section 2.5 come from scripts/token_probe.py (real BPE;
    Qwen2.5 lower bound, GPT-2 upper bound) and run ~15-25%% below this
    estimate.
    """
    return max(1, round(len(text) / 4))


class Session:
    """Persistent stdio session -- the real MCP transport shape."""

    def __init__(self):
        self.p = subprocess.Popen(
            [PY, SERVER], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1)

    def send(self, obj):
        t0 = time.perf_counter()
        self.p.stdin.write(json.dumps(obj) + "\n")
        self.p.stdin.flush()
        line = self.p.stdout.readline()
        return (time.perf_counter() - t0) * 1000.0, line

    def close(self):
        try:
            self.p.stdin.close()
        except Exception:
            pass
        self.p.terminate()
        try:
            self.p.wait(timeout=5)
        except Exception:
            self.p.kill()


def main():
    as_json = "--json" in sys.argv
    if not os.path.isfile(SERVER):
        sys.stderr.write(
            "error: server under test not found: %r\n"
            "This repo does not bundle the server. Either clone it:\n"
            "  git clone https://github.com/Lmeng486/nano-mcp-termux /tmp/nano-mcp-termux\n"
            "or point at it explicitly:\n"
            "  MCP_SERVER=/path/to/nano_mcp_termux.py python3 %s\n"
            % (SERVER, os.path.basename(__file__)))
        return 2

    out = {}

    # ---------------- A. wire size ----------------
    json_req = json.dumps({
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "device_status", "arguments": {}},
    }, separators=(",", ":"))
    pb_req = protobuf_tool_call("tools/call", "device_status", 3)

    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "bench", "version": "1"}}}
    call = {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "device_status", "arguments": {}}}
    raw = rpc_once([init, call])
    resp = find(raw, 3) or {}
    json_resp = json.dumps(resp, separators=(",", ":"))
    # protobuf response is just the serialized content text + framing
    content_text = ""
    try:
        content_text = resp["result"]["content"][0]["text"]
    except Exception:
        pass
    pb_resp_len = len(content_text.encode("utf-8"))

    out["wire"] = {
        "request_json_bytes": len(json_req.encode()),
        "request_protobuf_bytes": len(pb_req),
        "request_ratio": round(len(json_req.encode()) / max(1, len(pb_req)), 2),
        "response_json_bytes": len(json_resp.encode()),
        "response_payload_bytes": pb_resp_len,
        "response_ratio": round(len(json_resp.encode()) / max(1, pb_resp_len), 2),
    }

    # ---------------- B. latency ----------------
    s = Session()
    try:
        s.send(init)
        lat = []
        for i in range(20):
            ms, _ = s.send({"jsonrpc": "2.0", "id": 100 + i, "method": "ping",
                            "params": {}})
            lat.append(ms)
        lat_sorted = sorted(lat)
        out["latency"] = {
            "samples": len(lat),
            "min_ms": round(min(lat), 3),
            "p50_ms": round(statistics.median(lat), 3),
            "p95_ms": round(lat_sorted[int(len(lat) * 0.95) - 1], 3),
            "max_ms": round(max(lat), 3),
            "mean_ms": round(statistics.mean(lat), 3),
        }
    finally:
        s.close()

    # ---------------- C. schema scaling ----------------
    raw = rpc_once([init, {"jsonrpc": "2.0", "id": 2, "method": "tools/list",
                           "params": {}}])
    tools = ((find(raw, 2) or {}).get("result") or {}).get("tools") or []
    measured_blob = json.dumps({"jsonrpc": "2.0", "id": 2,
                                "result": {"tools": tools}},
                               separators=(",", ":"), ensure_ascii=False)
    per_tool = len(measured_blob.encode()) / max(1, len(tools))
    scale = []
    for n in (4, 19, 29, 38, 52, 72):
        b = int(round(per_tool * n))
        scale.append({"tool_count": n, "est_bytes": b, "est_tokens": tok("x" * b),
                      "measured": n == len(tools)})
    out["scaling"] = {
        "measured_tools": len(tools),
        "measured_total_bytes": len(measured_blob.encode()),
        "per_tool_bytes": round(per_tool, 1),
        "extrapolated": scale,
    }

    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    w = out["wire"]
    print("== A. wire size (same device_status call) ==")
    print("request  JSON-RPC : %4d bytes" % w["request_json_bytes"])
    print("request  protobuf : %4d bytes   (%.1fx smaller)"
          % (w["request_protobuf_bytes"], w["request_ratio"]))
    print("response JSON-RPC : %4d bytes" % w["response_json_bytes"])
    print("response payload  : %4d bytes   (%.1fx smaller)"
          % (w["response_payload_bytes"], w["response_ratio"]))
    print()
    l = out["latency"]
    print("== B. latency, persistent session (%d ping samples) ==" % l["samples"])
    print("min %.3f ms | p50 %.3f ms | p95 %.3f ms | max %.3f ms"
          % (l["min_ms"], l["p50_ms"], l["p95_ms"], l["max_ms"]))
    print()
    sc = out["scaling"]
    print("== C. tools/list schema cost ==")
    print("   (token column = chars/4 heuristic, not the report section 2.5 figures)")
    print("measured: %d tools -> %d bytes (%.1f bytes/tool)"
          % (sc["measured_tools"], sc["measured_total_bytes"], sc["per_tool_bytes"]))
    print("extrapolated to real Termux servers:")
    for row in sc["extrapolated"]:
        mark = " (measured)" if row["measured"] else " (extrapolated)"
        print("   %3d tools -> %5d bytes  ~%5d tok(chars/4)%s"
              % (row["tool_count"], row["est_bytes"], row["est_tokens"], mark))
    return 0


if __name__ == "__main__":
    sys.exit(main())