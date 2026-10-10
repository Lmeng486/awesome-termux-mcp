#!/usr/bin/env python3
"""Simulated MCP client — covers version negotiation & graceful degradation."""
import json, os, subprocess, sys

_HERE = os.path.dirname(os.path.abspath(__file__))
SRV = [os.environ.get("MCP_PYTHON", sys.executable),
       os.environ.get("MCP_SERVER", os.path.join(_HERE, "nano-mcp-system.py"))]

def talk(reqs):
    return talk_raw([json.dumps(r) for r in reqs])

def talk_raw(lines):
    p = subprocess.run(SRV, input="\n".join(lines) + "\n",
                       capture_output=True, text=True, timeout=20)
    resp = [json.loads(l) for l in p.stdout.splitlines() if l.strip()]
    if not resp:
        sys.stderr.write("[test-client] server returned nothing; rc=%s stderr=%r\n" % (p.returncode, p.stderr))
        raise SystemExit(2)
    return resp, p.stderr

checks = []
def check(name, cond):
    checks.append((name, bool(cond)))

# --- scenario A: client sends 2025-11-25 -> echoed back ---
resp, _ = talk([
    {"jsonrpc": "2.0", "id": 1, "method": "initialize",
     "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "ping"},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
     "params": {"name": "device_status", "arguments": {}}},
])
init = resp[0]["result"]
check("initialize echoes client version 2025-11-25",
      init.get("protocolVersion") == "2025-11-25")
check("capabilities == {'tools': {}}", init.get("capabilities") == {"tools": {}})
check("notification got NO response", len(resp) == 4)
check("ping -> {}", resp[1]["result"] == {})
check("tools/list ok", resp[2]["result"]["tools"][0]["name"] == "device_status")
bat = json.loads(resp[3]["result"]["content"][0]["text"]).get("battery", {})
check("tools/call content type text",
      resp[3]["result"]["content"][0]["type"] == "text")
check("battery source in full degradation ladder",
      bat.get("source") in ("termux-api", "sysfs", "sysfs-uevent", "unavailable"))

# --- scenario B: client sends 2025-06-18 -> echoed back ---
resp2, _ = talk([{"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": "2025-06-18"}}])
check("initialize echoes client version 2025-06-18",
      resp2[0]["result"]["protocolVersion"] == "2025-06-18")

# --- scenario C: unknown version -> highest supported ---
resp3, _ = talk([{"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": "1999-01-01"}}])
check("unknown version -> highest supported 2025-11-25",
      resp3[0]["result"]["protocolVersion"] == "2025-11-25")

# --- scenario D: protocol errors ---
resp4, err = talk_raw([
    '{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "no_such_tool", "arguments": {}}}',
    'not json at all',
])
check("unknown tool -> -32602", resp4[0]["error"]["code"] == -32602)
check("parse error -> -32700", resp4[1]["error"]["code"] == -32700)
check("logs on stderr only", "[nano-mcp]" in err)
check("stdout clean (all lines are JSON)",
      all(True for _ in resp4))  # talk() already json.loads every line

fails = [n for n, okc in checks if not okc]
for n, okc in checks:
    print(("PASS " if okc else "FAIL ") + n)
print("RESULT: " + ("ALL CHECKS PASSED" if not fails else f"{len(fails)} FAILED"))
sys.exit(1 if fails else 0)
