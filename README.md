# awesome-termux-mcp

> **A Curated Directory of Verified MCP Servers on Android (Termux / PRoot) — with a Zero-Dependency Nano Prototype & Runtime Survival Guides.**

Most MCP (Model Context Protocol) servers assume a PC with Docker and Node. Almost nothing is **curated, tested and documented for running directly on an Android phone inside Termux/PRoot**. This repo fills that gap:

1. **Verified directory** — every listed server carries a real-device badge (see below).
2. **nano-mcp-system.py** — a single-file, zero-dependency MCP server (~145 lines, Python stdlib only) that passes a full JSON-RPC protocol loop test. Use it as a template or as your first tool server on-device.
3. **Runtime Survival Guide** — the Android-specific pitfalls nobody warns you about (Phantom Process Killer, stdout pollution, wake-lock myths).

## Directory of Termux/Android MCP Servers

> Badges: ✅ Verified on Device · ⚠️ Requires Termux:API · 🚫 PC/ADB-Dependent

| Project | Tools | Badge | Notes |
|---|---|---|---|
| [nano-mcp-system (this repo)](./nano) | 1+ | ✅ | Zero-dependency, stdlib-only, protocol-loop tested |
| Termux-API-Tools-MCP-Server | battery/sms/camera | ⚠️ | Requires Termux + Termux:API from same source (F-Droid) |
| htekdev/phone-mcp-server | 18 | ⚠️ | Same-source install requirement |
| xlisp/termux-mcp-server | 45+ | ⚠️ | Broad Termux API surface |
| wujie272/termux-mcp | 100+ | ⚠️ | Largest tool count, unverified on-device |
| MemPlato | 29 | ⚠️ | Runs inside Termux |
| Mobile MCP / Android Mobile MCP | varies | 🚫 | Designed for ADB from a host machine |
| ADB Friend | varies | 🚫 | ADB host-dependent |

*Badges are upgraded to ✅ only after an end-to-end run on a real device. PRs must include the device model, Android/Termux version and reproduction steps.*

## nano-mcp-system: the minimal MCP server for Termux

```bash
# run (it speaks JSON-RPC over stdio)
python3 nano/nano-mcp-system.py

# run the protocol loop test
python3 nano/test_client.py   # -> ALL CHECKS PASSED
```

Protocol surface (minimal promise, maximum compatibility):

- `initialize` → `protocolVersion` echoes the client's requested version if supported (`2025-06-18`, `2025-11-25`), otherwise falls back to the highest supported version per the MCP version-negotiation strategy; `capabilities: {"tools": {}}` (nothing more, so no client can break on unsupported capability negotiation)
- Battery reads degrade gracefully: `termux-api` → sysfs `capacity` → sysfs `uevent` (`POWER_SUPPLY_CAPACITY`) → `unavailable`
- `notifications/initialized` → silent (no response, per JSON-RPC spec)
- `ping` → `{}`
- `tools/list` → tool cards with `name` / `description` / `inputSchema`
- `tools/call` → `{"content": [{"type": "text", "text": "<serialized JSON>"}]}`

First tool: **`device_status`** — aggregates battery / storage / arch / memory with a **graceful degradation ladder**: `termux-battery-status` → sysfs → `"source": "unavailable"`. A missing sensor never crashes the tool call; the agent always gets usable JSON.

## Runtime Survival Guide (read before you connect anything)

### 1. stdout is sacred
Any `print()` inside an MCP server is a bug: one stray line and the client dies with a JSON-RPC Parse Error and hangs. Write all logs to `sys.stderr`, always `flush()`, and wrap the whole loop in a global `try/except` so tracebacks never leak to stdout. (nano-mcp-system.py already does this — copy the pattern.)

### 2. Phantom Process Killer (Android 12+)
Android 12+ kills "phantom" child processes and enforces a 32-process cap. **`termux-wake-lock` only prevents CPU sleep — it does NOT protect against OOM or phantom kills.**

Fix (requires ADB or Shizuku):
```bash
settings put global settings_enable_monitor_phantom_procs false
```
Two failure modes to distinguish:
- **A**: the Termux-side MCP server process gets killed → use the setting above, and start the server with `nohup` / `setsid`, redirecting logs to a file so it doesn't depend on a live terminal.
- **B**: the MCP client connects to Termux and Termux itself gets killed → same setting, plus keep the Termux session alive in a persistent foreground notification.

### 3. Install sources must match
If a tool depends on Termux:API, Termux and Termux:API **must come from the same store (F-Droid or GitHub)**, otherwise the `am`/Broadcast bridge silently fails.

### 4. Graceful degradation beats hard errors
Never let a tool call fail because a subsystem is missing (no termux-api, no root, locked-down sysfs). Return partial data with a `"source": "unavailable"` marker — an agent that sees an exception will assume the whole MCP server is broken.

## Contributing

PRs welcome, but a listing without proof will be rejected. Provide: device model, Android version, Termux version, client used (Claude Desktop / Cursor / Operit / ...), and reproduction steps.

## Related

- [AI-Android-Playbook](https://github.com/Lmeng486/AI-Android-Playbook) — companion repo: agent pitfall protocols & a runtime interceptor harness for Android.

## License

MIT
