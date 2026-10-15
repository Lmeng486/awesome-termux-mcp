# MCP on Mobile: Measured Overhead Report

> **What does an MCP server actually cost on a phone?**
> Every number below was read straight off a real device's stdio JSON-RPC
> surface — not quoted from a blog post, not estimated from a PC benchmark.
> The scripts that produced them ship in this repo (`scripts/`), so anyone can
> re-run the whole thing on their own hardware in under a minute.

**Measured on:** Xiaomi `23013RK75C` · Android 15 (SDK 35) · aarch64 · Termux 0.118.3 · Python 3.14.6
**Subject under test:** [`nano-mcp-termux`](https://github.com/Lmeng486/nano-mcp-termux) `@ main` — 4 tools, zero-dependency, single-file stdio server. The file measured is `nano_mcp_termux.py` at commit `00df8af` (27 571 B, `sha256 34709c02…e34b5`). Its source still declares `SERVER_VERSION = "1.1.0"`, but it is the `main` revision that came **after** the v1.1.0 tag: `a0030c5` rewrote all four tool descriptions and added annotations, which is what moved the catalog from ~1.3 KB to ~3.6 KB. Quoting this report against the bare `v1.1.0` tag will not reproduce the numbers below.
**Control environment:** PRoot Linux · Python 3.12.3 (same scripts, x86_64)
**Token counts:** two real tokenizers, run **fully offline** — Qwen2.5 BPE and GPT-2 byte-level BPE (§1)

---

## TL;DR

| Question | Measured answer |
|---|---|
| Handshake cost (`initialize`) | **152 bytes** |
| Tool catalog cost (`tools/list`, 4 tools) | **3 617 B** compact (3 714 B as written to the wire) — **798 tokens** (Qwen2.5) / **889 tokens** (GPT-2) |
| Single tool call payload (`device_status`) | **437 bytes** (device) / 415 bytes (PRoot) |
| Is JSON-RPC really "2–5 KB per call vs 200 B for protobuf"? | **No.** Measured gap is **3.3× (request)** and **1.3× (response)** |
| Local stdio round-trip latency | **sub-millisecond** (p50 ≈ 0.12 ms) |
| Do large tool catalogs eat the context window? | **Yes.** Extrapolated **~14 100 – 15 700 tokens** at 72 tools |

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

Byte counts are UTF-8 bytes of the exact bytes on the wire. Token counts are
**real tokenizer counts**, produced by `scripts/token_probe.py` running **fully
offline** against two independent vocabularies:

| Tokenizer | Vocabulary | Why it is included |
|---|---:|---|
| **Qwen2.5 BPE** | 151 665 | the most widely used open tokenizer family in edge LLM work |
| **GPT-2 byte-level BPE** | 50 257 | the classic `cl100k`-era baseline; also the tokenizer `tiktoken`'s `gpt2` encoding reproduces |

The two bracket the plausible range: the Qwen2.5 vocabulary is much larger and
packs more JSON punctuation per token, so it is the **lower bound**; GPT-2 is the
**upper bound**. Llama-family vocabularies could not be fetched from this network
(HF mirror returned 403), so they are *not* claimed. The legacy `chars / 4`
heuristic is printed alongside for continuity with earlier revisions of this
report — note that it lands **above** both real tokenizers on compact JSON,
because JSON punctuation is cheap to tokenize while the heuristic assumes prose.

Where a number is extrapolated rather than measured, it is marked
`(extrapolated)` in the output itself.

### Byte-count conventions (three distinct numbers, do not conflate them)

The same `tools/list` response yields three different byte counts depending on
how you serialise it. All three are reported here on purpose:

| Serialisation | Bytes | Used for |
|---|---:|---|
| **As written to the wire** (`json.dumps(obj, ensure_ascii=False)`, default separators) | **3 714** | what actually crosses stdio |
| **Compact, `ensure_ascii=False`** | **3 617** | §2.5 schema-scaling math |
| **Compact, `ensure_ascii=True`** | **3 623** | §2.2 catalog table (the historical number) |

Earlier revisions of this report mixed the last two without saying so. The
difference is real but tiny (`\uXXXX` escaping of the handful of non-ASCII
characters in the descriptions); the wire form is larger still because the
server uses `json.dumps`' default `", "` / `": "` separators rather than
compact ones. **When comparing against a packet capture, use 3 714.**

### Reproduction

```bash
# on any Termux / Linux / Raspberry Pi box
python3 scripts/measure_overhead.py            # human-readable
python3 scripts/measure_overhead.py --json     # machine-readable
python3 scripts/probe_bench.py
python3 scripts/token_probe.py                 # real-tokenizer re-count (offline)
```

`token_probe.py` needs `tokenizers` plus two local vocabulary files; it performs
**no network access**. Point it at any vocabulary you like:

```bash
TOKENIZER_FILE=/path/to/tokenizer.json python3 scripts/token_probe.py
```

To point the probes at a different server:

```bash
MCP_SERVER=/path/to/your_server.py python3 scripts/probe_bench.py
```

---

## 2. Findings

### 2.1 Handshake floor: 152 bytes

The `initialize` response is **152 bytes** in compact form (3 714-style wire form:
**166 B**, since the server writes `json.dumps` with default separators) —
identical in PRoot (Py 3.12.3) and on the real device (Py 3.14.6). Handshaking is
effectively free; there is no reason to avoid a fresh connection on a mobile
transport for payload reasons.

### 2.2 Tool catalog: 3 617 bytes, ~780–890 tokens, for 4 tools

`tools/list` returns **3 617 B** compact (`ensure_ascii=False`) — **3 623 B** with
`ensure_ascii=True`, **3 714 B** as actually written to stdio. Real-tokenizer
counts and per-tool schema cost:

| Tool | Schema bytes | Qwen2.5 tokens | GPT-2 tokens | `chars/4` (legacy) |
|---|---:|---:|---:|---:|
| `device_status` | 789 | 169 | 182 | 197 |
| `server_health` | 727 | 155 | 175 | 181 |
| `resolve_path` | 1 254 | 280 | 314 | 314 |
| `path_adapter` | 798 | 177 | 200 | 200 |
| **Total (4 tools)** | **3 617** | **781** | **871** | **892** |

*(Per-tool rows are the compact serialisation of each individual tool object; the
total is the whole `tools/list` response, so it carries the extra `{"jsonrpc",
"id", "result": {...}}` envelope — hence 781/871 rather than the naive sum
798/889. Both figures are printed by the probe.)*

Two things worth noticing:

- The legacy `chars / 4` column **over-estimates** by ~15–25 % here, not because
  it is wrong in general but because JSON-RPC schemas are punctuation-dense, and
  BPE vocabularies merge that punctuation aggressively. Anyone who quoted
  "≈1 100 tokens" from an earlier revision should use **~800 (Qwen2.5)** to
  **~890 (GPT-2)**.
- The heaviest tool (`resolve_path`, 1 254 B) is also the one with the richest
  argument surface — **schema cost tracks argument complexity, not tool count
  alone**. A server's tool catalog is *prepended context the model pays for on
  every session*, before it has done any work.

### 2.3 A single tool call is hundreds of bytes, not kilobytes

A real `device_status` call:

| Environment | Response bytes | Round-trip |
|---|---:|---:|
| Real device (Py 3.14.6) | **437** | 0.674 s / 0.786 s* |
| PRoot (Py 3.12.3) | **415** | 0.432 s |

*(Both figures are compact serialisations, consistent with §2.2. The same PRoot
response as actually written to stdio is **424 B** — see the convention table in §1.)*

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

> **Byte-count conventions** (same three-way split as §1). Both JSON-RPC figures in
> this table are *compact* re-serialisations (`separators=(",", ":")`) — the same
> convention as §2.3. The bytes the server actually writes to stdio for the same
> `device_status` call are **96 B** (request) and **425 B** (response, including the
> trailing newline; 424 B without it, the value quoted in §2.3). On the protobuf side
> the request is a bare `ToolCall` message and the response is the **content payload
> alone, with no protobuf envelope; wrapping it would only make the protobuf larger
> and the ratio smaller, so **1.3× is the conservative figure**. Absolute values also
> drift with the interpreter: the numbers above come from the real device
> (CPython 3.14.6), while PRoot (CPython 3.12.3) reproduces **415 B / 311 B**.

**Verdict: refuted.** The real overhead of JSON-RPC over a binary encoding for
this workload is **3.3× on the request and 1.3× on the response** — not 10–25×.
The "2–5 KB" figure is off by roughly **5–25×** for a realistic mobile tool
call.

Why the gap? The quoted figure tends to count the *entire* JSON-RPC envelope,
pretty-printed, with full schema echoes — or simply assumes a large payload that
this class of server does not produce. As actually written to stdio, a tool call
here is under half a kilobyte in both directions (96 B request, 425 B response).

**Practical consequence:** switching a mobile MCP server to protobuf would save
~66 bytes per request and ~106 bytes per response here. That is not where the
bytes are. **The transport encoding is a rounding error next to the schema
cost** (§2.5).

### 2.5 ✅ The real cost is schema scaling — and the worry is justified

Measured per-tool schema cost: **904.2 bytes/tool** (3 617 B ÷ 4 tools), which is
**195.3 Qwen2.5 tokens/tool** or **217.8 GPT-2 tokens/tool**. Extrapolated to the
tool counts of real Termux MCP servers listed in this directory:

| Tools | Est. catalog bytes | Qwen2.5 tokens | GPT-2 tokens | Source |
|---:|---:|---:|---:|---|
| 4 | 3 617 | 781 | 871 | **measured** |
| 19 | 17 181 | 3 710 | 4 137 | extrapolated |
| 29 | 26 223 | 5 662 | 6 315 | extrapolated |
| 38 | 34 362 | 7 420 | 8 274 | extrapolated |
| 52 | 47 021 | 10 153 | 11 323 | extrapolated |
| 72 | 65 106 | 14 058 | 15 678 | extrapolated |

*(Extrapolation assumes uniform per-tool cost; real catalogs vary with argument
complexity — treat these as order-of-magnitude, which is exactly how they are
labelled in the script output. The n = 4 token cells are the sum over the four
per-tool blobs; measuring the whole `tools/list` envelope instead adds ~17 tokens
for the `{"jsonrpc","id","result":…}` wrapper, giving 798 / 889.)*

The 19 / 29 / 38 / 52 / 72 columns are not arbitrary: they are the **actual
tool counts of the five third-party servers verified in this directory's main
README**. The mapping is deliberate — a 72-tool server projects to roughly
**14 000 – 15 700 tokens of catalog** before a single call is made.

**Verdict: confirmed, with a correction.** For a small edge model with a 4 K–8 K
context window, a large tool catalog is not a minor overhead — it is *most of the
window*. This, not the wire encoding, is the real mobile/edge MCP problem. But the
earlier `chars / 4` estimate of ~16 276 tokens at 72 tools was **too pessimistic**:
real tokenizers land ~4–14 % lower, because JSON punctuation is cheap to encode.

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
   server is **~14 100 – 15 700 tokens** (Qwen2.5 – GPT-2, §2.5) — fatal for
   4 K–8 K edge windows.
3. **Split large servers.** Expose a small "core" tool set by default and gate
   the rest behind a progressive-disclosure tool, rather than shipping 72
   schemas up front.
4. **Local stdio is free; subprocess spawn is not.** Keep the transport simple
   and make tool handlers cheap — or cache/aggregate the shell calls they wrap.
5. **Handshakes are cheap.** A fresh 152-byte `initialize` per session is
   affordable; do not build connection pooling for payload reasons.

---

## 4. Caveats (read before quoting)

- **Token counts come from two real tokenizers, run fully offline** — Qwen2.5 BPE
  (lower bound) and GPT-2 byte-level BPE (upper bound); the legacy `chars / 4`
  heuristic is kept only as a comparison column and is *not* the reported figure.
  Llama-family vocabularies are **not claimed** (the HF mirror returned 403).
  Byte counts are exact; token counts vary by vocabulary, so quote a range.
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
git clone https://github.com/Lmeng486/nano-mcp-termux /tmp/nano-mcp-termux
python3 scripts/measure_overhead.py
python3 scripts/probe_bench.py
python3 scripts/token_probe.py   # offline real-tokenizer re-count
```

This repository does not vendor the server under test. All three scripts look
for it in the same order -- first positional argument, then `$MCP_SERVER`, then
`./nano_mcp_termux.py`, then `/tmp/nano-mcp-termux/nano_mcp_termux.py` -- so keep
the second `git clone` above, or pass `MCP_SERVER=/path/to/server.py`. If none of
the four exists, the script prints the path it looked for and exits 2.

Scripts: [`scripts/measure_overhead.py`](../scripts/measure_overhead.py) ·
[`scripts/probe_bench.py`](../scripts/probe_bench.py) ·
[`scripts/token_probe.py`](../scripts/token_probe.py)

*Part of the [awesome-termux-mcp](https://github.com/Lmeng486/awesome-termux-mcp)
verified-on-device series. Companion: [nano-mcp-termux](https://github.com/Lmeng486/nano-mcp-termux).*
