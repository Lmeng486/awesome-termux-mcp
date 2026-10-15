# MCP on Mobile: Measured Overhead Report

> **What does an MCP server actually cost on a phone?**
> Every number below was read straight off a real device's stdio JSON-RPC
> surface — not quoted from a blog post, not estimated from a PC benchmark.
> The scripts that produced them ship in this repo (`scripts/`), so anyone can
> re-run the whole thing on their own hardware in under a minute.

**Measured on:** Xiaomi `23013RK75C` · Android 15 (SDK 35) · aarch64 · Termux 0.118.3 · Python 3.14.6
**Subject under test:** [`nano-mcp-termux`](https://github.com/Lmeng486/nano-mcp-termux) v1.1.0 (4 tools, zero-dependency, single-file stdio server)
**Control environment:** PRoot Linux · Python 3.12.3 (same scripts, x86_64)

---

## TL;DR

| Question | Measured answer |
|---|---|
| Handshake cost (`initialize`) | **152 bytes** |
| Tool catalog cost (`tools/list`, 4 tools) | **3 623 bytes ≈ 1 100 tokens** |
| Single tool call payload (`device_status`) | **437 bytes** (device) / 415 bytes (PRoot) |
| Is JSON-RPC really "2–5 KB per call vs 200 B for protobuf"? | **No.** Measured gap is **3.3× (request)** and **1.3× (response)** |
| Local stdio round-trip latency | **sub-millisecond** (p50 ≈ 0.12 ms) |
| Do large tool catalogs eat the context window? | **Yes.** Extrapolated **~16 276 tokens** at 72 tools |

Two of these overturn things that are commonly repeated online, and one of them
**confirms** the biggest real worry for edge models. Details below.

---

## 1. Method

All figures come from two stdlib-only scripts:

- **`scripts/measure_overhead.py`** — opens a stdio JSON-RPC session with the
  server and reads the *server's own response bytes* for `initialize`,
  `tools/list` (plus per-tool breakdown) and a real `tools/call`.
- **`scripts/probe_bench.py`** — three benches: (A) wire-size comparison of the
  same call encoded as JSON-RPC vs a hand-rolled protobuf encoder (varint,
  zero protobuf dependency); (B) persistent-session latency over 20 `ping`
  round-trips; (C) schema scaling extrapolation.

Byte counts are UTF-8 bytes of the exact bytes on the wire. Token counts are a
**`chars / 4` heuristic, explicitly labelled as an estimate** — not a tokenizer
count. Where a number is extrapolated rather than measured, it is marked
`(extrapolated)` in the output itself.

### Reproduction

```bash
# on any Termux / Linux / Raspberry Pi box
python3 scripts/measure_overhead.py            # human-readable
python3 scripts/measure_overhead.py --json     # machine-readable
python3 scripts/probe_bench.py
```

To point the probes at a different server:

```bash
MCP_SERVER=/path/to/your_server.py python3 scripts/probe_bench.py
```

---

## 2. Findings

### 2.1 Handshake floor: 152 bytes

The `initialize` response is **152 bytes** — identical in PRoot (Py 3.12.3) and
on the real device (Py 3.14.6). Handshaking is effectively free; there is no
reason to avoid a fresh connection on a mobile transport for payload reasons.

### 2.2 Tool catalog: 3 623 bytes ≈ 1 100 tokens for 4 tools

`tools/list` returns **3 623 bytes** for this server's 4 tools. Per-tool schema
cost:

| Tool | Schema bytes | Est. tokens |
|---|---:|---:|
| `device_status` | 789 | 197 |
| `server_health` | 727 | 181 |
| `resolve_path` | 1 254 | 314 |
| `path_adapter` | 798 | 200 |
| **Total (4 tools)** | **3 623** | **~1 100** |

The heaviest tool (`resolve_path`, 1 254 B) is also the one with the richest
argument surface — **schema cost tracks argument complexity, not tool count
alone**. A server's tool catalog is *prepended context the model pays for on
every session*, before it has done any work.

### 2.3 A single tool call is hundreds of bytes, not kilobytes

A real `device_status` call:

| Environment | Response bytes | Round-trip |
|---|---:|---:|
| Real device (Py 3.14.6) | **437** | 0.674 s / 0.786 s* |
| PRoot (Py 3.12.3) | **415** | 0.432 s |

\* two independent runs, showing run-to-run variance.

The payload is a few hundred bytes of JSON. The round-trip time is dominated by
**spawning the underlying `termux-*` / `df` / `free` subprocesses**, not by the
JSON-RPC framing.

### 2.4 ⚠️ The "2–5 KB vs 200 B" claim does not survive measurement

A widely-repeated argument for a binary encoding runs roughly:

> "An MCP tool call costs 2–5 KB in JSON-RPC, but only ~200 bytes in protobuf —
> so JSON-RPC is 10–25× heavier."

`probe_bench.py` encodes the **same** `device_status` call both ways and
measures the real bytes:

| | JSON-RPC | protobuf | ratio |
|---|---:|---:|---:|
| **Request** | 95 B | 29 B | **3.3×** |
| **Response** | 437 B | 331 B | **1.3×** |

**Verdict: refuted.** The real overhead of JSON-RPC over a binary encoding for
this workload is **3.3× on the request and 1.3× on the response** — not 10–25×.
The "2–5 KB" figure is off by roughly **5–25×** for a realistic mobile tool
call.

Why the gap? The quoted figure tends to count the *entire* JSON-RPC envelope,
pretty-printed, with full schema echoes — or simply assumes a large payload that
this class of server does not produce. On the wire, with compact separators, a
tool call is a few hundred bytes.

**Practical consequence:** switching a mobile MCP server to protobuf would save
~66 bytes per request and ~106 bytes per response here. That is not where the
bytes are. **The transport encoding is a rounding error next to the schema
cost** (§2.5).

### 2.5 ✅ The real cost is schema scaling — and the worry is justified

Measured per-tool schema cost: **904.2 bytes/tool** (3 617 B ÷ 4 tools).
Extrapolated to the tool counts of real Termux MCP servers listed in this
directory:

| Tools | Est. catalog bytes | Est. tokens | Source |
|---:|---:|---:|---|
| 4 | 3 617 | ~904 | **measured** |
| 19 | 17 181 | ~4 295 | extrapolated |
| 29 | 26 223 | ~6 556 | extrapolated |
| 38 | 34 362 | ~8 590 | extrapolated |
| 52 | 47 021 | ~11 755 | extrapolated |
| 72 | 65 106 | ~16 276 | extrapolated |

*(Extrapolation assumes uniform per-tool cost; real catalogs vary with argument
complexity — treat these as order-of-magnitude, which is exactly how they are
labelled in the script output.)*

The 19 / 29 / 38 / 52 / 72 columns are not arbitrary: they are the **actual
tool counts of the five third-party servers verified in this directory's main
README**. The mapping is deliberate — a 72-tool server projects to roughly
**16 276 tokens of catalog** before a single call is made.

**Verdict: confirmed.** For a small edge model with a 4 K–8 K context window,
a large tool catalog is not a minor overhead — it is *most of the window*. This,
not the wire encoding, is the real mobile/edge MCP problem.

### 2.6 Local stdio latency is negligible

20 sequential `ping` round-trips over one persistent stdio session:

| Run | min | p50 | p95 | max |
|---|---:|---:|---:|---:|
| Run 1 | 0.201 ms | 0.210 ms | 0.262 ms | 0.328 ms |
| Run 2 | 0.111 ms | 0.117 ms | 0.205 ms | 0.214 ms |

Sub-millisecond, with visible run-to-run variance from device load. **The local
stdio transport is not the bottleneck** — per-call *latency* concerns should be
directed at subprocess spawn cost (§2.3) and model inference, not at the pipe.

---

## 3. Implications for mobile / edge MCP

1. **Don't optimise the encoding first.** JSON-RPC → protobuf buys ~3.3×/1.3×
   on wire bytes (§2.4), which is negligible against schema cost. Optimise the
   *catalog* before the *codec*.
2. **Tool catalog size is the budget that matters.** Every tool a server exposes
   is context the model pays for on every session. At ~904 B/tool, a 72-tool
   server is ~16 K tokens — fatal for 4 K–8 K edge windows.
3. **Split large servers.** Expose a small "core" tool set by default and gate
   the rest behind a progressive-disclosure tool, rather than shipping 72
   schemas up front.
4. **Local stdio is free; subprocess spawn is not.** Keep the transport simple
   and make tool handlers cheap — or cache/aggregate the shell calls they wrap.
5. **Handshakes are cheap.** A fresh 152-byte `initialize` per session is
   affordable; do not build connection pooling for payload reasons.

---

## 4. Caveats (read before quoting)

- **Token counts are `chars / 4` heuristics**, explicitly labelled as estimates.
  A real tokenizer will differ; the byte counts, however, are exact.
- **§2.5 beyond 4 tools is extrapolation**, not measurement. It assumes uniform
  per-tool cost and is marked as such in the script output.
- **Latency and round-trip figures vary run to run** with device load; two runs
  are reported rather than a single cherry-picked number.
- **One device, one Android version, one server.** These are reproducible
  baselines, not universal constants. Re-run the scripts on your hardware.

---

## 5. Reproduce / cite

```bash
git clone https://github.com/Lmeng486/awesome-termux-mcp
cd awesome-termux-mcp
python3 scripts/measure_overhead.py
python3 scripts/probe_bench.py
```

Scripts: [`scripts/measure_overhead.py`](../scripts/measure_overhead.py) ·
[`scripts/probe_bench.py`](../scripts/probe_bench.py)

*Part of the [awesome-termux-mcp](https://github.com/Lmeng486/awesome-termux-mcp)
verified-on-device series. Companion: [nano-mcp-termux](https://github.com/Lmeng486/nano-mcp-termux).*
