# Edge MCP Failure Taxonomy

> **Every way an MCP server actually breaks on a phone — classified by root cause.**
> Not a list of bugs. A *taxonomy*: each class of failure, why it happens, the
> real-device case that proves it, and the mitigation. Every case below is drawn
> from a server that was actually installed and run on the device in this
> directory — none are hypothetical.

**Device:** Xiaomi `23013RK75C` · Android 15 (SDK 35) · aarch64 · no root · Termux 0.118.3 · Python 3.14.6
**Sources:** the five third-party verification reports in the [main README](../README.md) plus the lifecycle work in [nano-mcp-termux](https://github.com/Lmeng486/nano-mcp-termux).

---

## The taxonomy at a glance

| ID | Failure class | Typical symptom | Real-device case |
|---|---|---|---|
| **F1** | Unbuildable dependencies | `pip install` dies compiling a Rust/C extension | `rpds-py` on arm64/Py3.14 → 4 of 5 servers |
| **F2** | Transport blocked by the OS | HTTP loopback silently times out | `memplato` SSE/HTTP on Android 15 |
| **F3** | Orphaned process leaks | Grandchildren survive a timeout → Phantom Process Killer | `nano-mcp-termux` 1.0.0 vs 1.1.0 |
| **F4** | stdout pollution | Client dies with JSON-RPC Parse Error | universal (design hazard) |
| **F5** | Privilege-tier gaps | Tools need root/ADB/Shizuku the device lacks | `xlisp` adb tools, `wujie272` Shizuku tier |
| **F6** | Environment drift | Worked yesterday, fails today (versions, network policy) | `htekdev` openssl + MIUI netpolicy |
| **F7** | Architecture mismatch | A PC-shaped design carried onto a phone unchanged | `hyhAsma` SSH-to-localhost relay |
| **F8** | Docs ≠ implementation | README promises more than the code delivers | `wujie272` "120+" vs 72; `device://info` crash |
| **F9** | No graceful degradation | A missing subsystem fails the whole tool call | design rule in the Survival Guide |

---

## F1 — Unbuildable dependencies

**Symptom.** `pip install mcp` / `pip install fastmcp` / `pip install pydantic>=2`
fails on-device. The traceback bottoms out in a Rust or C build:
`rpds-py` needs Rust/maturin, `pydantic-core` needs a compiler, `numpy` needs a
cmake backend. On arm64 + Python 3.14 there are **no prebuilt wheels**.

**Why it happens.** The MCP Python ecosystem leans on compiled extensions. Wheel
coverage lags newest Python versions and non-x86 arches — exactly the phone case.

**Real-device evidence.** Four of the five third-party servers hit this:

| Server | Blocked by | Workaround actually used |
|---|---|---|
| `hyhAsma/termux-api-tools-mcp-server` | `fastmcp`/`mcp` won't install | ~75-line stdio JSON-RPC `fastmcp.py` shim; `paramiko` deps from Termux **apt** (precompiled) |
| `xlisp/termux-mcp-server` | `rpds-py` (via `mcp[cli]`) | local FastMCP-compatible shim |
| `wujie272/termux-mcp` | `rpds-py` | shim + `Context` class + `@mcp.resource()` support |
| `VChe-creator/memplato` | `pydantic>=2`, `numpy` | pin `pydantic<2` + `fastapi==0.95.2`; `numpy` → try/except (embeddings disabled); minimal `mcp` stub |

**Mitigations**
- Prefer **stdlib-only** servers (the `nano-*` pattern) — nothing to build.
- Ship the `pip install` path *and* an apt path: Termux **apt** packages are
  precompiled for arm64 (`python-cryptography`, `python-bcrypt`, `python-pynacl`).
- If you must depend on the SDK, document a **shim** path and pin working
  versions (`pydantic<2`). Do not assume the newest Python has wheels.

---

## F2 — Transport blocked by the OS

**Symptom.** A server starts and listens, but every client connection **times
out** — `curl`, raw `socket.connect()`, all of it. No error, just silence.

**Why it happens.** Android 15 / MIUI applies loopback interception that a
userspace server cannot see or bypass.

**Real-device evidence.** `VChe-creator/memplato` listens on `127.0.0.1:7333`
over SSE/HTTP. On-device:
- `curl` to `127.0.0.1:7333` and `::1:7333` → **timeout**.
- **Control test:** a process that listens on `7455` and connects to *itself* in
  the same process → **also times out**. That rules out the project and proves
  the block is OS-level.
- **Workaround that worked:** in-process calls to the same 29 tools (the `/mcp`
  endpoint just calls those functions) — semantically identical, HTTP bypassed.

**Mitigations**
- Prefer **stdio** transports — they are not subject to loopback interception.
- If you need HTTP, verify loopback on the target device *first*; otherwise run
  the handler in-process.
- Document the device class where HTTP is known-blocked.

---

## F3 — Orphaned process leaks (the Android-specific killer)

**Symptom.** A tool call times out; later, the device is under memory pressure or
Termux is killed wholesale. Nothing looks wrong at call time.

**Why it happens.** `subprocess.run(..., timeout=...)` terminates only the
**direct** child — the `sh -c` wrapper. Anything the shell already spawned is
reparented to init and **survives forever**. Android 12+ counts these and runs
the **Phantom Process Killer**; too many and the whole app group dies.

**Real-device evidence.** `nano-mcp-termux` ships a reproducible A/B regression:

```bash
python3 test_lifecycle_orphan.py
# current  nano_mcp_termux.py            leaked_grandchildren=0
# legacy   nano_mcp_termux_v10_backup.py leaked_grandchildren=1   <- the bug
# PASS
```

Same device, same test, only the spawning strategy differs. 1.0.0 leaks one
grandchild per timed-out call; 1.1.0 leaks zero.

**Mitigations**
- Spawn with `start_new_session=True`; tear down with
  `os.killpg(pgid, SIGTERM)` → `SIGKILL` so the **whole tree** dies.
- Add a parent-process watchdog + stdin-EOF detection so a dead client never
  leaves a zombie server.
- Ship the A/B regression test so the fix is provable, not asserted.

---

## F4 — stdout pollution

**Symptom.** The client dies with a **JSON-RPC Parse Error** and hangs, usually
right after startup.

**Why it happens.** Any stray `print()` inside a stdio server lands on the
protocol channel. One line is enough to corrupt the stream.

**Real-device evidence.** This is a design hazard rather than a specific
project's bug — which is why it is listed as Survival Guide rule #1. The
`nano-*` servers treat stdout-JSON-only as a **tested assertion** (part of the
32/32 protocol suite), not a convention.

**Mitigations**
- All logs → `sys.stderr`, always `flush()`.
- Wrap the whole loop in a global `try/except` so tracebacks never reach stdout.
- **Assert it in tests**: "stdout contains only JSON" is a checkable property.

---

## F5 — Privilege-tier gaps

**Symptom.** Some tools work, others return "not available" / degrade. The server
is fine; the device lacks the privilege tier.

**Why it happens.** Many servers assume root or ADB. Phones without root are the
common case, not the exception.

**Real-device evidence.**
- `xlisp/termux-mcp-server`: termux-api/Python-internal tools work
  out-of-the-box; the **adb family** needs `pkg install android-tools` +
  wireless-debugging pairing. `adb_setup_status` returns a **graceful
  degradation hint** instead of failing — the correct pattern.
- `wujie272/termux-mcp`: three-tier chain (Shizuku → ADB → Direct Termux).
  Direct-Termux tools work with no root; `shizuku_status` degrades gracefully
  ("未启动 — 请在 Shizuku App 中启动").

**Mitigations**
- Design a **privilege ladder** with a working bottom tier (no-root) and
  explicit degradation for the tiers above it.
- Never let a missing tier throw — return a status message the agent can act on.

---

## F6 — Environment drift

**Symptom.** A server that worked yesterday fails today. Not a code change — the
environment moved underneath it.

**Real-device evidence.**
- `htekdev/phone-mcp-server`: apt `nodejs` (v26.4.0) failed with
  `cannot locate symbol "OSSL_PROVIDER_add_conf_parameter"` — fixed by
  `apt-get install --only-upgrade openssl`. A shared-library drift, not a bug.
- **MIUI background network cut:** long-running Termux got its network blocked by
  per-UID policy (`dumpsys netpolicy` → `APP_STANDBY|APP_BACKGROUND`). Restored
  with `am set-standby-bucket com.termux active` + foregrounding the app.

**Mitigations**
- Document known-good version pins and the `openssl` upgrade step.
- For long-lived sessions, document the standby-bucket fix and keep a foreground
  notification alive.

---

## F7 — Architecture mismatch

**Symptom.** The server technically runs, but it carries a **PC-shaped design**
onto a phone, adding a layer that is pure overhead there.

**Real-device evidence.** `hyhAsma/termux-api-tools-mcp-server` (FastMCP) shells
**every** tool call through **paramiko SSH to `localhost:8022`** — a full SSH
stack to talk to the same device. `main` refuses to start without SSH
credentials; the 38 handlers only ran after bypassing `main` and starting
`sshd` + an ed25519 loopback key.

**Verdict:** the SSH-in-the-middle layer is **redundant when the client already
runs inside Termux** — direct `subprocess` calls would drop paramiko entirely.

**Mitigations**
- When the client and server share a device, skip the network hop.
- If a remote transport is needed, make it **optional**, not a startup gate.

---

## F8 — Docs ≠ implementation

**Symptom.** The README's headline number does not match what the server
actually exposes, or a documented resource crashes.

**Real-device evidence.**
- `wujie272/termux-mcp`: README advertises **"120+"** tools; the shipped default
  set is **72** (the extra modules, incl. a GitHub module, are disabled).
  `resources/list` → 8, as advertised.
- **A real bug found:** resource `device://info` crashes with
  `IndexError: list index out of range` in `resources.py:38` — uptime parsing
  has no fallback for empty output. Reported as upstream issue material.

**Mitigations**
- State the **default-load** tool count, not the sum across disabled modules.
- Add a fallback for every parse of external command output (empty output is a
  normal case, not an error case).

---

## F9 — No graceful degradation

**Symptom.** One missing subsystem (no termux-api, no root, locked sysfs) makes
a tool **throw**, and the agent concludes the whole server is broken.

**Why it matters.** An agent that sees an exception does not try the next tool —
it gives up on the server.

**Real-device evidence.** This is Survival Guide rule #4, and it is exactly what
the `nano-*` `device_status` demonstrates with its degradation ladder
(`termux-api` → sysfs `capacity` → sysfs `uevent` → `"source": "unavailable"`):
on the real device the full ladder reaches `termux-api`; under PRoot it falls
through to `unavailable` — **same code, no crash, honest data**.

**Mitigations**
- Return partial data with a `"source": "unavailable"` marker.
- Never let a tool call fail because a subsystem is absent.

---

## Checklist for MCP server authors targeting mobile

- [ ] **Zero compiled dependencies** — or ship a documented apt/shim fallback (F1).
- [ ] **stdio transport** by default; verify HTTP loopback before shipping it (F2).
- [ ] **`start_new_session=True` + `os.killpg`** on every spawned command (F3).
- [ ] **stdout is JSON-only**, and a test asserts it (F4).
- [ ] **Privilege ladder** with a working no-root bottom tier (F5).
- [ ] **Pinned versions + documented env fixes** (openssl, standby bucket) (F6).
- [ ] **No redundant network hop** when client and server share a device (F7).
- [ ] **Documented tool count = default-load count**; fallbacks on every parse (F8).
- [ ] **Graceful degradation** everywhere; no tool throws on a missing subsystem (F9).

---

*Part of the [awesome-termux-mcp](https://github.com/Lmeng486/awesome-termux-mcp)
verified-on-device series. Companion report:
[MCP on Mobile: Measured Overhead Report](./MCP-ON-MOBILE-OVERHEAD.md).*