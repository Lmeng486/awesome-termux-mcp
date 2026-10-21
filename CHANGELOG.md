# Changelog

All notable changes to this repository are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]
### Added
- README: linked the Dev.to announcement write-up (Showdev: A zero-dependency MCP server that runs on Android Termux) under Related.
- `docs/MCP-ON-MOBILE-OVERHEAD.md`: real-device measured overhead report
  (handshake bytes, tool-catalog token cost, JSON-RPC vs protobuf wire size,
  schema-scaling extrapolation). Refutes the widely-quoted "2–5 KB per call vs
  200 B protobuf" figure (measured: 3.3× request, 1.3× response) and confirms
  that tool-catalog schema cost — not wire encoding — is the real edge problem.
- `docs/EDGE-MCP-FAILURE-TAXONOMY.md`: F1–F9 root-cause taxonomy of how MCP
  servers actually break on Android, distilled from the five third-party
  verifications in this directory.
- `scripts/measure_overhead.py`, `scripts/probe_bench.py`, `scripts/token_probe.py`:
  the stdlib-only probes that produced every number in the overhead report
  (re-runnable, `MCP_SERVER=` accepts any server). `token_probe.py` re-counts the
  tool catalog with two real tokenizers (Qwen2.5 BPE, GPT-2 byte-level BPE) and is
  **fully offline** — `tiktoken` is deliberately not used, because fetching its BPE
  files needs network access. Point it at another vocabulary with `TOKENIZER_FILE=`.
- Correction note: the report's earlier token column was a `chars / 4` heuristic
  (≈1 100 tokens for 4 tools, ≈16 276 extrapolated to 72). Real tokenizers put the
  same payload at **798 (Qwen2.5) – 889 (GPT-2)** for 4 tools and **~14 058 – 15 678**
  at 72, i.e. the heuristic **over-estimated by ~15–25 %** on compact JSON. The
  commit message of `f569449` quotes the old figures; that commit is left as-is for
  history, and this changelog entry is the correction of record.
- Correction note: the measured subject is `nano-mcp-termux` at `main` (`00df8af`),
  not the bare `v1.1.0` tag. The tag's catalog is ~1.3 KB; `a0030c5` rewrote the four
  tool descriptions and added annotations, which is what took it to ~3.6 KB.
- Correction note: `measure_overhead.py` and `probe_bench.py` resolved the server
  under test to `./nano_mcp_termux.py` only. This repository does not vendor that
  file, so the bare commands in section 5 of the report wrote 2 bytes of output or
  died with `BrokenPipeError` instead of producing a number. Both scripts now use
  the same four-step resolver as `token_probe.py` (positional argument ->
  `$MCP_SERVER` -> `./nano_mcp_termux.py` -> `/tmp/nano-mcp-termux/...`) and exit 2
  with the path they looked for when nothing matches. Section 5 now shows the
  second `git clone` that makes the bare invocation work.
- Correction note: the JSON-RPC sizes printed by `probe_bench.py` are *compact*
  re-serialisations (`separators=(",", ":")`), not the bytes the server writes to
  stdio, and the token column in its section C is the legacy `chars/4` heuristic,
  not the real-tokenizer figures in report section 2.5. Both are now labelled in
  the script output, and the byte conventions are stated in the report.
- `scripts/check_readme.py`: offline check for the directory table shape and for
  broken relative links.
- GitHub Actions CI: protocol test on Python 3.9 to 3.13 plus the README check.
- Issue forms for new listings and corrections, a pull-request checklist,
  `CONTRIBUTING.md`, `SECURITY.md` and this changelog.

- `docs/QUANT-DECAY-MINICPM5.md`: third measured report — quantization decay of
  agent tool-triggering on-device (MiniCPM5-2B, Q4_K_M vs Q8_0 on the SKILL.md
  trigger path, 84 raw model outputs). Decay lands at the decision layer
  (trigger rate 66.7% vs 81.5%), not the format layer (parse rate 100% at both
  quants); EMPTY_THINKING is proven to be a token-budget problem, and raising
  max_tokens 384→512 buys the trigger rate back to 88.9% while saving 1.19GB
  RAM vs Q8_0 (trigger-rate dimension only — see the report's extrapolation
  boundary). Reproducible with the companion repo skillmd-termux (see the
  report's Reproduce section).
- Upstream submission of that report: [OpenBMB/MiniCPM#388](https://github.com/OpenBMB/MiniCPM/issues/388) (open) — the
  maintainer-facing thread carrying the same numbers. A duplicate posted
  seconds later was closed by its author as
  [#389](https://github.com/OpenBMB/MiniCPM/issues/389), so #388 is the
  single canonical thread.

## [0.1.0] - 2026-10-12

### Added
- `nano/nano-mcp-system.py`: single-file, zero-dependency MCP server (stdlib only)
  implementing `initialize` / `ping` / `tools/list` / `tools/call`, with a graceful
  battery-degradation ladder.
- `nano/test_client.py`: 13-check protocol loop test (`RESULT: ALL CHECKS PASSED`).
- Verified directory of Termux/Android MCP servers, with on-device verification
  reports for `nano-mcp-termux`, `hyhAsma/termux-api-tools-mcp-server`,
  `htekdev/phone-mcp-server`, `xlisp/termux-mcp-server`, `wujie272/termux-mcp`
  and `VChe-creator/memplato`.
- Runtime Survival Guide: stdout hygiene, Phantom Process Killer, install-source
  matching and graceful degradation.
