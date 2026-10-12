# Changelog

All notable changes to this repository are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
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
