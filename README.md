# awesome-termux-mcp

> **A Curated Directory of Verified MCP Servers on Android (Termux / PRoot) — with a Zero-Dependency Nano Prototype & Runtime Survival Guides.**

[![CI](https://github.com/Lmeng486/awesome-termux-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/Lmeng486/awesome-termux-mcp/actions/workflows/ci.yml)

Most MCP (Model Context Protocol) servers assume a PC with Docker and Node. Almost nothing is **curated, tested and documented for running directly on an Android phone inside Termux/PRoot**. This repo fills that gap:

1. **Verified directory** — every listed server carries a real-device badge (see below).
2. **nano-mcp-system.py** — a single-file, zero-dependency MCP server (~145 lines, Python stdlib only) that passes a full JSON-RPC protocol loop test. Use it as a template or as your first tool server on-device.
3. **Runtime Survival Guide** — the Android-specific pitfalls nobody warns you about (Phantom Process Killer, stdout pollution, wake-lock myths).

## Directory of Termux/Android MCP Servers

> Badges: ✅ Verified on Device · ⚠️ Requires Termux:API · 🚫 PC/ADB-Dependent

| Project | Tools | Badge | Notes |
|---|---|---|---|
| [nano-mcp-system (this repo)](./nano) | 1+ | ✅ | Verified on device — 13/13 checks, battery via termux-api |
| [nano-mcp-termux](https://github.com/Lmeng486/nano-mcp-termux) | 4 | ✅ | Verified on device — 32/32 protocol checks + orphan-leak A/B regression; process-group lifecycle & Android path adapter |
| [Termux-API-Tools-MCP-Server](https://github.com/hyhAsma/termux-api-tools-mcp-server) | 38 | ⚠️→✅* | Verified on device — protocol + full tool surface live; see report below |
| [htekdev/phone-mcp-server](https://github.com/htekdev/phone-mcp-server) | 19 | ⚠️→✅* | Verified on device — Streamable HTTP; 19 tools live, battery/flashlight/volume/device_info/shell tested; see report below |
| [xlisp/termux-mcp-server](https://github.com/xlisp/termux-mcp-server) | 52 | ⚠️→✅* | Verified on device — stdio; 52 tools live, 7 read-only tools tested end-to-end; see report below |
| [wujie272/termux-mcp](https://github.com/wujie272/termux-mcp) | 72 | ⚠️→✅* | Verified on device — stdio; 72 tools + 8 resources live, 10 read-only calls tested end-to-end; see report below |
| [VChe-creator/memplato](https://github.com/VChe-creator/memplato) | 29 | ⚠️→✅* | Verified on device — FastAPI/SSE; server starts, 29 tools live, 6 read-only tools tested in-process (HTTP loopback blocked by device); see report below |
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

## Verified on Device (real hardware report)

**Device:** Xiaomi `23013RK75C` · Android 15 (SDK 35) · aarch64
**Environment:** Termux `0.118.3` (GitHub release) · Termux:API app `0.53.0` · Python `3.14.6`

- `test_client.py`: **13/13 PASS** on-device (version negotiation, error codes, stderr/stdout hygiene, degradation ladder)
- `device_status` real output (battery via **highest ladder rung `termux-api`**):
  ```json
  {"battery": {"percent": 60, "source": "termux-api"},
   "storage": {"source": "df", "raw": "/dev/block/dm-58 462G 365G 97G 79%"},
   "arch": "aarch64",
   "memory": {"source": "free", "raw": "Mem: 15152 total / 3559 avail"}}
  ```
- Proot (simulated) vs device contrast: in proot the battery rung falls through to `unavailable`; on real Termux the full ladder up to `termux-api` works — exactly the graceful degradation the design promises.

### Sibling project: `nano-mcp-termux` (4 tools, 1.1.0)

Same device & Termux environment. Where `nano-mcp-system` stops at "one tool, minimal promise", `nano-mcp-termux` pushes the same zero-dependency, single-file idea into the two places MCP servers on phones actually break:

- **`[lifecycle]` no orphaned processes** — 1.0.0 used `subprocess.run(..., timeout=...)`, which kills only the direct `sh -c` child; grandchildren get reparented to init and survive forever (the exact leak class that trips Phantom Process Killer). 1.1.0 spawns with `start_new_session=True` and tears down with `os.killpg(pgid, SIGTERM)` → `SIGKILL`.
  Reproducible A/B proof shipped in-repo: `python3 test_lifecycle_orphan.py` → `current leaked_grandchildren=0` / `legacy leaked_grandchildren=1`.
- **`[lifecycle]` self-terminating server** — parent watchdog + stdin-EOF detection + optional idle timeout, so a dead client never leaves a zombie server.
- **`[paths]` Android/Termux path adapter** — resolves `/sdcard` ↔ `/storage/emulated/0` ↔ `$HOME/storage/shared`, flags `noexec` mounts, case-insensitive filesystems and shell-quoting hazards before a tool call ever reaches a shell.
- **`server_health`** — pid/ppid/env, uptime, request counters, live children, reaping policy, RSS, and a Phantom Process Killer risk assessment.

Protocol suite: **32/32 PASS** (`python3 test_client.py`), including version negotiation across `2024-11-05` / `2025-06-18` / `2025-11-25`, error codes `-32602` / `-32700`, stdout-JSON-only hygiene and stdin-close self-termination.

### Third-party verification: `hyhAsma/termux-api-tools-mcp-server` (38 tools)

Same device & Termux environment. Findings (tested read-only tools only; no `send_sms`/`telephony_call`/camera writes were invoked):

- **Architecture:** PC-oriented design — the server (FastMCP) shells every tool call through **paramiko SSH** to `localhost:8022`. `main` refuses to start without SSH credentials; we bypassed only the `main` gate and ran its `mcp` object directly via a 5-line loader (`runner.py`) — **all 38 `@mcp.tool` handlers ran unmodified**.
- **Dependency reality on Termux arm64:** `fastmcp`/`mcp` fail to install (rpds-py needs Rust/maturin; watchfiles won't build). We substituted a ~75-line stdio JSON-RPC `fastmcp.py` shim implementing `@mcp.tool()`, `initialize`, `tools/list`, `tools/call`. Business code untouched. `paramiko` itself installs fine once `python-cryptography`/`python-bcrypt`/`python-pynacl` come from Termux's **apt** (precompiled), not pip.
- **`tools/list`:** 38 tools returned live, matching source exactly — battery, brightness, call_log, camera_info/photo, clipboard get/set, contact_list, dialog, download, fingerprint, infrared ×2, location, media_player/scan, microphone_record, notification ×2, sensor, share, sms_list/**sms_send**, storage_get, telephony_call/cellinfo/deviceinfo, toast, torch, tts ×2, usb, vibrate, volume, wallpaper, wifi ×3.
- **End-to-end `tools/call`** (after `sshd` started + ed25519 key loopback):
  ```json
  {"present": true, "technology": "Li-poly", "health": "GOOD", "plugged": "UNPLUGGED",
   "status": "DISCHARGING", "temperature": 42.8, "voltage": 4193, "current": 1216000,
   "percentage": 80, "level": 80, "scale": 100, "charge_counter": 3188, "cycle": 827}
  ```
- **Verdict:** protocol and full tool surface are real and functional on-device once (a) an SSH transport shim replaces unbuilt Rust deps and (b) sshd runs on the phone itself. The SSH-in-the-middle design is redundant when the client already runs inside Termux — direct `subprocess` calls would drop the paramiko layer entirely.
- Repro: `pip install paramiko` (apt: `python-cryptography python-bcrypt python-pynacl openssh`); place a `fastmcp.py` shim on `sys.path` (fastmcp itself cannot build); `ssh-keygen` + `sshd`; load module, drive `mcp` via stdio JSON-RPC.

### Third-party verification: `htekdev/phone-mcp-server` (19 tools)
Same device. Findings (read-only tools only; `send_sms`/`make_call`/`set_clipboard`/`record_audio`/`take_photo` were never invoked):
- **Architecture:** the only Streamable-HTTP entry in this directory — Node.js + Express + `@modelcontextprotocol/sdk`, listens on `:3000` (`/mcp` POST/GET/DELETE + `/health`), sessions via `mcp-session-id`. Zero root required; every tool shells out to `termux-*` from Termux:API.
- **Termux reality:** apt `nodejs` (v26.4.0) initially failed with `cannot locate symbol "OSSL_PROVIDER_add_conf_parameter"` — fixed by `apt-get install --only-upgrade openssl`. Long-background Termux also got network-cut by MIUI per-UID policy (`dumpsys netpolicy` shows `APP_STANDBY|APP_BACKGROUND`); `am set-standby-bucket com.termux active` + foregrounding the app restored it. Neither is a project defect.
- **Protocol handshake (raw curl):** `initialize` → `protocolVersion 2025-03-26`, serverInfo `phone-mcp 1.0.0`; `tools/list` → **19 tools live** (18 Termux:API + 1 `shell` bonus with a `BLOCKED_COMMANDS` denylist: `rm -rf /`, `mkfs`, `dd if=`, `reboot`, `shutdown`, `> /dev/`, `chmod 777 /`).
- **End-to-end `tools/call`** (all via real HTTP round-trips):
  - `get_battery`: `{"percentage": 58, "technology": "Li-poly", "temperature": 38.5, "cycle": 828, ...}`
  - `get_volume`: 6 audio streams with real values (call 9/11, alarm 15/15, ...)
  - `device_info`: platform android/arm64, uptime, memory, battery + WiFi (`ip 192.168.2.105`, `link_speed 432 Mbps`) panorama
  - `flashlight`: `state:"on"` → "Flashlight turned on" → `state:"off"` → closed loop ✅
  - `shell`: `echo hello-from-mcp` → `hello-from-mcp` (safe echo-level check only)
- **Verdict:** design is sound for Termux — no root, no SSH detour, plain `execFile("termux-*")`. Streamable HTTP makes it reachable from other devices on the LAN too (a plus the stdio projects lack). Only friction is Termux-side environment upkeep (openssl version, MIUI background network cuts).
- Repro: inside Termux `pkg install nodejs-lts termux-api`; `npm install`; `node server.js`; POST `initialize` with `Accept: application/json, text/event-stream`, keep the returned `mcp-session-id`, then `tools/list` / `tools/call`.
## Runtime Survival Guide (read before you connect anything)

### Third-party verification: `xlisp/termux-mcp-server` (52 tools)
Same device (Xiaomi 23013RK75C, Android 15, no root, Termux 0.118.3, Python 3.14.6).
- **Architecture**: single-file Python stdio MCP server, `mcp[cli]>=1.2.0` (FastMCP), 52 tools in two families: termux-api direct calls and adb-routed commands (Android 12+ auto-routes `_ADB_REQUIRED_CMDS` through `adb shell`). Ships a `BLOCKED_COMMANDS` blacklist (rm/mkfs/dd/shutdown/...).
- **Reality on Termux/Py3.14**: `pip install mcp` fails — `rpds-py` has no arm64 Py3.14 wheel and source build dies. Verified against the official protocol with a local FastMCP-compatible shim.
- **Handshake**: `initialize` → `termux-control 0.1.0`, protocol 2024-11-05; `tools/list` → **52 tools** (README claims 45+, actual is higher).
- **End-to-end `tools/call` (7 read-only tools, zero write calls)**: `get_battery_status` → 54% / Li-poly / 38.7°C / cycle 828; `get_device_info` → Redmi 23013RK75C, Android 15 SDK 35, aarch64; `get_volume` → 6 streams (call 9/11, alarm 15/15); `get_sensor_list` → 70+ hardware sensors; `list_directory` → real Termux home listing; `get_storage_info` → 462G/97G avail/80%; `adb_setup_status` → graceful degradation hint ("pkg install android-tools") — expected without adb, not a project defect.
- **Verdict**: ✅ works as advertised. termux-api/Python-internal tools are usable out-of-the-box without root; adb-family tools require `pkg install android-tools` + wireless debugging pairing (normal Android 12+ gate, not a bug).
- **Repro**: clone repo → `python termux_mcp_server.py` under any MCP stdio client (or mcp[cli] on Py<3.14) → initialize → tools/list → tools/call.

### Third-party verification: wujie272/termux-mcp (72 tools)

- **Architecture**: Full refactor of xlisp/termux-mcp-server into a multi-module package (`termux_mcp/`), v0.4.0, MIT. FastMCP + stdio (`server.py`) / HTTP (`http_server.py`, port 3000) dual entry. Layered tool loading, 8 MCP Resources, security gates (`TERMUX_MCP_READONLY`, `TERMUX_MCP_ALLOW_SHELL`), three-tier privilege chain (Shizuku rish → ADB → Direct Termux).
- **Reality on Termux/Py3.14**: `pip install mcp` fails (rpds-py has no arm64 Py3.14 wheel) — verified via a local FastMCP shim. Shim needed 3 additions for this project: a `Context` class (tools use `await ctx.report_progress`), auto-injection of `ctx` into tool calls, and `@mcp.resource()` support + `resources/list`/`resources/read` methods.
- **Handshake**: `initialize` → `termux-control`, protocol 2024-11-05. **tools/list → 72 tools** (README claims "120+" across all modules incl. a disabled GitHub module — the shipped default set is 72). **resources/list → 8 resources** as advertised.
- **End-to-end read-only tests**: `get_battery_status` (real: 38%, Li-poly, 41.8°C, cycle 828, DISCHARGING); `get_device_info` (Model 23013RK75C, Android 15, aarch64, uptime 7:46); `get_wifi_info` (returns data; ssid masked by Android 15 permission limits); `get_storage_info` (462G/365G/97G, 80%); `get_volume` (6 streams); `list_installed_packages` (dpkg output); `read_file` (real file content); `search_files` (works, injected ctx required); `shizuku_status` (graceful degradation: "未启动 — 请在 Shizuku App 中启动"); `device_health` (health score 100/100, though battery/storage sub-checks failed to parse); `resources/read device://battery` (real JSON battery data).
- **Found a real bug**: resource `device://info` crashes with `IndexError: list index out of range` in `resources.py:38` (uptime parsing has no fallback for empty output). Reported as upstream issue material.
- **Verdict**: ✅ works as advertised on the Direct-Termux tier, no root needed. Shizuku/ADB-tier tools degrade gracefully with clear messages. Watch: README tool count (120+) overstates the default-load set (72).
- **Repro**: `curl -sL https://codeload.github.com/wujie272/termux-mcp/tar.gz/refs/heads/master | tar xz && python server.py` on Termux Python 3.14 (with FastMCP shim due to rpds-py).

### Third-party verification: VChe-creator/memplato (29 tools)
- **Architecture**: Flutter Android app + Python FastAPI MCP server (`assets/memplato_server.py`, 1517 lines) exposing 29 `memplato_*` tools over SSE (`/sse`) + a hand-written JSON-RPC `/mcp` endpoint (port 7333, SQLite at `~/.memplato_mobile/palace.db`). Repo `github.com/MemPlato` from the README is a 404 — real repo found via GitHub API: `VChe-creator/memplato`, AGPL-3.0, v1.0.8 MVP.
- **Reality on Termux/Py3.14**: `pip install mcp` / `pydantic>=2` / `numpy` all fail to compile (rpds-py / pydantic-core / cmake backend) — pinned `pydantic<2` + `fastapi==0.95.2` works, `numpy` patched to a try/except import (server degrades to fulltext search, embeddings disabled), and a minimal `mcp` stub package supplies `Server`/`Tool`/`TextContent`/`SseServerTransport` (the script only uses the decorator registry, never the request loop).
- **Server startup**: ✅ `PYTHONPATH=<stub dir> python assets/memplato_server.py` → uvicorn on `0.0.0.0:7333`, `[OK] memplato Mobile v1.0.8 running on port 7333`, embeddings gracefully disabled (no ONNX model).
- **HTTP loopback is device-blocked**: `curl` and raw `socket.connect()` to `127.0.0.1:7333` and `::1:7333` all time out — a decisive control test (listen on 7455 then connect to self, same process, no server involved) **also times out**, proving the block is Android-15/MIUI-level loopback interception, not a project bug.
- **In-process MCP test (bypasses HTTP, semantically identical — the `/mcp` endpoint just calls these functions)**: `list_mcp_tools()` → **29 tools**, matching the README claim exactly. 6 read-only tools called end-to-end: `memplato_status` (`{"status":"ok","server":"memplato Mobile v1.0.8","drawers":0,"embeddings":false,"port":7333}`), `memplato_list_wings`, `memplato_get_taxonomy`, `memplato_kg_stats`, `memplato_graph_stats`, `memplato_search(query="test")` — all return valid JSON.
- **Verdict**: ✅ server core works on device with moderate dependency shims; the SSH-relay / autossh tunnel path (relay.memplato.com) was not tested (requires external network + app authorization, out of scope). Watch: HTTP transport unusable on MIUI-loopback-restricted devices — stdio/in-process or a TCP-capable environment is needed.
- **Repro**: `curl -sL https://codeload.github.com/VChe-creator/memplato/tar.gz/refs/heads/main | tar xz && cd memplato-main && PYTHONPATH=<stub> python assets/memplato_server.py` on Termux Python 3.14.

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

**Mandatory for any new tool that spawns processes:** client `arguments` MUST be passed as argument arrays or escaped with `shlex.quote()` — never interpolated into a command string. PRs violating this will be rejected.

Listings must not require disabling security mechanisms, or permissions beyond what their stated features need.

## Security

- **Least privilege by design** — runs as the Termux sandbox user, no root, no ADB. Worst case = the Termux app's own permissions.
- **No arbitrary command execution** — tools are a static whitelist (`device_status` only). Client `arguments` never reach a shell.
- **Zero dependencies** — ~165 lines of stdlib-only Python, fully auditable before you run it.
- **Read-only** — collects device metadata (battery/storage/arch/memory). No location, no contacts, no network egress, no writes.
- **stdio is the trust boundary** — communicates over stdin/stdout pipes only; no TCP port is ever opened.
- Disabling Phantom Process Killer (`settings` / `device_config`) is a **manual user action** with ADB/Shizuku. The MCP server itself never executes it.

## Related

- [AI-Android-Playbook](https://github.com/Lmeng486/AI-Android-Playbook) — companion repo: agent pitfall protocols & a runtime interceptor harness for Android.

## License

MIT
