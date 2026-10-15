#!/usr/bin/env python3
"""Measured-overhead probe for nano-mcp-termux.

Purpose
-------
Produce *measured* numbers for the MCP-on-mobile overhead report instead of
quoting community estimates. Everything here is read straight off the server's
own stdio JSON-RPC surface, so the numbers are reproducible on any device.

What it measures
----------------
1. initialize  -> response bytes (handshake floor)
2. tools/list  -> total response bytes, plus per-tool schema bytes
3. tools/call  -> a real device_status round-trip (payload + wall time)
4. token estimate for the tools/list payload (chars/4 heuristic, labelled as
   an estimate, not a tokenizer count). For real-tokenizer counts use
   scripts/token_probe.py.

Byte conventions
----------------
`tools_list_bytes` is a *compact* re-serialisation ("," / ":" separators), not
the bytes the server actually writes to stdio (default ", " / ": " separators,
which are larger). See the byte-convention table in the report's section 1.

Usage
-----
    python3 measure_overhead.py            # human-readable
    python3 measure_overhead.py --json     # machine-readable
"""
import json
import os
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


def rpc(lines, timeout=20):
    """Send newline-delimited JSON-RPC to the server, return (raw_stdout, elapsed)."""
    payload = "".join(json.dumps(m) + "\n" for m in lines)
    t0 = time.time()
    proc = subprocess.run(
        [sys.executable, SERVER],
        input=payload.encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=timeout,
    )
    elapsed = time.time() - t0
    return proc.stdout.decode("utf-8", "replace"), elapsed


def one(raw, want_id):
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


def token_estimate(text):
    """chars/4 heuristic. Explicitly an estimate; real tokenizers differ."""
    return max(1, round(len(text) / 4))


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

    init_req = {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "overhead-probe", "version": "1.0"}},
    }
    list_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    call_req = {
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "device_status", "arguments": {}},
    }

    raw, _ = rpc([init_req])
    init_obj = one(raw, 1) or {}
    init_bytes = len(json.dumps(init_obj, separators=(",", ":")))

    raw, _ = rpc([init_req, list_req])
    list_obj = one(raw, 2) or {}
    tools = (list_obj.get("result") or {}).get("tools") or []
    list_bytes = len(json.dumps(list_obj, separators=(",", ":")))
    list_pretty = json.dumps(list_obj, ensure_ascii=False, indent=2)

    per_tool = []
    for t in tools:
        blob = json.dumps(t, separators=(",", ":"), ensure_ascii=False)
        per_tool.append({
            "name": t.get("name"),
            "bytes": len(blob.encode("utf-8")),
            "est_tokens": token_estimate(blob),
        })

    raw, elapsed = rpc([init_req, call_req])
    call_obj = one(raw, 3) or {}
    call_bytes = len(json.dumps(call_obj, separators=(",", ":")))

    report = {
        "device": "Xiaomi 23013RK75C / Android 15 (SDK 35) / aarch64",
        "server": os.path.basename(SERVER),
        "python": sys.version.split()[0],
        "initialize_bytes": init_bytes,
        "tools_list_bytes": list_bytes,
        "tools_list_est_tokens": token_estimate(list_pretty),
        "tool_count": len(tools),
        "per_tool": per_tool,
        "device_status_call_bytes": call_bytes,
        "device_status_roundtrip_s": round(elapsed, 3),
    }

    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print("== MCP on Mobile: measured overhead probe ==")
    print("server          :", report["server"])
    print("python          :", report["python"])
    print()
    print("initialize resp : %5d bytes" % init_bytes)
    print("tools/list resp : %5d bytes  (~%d tokens, chars/4 estimate)"
          % (list_bytes, report["tools_list_est_tokens"]))
    print("tools in list   : %d" % len(tools))
    for t in per_tool:
        print("   - %-16s %5d bytes  ~%4d tokens"
              % (t["name"], t["bytes"], t["est_tokens"]))
    print("device_status   : %5d bytes payload, %.3fs round-trip"
          % (call_bytes, report["device_status_roundtrip_s"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
