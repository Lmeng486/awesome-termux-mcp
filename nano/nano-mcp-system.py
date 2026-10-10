#!/usr/bin/env python3
"""nano-mcp-system.py — Zero-dependency, single-file MCP server for Termux/Android.

Implements the minimal MCP protocol surface over stdio:
  initialize | notifications/initialized (silent) | ping | tools/list | tools/call

Design rules (see README):
  1. stdout is SACRED: only JSON-RPC frames go to stdout. All logs -> stderr.
  2. capabilities declare ONLY {"tools": {}} — minimal promise, max compatibility.
  3. Graceful degradation: device_status never fails; missing inputs marked unavailable.
"""
import json, subprocess, sys

PROTOCOL_VERSION = "2025-06-18"


def log(msg):
    sys.stderr.write("[nano-mcp] " + str(msg) + "\n")
    sys.stderr.flush()


def send(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def run(cmd, timeout=5):
    """Run a shell command; return stdout string or None on failure."""
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              timeout=timeout).stdout.strip()
    except Exception as e:
        log("run failed: " + cmd + " -> " + repr(e))
        return None


# ---------------------------------------------------------------- tools impl

def tool_device_status(_args):
    out = {"battery": None, "storage": None, "arch": None, "memory": None}

    # battery: termux-api -> sysfs -> unavailable
    raw = run("termux-battery-status")
    if raw:
        try:
            b = json.loads(raw)
            out["battery"] = {"percent": b.get("percentage"), "source": "termux-api"}
        except Exception:
            pass
    if out["battery"] is None:
        cap = run("cat /sys/class/power_supply/battery/capacity")
        out["battery"] = ({"percent": int(cap), "source": "sysfs"}
                          if cap and cap.isdigit() else {"source": "unavailable"})

    # storage: df /data
    df = run("df -h /data")
    if df:
        out["storage"] = {"source": "df", "raw": df}

    # arch
    arch = run("uname -m")
    out["arch"] = arch if arch else "unavailable"

    # memory: free -m -> /proc/meminfo
    mem = run("free -m | grep Mem")
    if mem:
        out["memory"] = {"source": "free", "raw": mem}
    else:
        mi = run("head -3 /proc/meminfo")
        out["memory"] = {"source": "procfs", "raw": mi} if mi else {"source": "unavailable"}

    return out


TOOLS = {
    "device_status": {
        "name": "device_status",
        "description": "Aggregate device info: battery/storage/arch/memory. Never fails; degraded fields marked unavailable.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
}


def handle(req):
    method = req.get("method", "")
    rid = req.get("id")

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "nano-mcp-system", "version": "0.1.0"},
        }}
    if method == "notifications/initialized":
        return None  # silent, no response for notifications
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": list(TOOLS.values())}}
    if method == "tools/call":
        name = req.get("params", {}).get("name", "")
        args = req.get("params", {}).get("arguments", {}) or {}
        if name not in TOOLS:
            return {"jsonrpc": "2.0", "id": rid, "error": {
                "code": -32602, "message": "Unknown tool: " + name}}
        try:
            data = tool_device_status(args) if name == "device_status" else {}
        except Exception as e:  # degrade, never crash the tool call
            log("tool error: " + repr(e))
            data = {"error": "internal", "detail": str(e)}
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}]}}

    return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601,
            "message": "Method not found: " + method}}


def main():
    log("nano-mcp-system starting (protocol " + PROTOCOL_VERSION + ")")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception as e:
            send({"jsonrpc": "2.0", "id": None, "error": {
                "code": -32700, "message": "Parse error: " + str(e)}})
            continue
        try:
            resp = handle(req)
            if resp is not None:
                send(resp)
        except Exception as e:
            log("UNCAUGHT: " + repr(e))
            send({"jsonrpc": "2.0", "id": req.get("id"), "error": {
                "code": -32603, "message": "Internal error: " + str(e)}})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("FATAL: " + repr(e))
        sys.exit(1)
