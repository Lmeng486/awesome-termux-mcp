# MCP Survival Survey — Pre-registered Test Protocol

**Version:** 1.0 (pre-registered, before any testing)
**Date:** 2026-10-26
**Status:** Protocol frozen. Judgement criteria below are written BEFORE the first test run. Results will be filled into per-server survival cards afterwards, without retroactive edits to this file.

---

## 1. Why this exists

The most-starred MCP servers are written for desktop/server environments. Nobody has published a reproducible record of which of them actually survive on an Android/aarch64 phone under Termux. This survey fills that gap with a fixed, pre-registered procedure.

Motivating context (measured, see `MCP-ON-MOBILE-OVERHEAD.md`): a single server exposing 72 tools costs ~14K tokens just for `tools/list`. On a phone, both installability and token/RSS overhead matter more than on a 32 GB workstation.

## 2. Fixed test environment (single-device bias, declared up front)

| Item | Value |
|---|---|
| Device | Xiaomi 23013RK75C (Redmi K60E) |
| OS | Android 15 (SDK 35), MIUI |
| Arch | aarch64, no root |
| Runtime | Termux (proot-distro not used unless noted) |
| Node | whatever Termux pkg provides at test time (recorded per card) |
| Python | 3.x from Termux pkg (recorded per card) |
| Network | residential Wi-Fi, mainland China (proxy state recorded per card) |

Caveats: results are a **dated snapshot of one device**, not a distribution-wide claim. Other phones, other Termux versions, other network paths may differ. Every card carries the test date.

## 3. Judgement levels (frozen)

A server is graded at the highest level it fully passes:

| Level | Name | Pass condition | Typical failure modes |
|---|---|---|---|
| **L0** | Install | `install`/dependency resolution completes on aarch64/Android without patching | glibc-only wheels, prebuilt binaries without arm64, native modules needing NDK |
| **L1** | Handshake | `initialize` + `tools/list` succeed over stdio | crashes on start, entry point missing after install |
| **L2** | Real call | at least one tool executes end-to-end and returns a usable result | tool exists but requires desktop-only deps (browser, display, ADB host) |
| **L3** | Overhead measured | L2 pass + recorded token cost of `tools/list` + peak RSS | — (measurement, not pass/fail) |

Grades used in cards: ✅ (L2+), ⚠️ (partial — e.g. L1 pass but L2 blocked, or pass with heavy caveats), ❌ (L0/L1 fail). Every non-✅ grade must cite a failure class from `EDGE-MCP-FAILURE-TAXONOMY.md` (F1–F9).

## 4. Measurement procedure (same for every server)

1. Clean install into a fresh venv / fresh `npm` prefix (record exact commands).
2. Record install wall time and any warnings.
3. Handshake: `initialize` → `tools/list` via stdio JSON-RPC. The harness is a new minimal generic probe (`scripts/survival_probe.py`, added with the first batch), modelled on the `talk()` pattern of `nano/test_client.py` but server-agnostic (server command passed as argv, no hardcoded tool names).
4. Pick the tool the server's own README lists first as its flagship; call it once with minimal args. Record raw outcome.
5. Token cost: count tokens of the serialized `tools/list` output. Same dual-BPE method as `scripts/token_probe.py` (Qwen2.5 lower bound / GPT-2 upper bound, `chars/4` printed alongside for continuity); vocab files reused from `/root/tokcheck` when present.
6. RSS: peak RSS of the server process (`server_health`-style /proc sampling).
7. Stop. No tuning, no workarounds beyond what the README itself documents. If a fix requires patching upstream code, that is an L0 fail with the patch noted.

Anti-HARKing rule: predictions below were written before testing. Cards link back here; deviations between prediction and outcome are reported as-is.

## 5. First batch (5 servers) — pre-registered predictions

Selection basis: top of the real star ranking (measured 2026-10-26 via GitHub API), filtered to actual MCP servers (platform-type projects excluded), covering different implementation stacks.

| # | Server (slug) | Stars @ 2026-10-26 | Stack | Prediction | Reason (one line) |
|---|---|---|---|---|---|
| 1 | upstash/context7 | 63,719 | Node, pure API client | ✅ | no native deps, stdio default |
| 2 | microsoft/playwright-mcp | 38,656 | Node + browser binary | ❌ | needs Chromium arm64 build under Termux; `playwright install` historically fails on Android |
| 3 | github/github-mcp-server | 33,977 | Go (official) | ⚠️ | arm64 release binary likely runs; needs PAT; docker image path is dead on device |
| 4 | firecrawl/firecrawl-mcp-server | 7,691 | Node, API client | ✅ | thin client to hosted API |
| 5 | mobile-next/mobile-mcp | 10,011 | Node + adb/appium | ⚠️ | automating Android *from* Android is circular; adb-in-Termux is the open question |

Note the built-in irony of #5: an MCP server whose purpose is mobile automation, tested on the very platform it automates.

## 6. Survival card template

```markdown
## <server> (<org/repo>) — <grade ✅/⚠️/❌>
- Tested: YYYY-MM-DD · Termux <pkg versions> · <network note>
- Stars at test time: N (source: GitHub API)
- L0 install: ✅/❌ — <one line, incl. wall time>
- L1 handshake: ✅/❌ — tools/list returned N tools
- L2 real call: ✅/❌ — <tool called> → <outcome>
- L3 overhead: tools/list ≈ X tokens · peak RSS ≈ Y MB
- Failure class: F? (EDGE-MCP-FAILURE-TAXONOMY) or "—"
- Repro: <minimal command sequence, paste-ready>
- Upstream thread: <issue/discussion URL, filled after posting>
```

## 7. Publication policy

1. Report lands in this repo (`docs/`) first — complete, dated, with repro commands.
2. One issue/discussion per tested upstream repo, linking back to the card. Card gets the upstream URL added (two-way link).
3. No maintenance promise: data is a snapshot; issues are drive-by reports, not support tickets. Survey ends whenever the operator stops; no roadmap debt.

## 8. Scope boundaries

- Not tested: OAuth-based servers requiring a hosted redirect endpoint, servers whose flagship tool needs a desktop GUI session, Windows/macOS-only builds.
- Out of scope claims: battery drain, thermal, multi-day stability. This is an installability + handshake + single-call + overhead survey.

---

*Pre-registration rationale: writing pass criteria and predictions before running prevents post-hoc rationalisation ("it failed but that's fine because..."). If reality disagrees with the table in §5, the table loses, and that is a result too.*
