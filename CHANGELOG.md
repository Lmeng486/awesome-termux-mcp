# Changelog

All notable changes to this repository are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]
### Added
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
- `scripts/check_readme.py`: offline check for the directory table shape and for
  broken relative links.
- GitHub Actions CI: protocol test on Python 3.9 to 3.13 plus the README check.
- Issue forms for new listings and corrections, a pull-request checklist,
  `CONTRIBUTING.md`, `SECURITY.md` and this changelog.

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
