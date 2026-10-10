#!/usr/bin/env python3
"""Local JSON-RPC loop test for nano-mcp-system.py."""
import json, subprocess, sys

REQS = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "test-client", "version": "0.0.1"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "ping"},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {
        "name": "device_status", "arguments": {}}},
    {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {
        "name": "no_such_tool", "arguments": {}}},
]

p = subprocess.run(["python3", "/root/awesome-termux-mcp/nano/nano-mcp-system.py"],
                   input="\n".join(json.dumps(r) for r in REQS),
                   capture_output=True, text=True, timeout=30)

resp = [json.loads(l) for l in p.stdout.splitlines() if l.strip()]
by_id = {r.get("id"): r for r in resp}

checks = []
checks.append(("initialize protocolVersion", by_id[1]["result"]["protocolVersion"] == "2025-06-18"))
checks.append(("capabilities == {'tools': {}}", by_id[1]["result"]["capabilities"] == {"tools": {}}))
checks.append(("notification got NO response (5 responses for 5 requests with ids)", len(resp) == 5))
checks.append(("ping -> {}", by_id[2].get("result") == {}))
tools = by_id[3]["result"]["tools"]
checks.append(("tools/list ok", len(tools) == 1 and tools[0]["name"] == "device_status" and "inputSchema" in tools[0]))
checks.append(("tools/call text content", by_id[4]["result"]["content"][0]["type"] == "text"))
dev = json.loads(by_id[4]["result"]["content"][0]["text"])
checks.append(("unknown tool -> -32602", by_id[5].get("error", {}).get("code") == -32602))
checks.append(("logs on stderr only", "[nano-mcp]" in p.stderr))
checks.append(("stdout clean (all lines are JSON)", all(l.strip().startswith("{") for l in p.stdout.splitlines())))

print("device_status ->", json.dumps(dev, ensure_ascii=False))
for name, ok in checks:
    print(("PASS" if ok else "FAIL"), "-", name)
print("RESULT:", "ALL CHECKS PASSED" if all(ok for _, ok in checks) else "FAILED")
sys.exit(0 if all(ok for _, ok in checks) else 1)