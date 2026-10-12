import os

# Repo root = parent of the directory containing this script (i.e. scripts/..),
# so the generator works from any clone location instead of a hard-coded path.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CI = """name: CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]
  workflow_dispatch:

permissions:
  contents: read

jobs:
  nano-protocol:
    name: nano protocol test (py${{ matrix.python-version }})
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.9", "3.10", "3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Byte-compile the server
        run: python -m py_compile nano/nano-mcp-system.py
      - name: Protocol loop test
        run: python3 nano/test_client.py

  readme:
    name: README consistency
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Directory table and relative links
        run: python3 scripts/check_readme.py
"""

NEW_LISTING = """name: New listing
description: Propose a verified Termux/Android MCP server for the directory
title: "[listing] <owner/repo>"
labels: ["listing"]
body:
  - type: markdown
    attributes:
      value: |
        A listing without on-device proof is rejected. Fill in every field.
        Badges start at the unverified tier and are only upgraded to a checkmark
        after an end-to-end run on real hardware.
  - type: input
    id: repo
    attributes:
      label: Repository URL
      placeholder: https://github.com/owner/repo
    validations:
      required: true
  - type: input
    id: tools
    attributes:
      label: Number of tools it actually exposes
      placeholder: "19"
    validations:
      required: true
  - type: input
    id: device
    attributes:
      label: Device model
      placeholder: Xiaomi 23013RK75C
    validations:
      required: true
  - type: input
    id: android
    attributes:
      label: Android / Termux version
      placeholder: Android 15 (SDK 35) / Termux 0.118.3
    validations:
      required: true
  - type: input
    id: client
    attributes:
      label: MCP client used
      placeholder: Claude Desktop / Cursor / Operit
    validations:
      required: true
  - type: textarea
    id: repro
    attributes:
      label: Reproduction steps
      description: Exact commands from a clean shell to a successful tools/list.
      render: shell
    validations:
      required: true
  - type: textarea
    id: evidence
    attributes:
      label: Evidence
      description: Paste real output from at least one read-only tools/call.
      render: json
    validations:
      required: true
  - type: checkboxes
    id: rules
    attributes:
      label: Ground rules
      options:
        - label: It runs without disabling any security mechanism.
          required: true
        - label: It asks for no permissions beyond its stated features.
          required: true
        - label: Any process-spawning tool passes arguments as arrays or via shlex.quote().
          required: true
"""

BUG_REPORT = """name: Report an issue
description: Something in the directory or a verification report is wrong
title: "[issue] "
body:
  - type: dropdown
    id: kind
    attributes:
      label: What is wrong?
      options:
        - A listing is inaccurate (tool count, badge or link)
        - A verification report is wrong
        - Bug in nano/nano-mcp-system.py
        - Broken link or formatting
        - Other
    validations:
      required: true
  - type: textarea
    id: what
    attributes:
      label: What happened
    validations:
      required: true
  - type: textarea
    id: expected
    attributes:
      label: What you expected instead
    validations:
      required: true
  - type: input
    id: env
    attributes:
      label: Environment
      placeholder: Xiaomi 23013RK75C / Android 15 / Termux 0.118.3 / Python 3.14.6
  - type: textarea
    id: logs
    attributes:
      label: Logs or command output
      render: shell
"""

CONFIG = """blank_issues_enabled: false
contact_links:
  - name: Security report
    url: https://github.com/Lmeng486/awesome-termux-mcp/security/advisories/new
    about: Report vulnerabilities privately, never in a public issue.
  - name: Runtime Survival Guide
    url: https://github.com/Lmeng486/awesome-termux-mcp#runtime-survival-guide-read-before-you-connect-anything
    about: Read this before reporting "the server dies on my phone".
  - name: Sibling project
    url: https://github.com/Lmeng486/nano-mcp-termux
    about: The 4-tool, 1.1.0 nano server with process-group lifecycle hardening.
"""

PR_TEMPLATE = """## What does this PR change?

<!-- One or two lines. Link the issue it closes, if any. -->

## Type

- [ ] New listing
- [ ] Correction to an existing listing or report
- [ ] Fix in `nano/`
- [ ] Docs / tooling

## Checklist

- [ ] `python3 nano/test_client.py` prints `RESULT: ALL CHECKS PASSED`
- [ ] `python3 scripts/check_readme.py` prints `README check OK`
- [ ] Any new listing includes device model, Android/Termux version, client and repro steps
- [ ] Any new listing ships real tool output (read-only calls only)
- [ ] Any process-spawning tool passes `arguments` as arrays or via `shlex.quote()`
- [ ] Nothing has to be disabled for this to run
- [ ] `nano/` is still stdlib-only, zero third-party dependencies

## Device used for verification

- Model:
- Android / Termux:
- Python:
- MCP client:
"""

CONTRIBUTING = """# Contributing

Thanks for helping make Termux/Android MCP servers easier to trust.

## The two rules that matter

1. **Proof, or it does not ship.** A listing or a verification report must come from
   a real device run. State which device, which Android/Termux version, which client,
   and the exact commands you ran.
2. **Zero dependencies in `nano/`.** `nano/nano-mcp-system.py` is a single, stdlib-only
   file. A PR that adds a third-party import to it will be rejected.

## Adding a server to the directory

Open a **New listing** issue (or a PR) with:

- the repository URL and the number of tools it actually exposes,
- device model + Android version + Termux version + Python version,
- the MCP client you connected with,
- reproduction steps from a clean shell to a successful `tools/list`,
- real output from at least one read-only `tools/call`.

Badges start unverified and are only upgraded to a checkmark after an end-to-end
on-device run.

## Security-relevant requirements

- Client `arguments` MUST be passed as argument arrays or escaped with
  `shlex.quote()`. Never interpolate them into a command string.
- Listings must not require disabling a security mechanism, and must not ask for
  permissions beyond what their stated features need.

## Development

```bash
# protocol loop test for the bundled nano server
python3 nano/test_client.py        # -> RESULT: ALL CHECKS PASSED

# README directory table + relative-link check
python3 scripts/check_readme.py    # -> README check OK
```

Both commands are exactly what CI runs. Run them before opening a PR.

## Reporting problems

- Bugs and inaccuracies: open a **Report an issue** issue.
- Vulnerabilities: use GitHub Security Advisories (see `SECURITY.md`), not a public issue.
"""

SECURITY = """# Security Policy

## Supported versions

| Component | Version | Supported |
|---|---|---|
| `nano/nano-mcp-system.py` | 0.1.x | yes |
| Directory listings and reports | current `main` | yes |

## Reporting a vulnerability

Report privately through **GitHub Security Advisories** (the `Security` tab, then
*Report a vulnerability*). Do not open a public issue for a vulnerability. Include
the device / Android / Termux versions and a minimal reproduction.

We aim to acknowledge within 72 hours.

## Threat model

This repository is a **directory plus one tiny reference server**, and that shapes
what a vulnerability can even be:

- **`nano/nano-mcp-system.py`** runs as the Termux sandbox user, with no root and no
  ADB. It opens no TCP port: stdio is the entire trust boundary. Its single tool
  (`device_status`) reads battery / storage / arch / memory and never forwards client
  input to a shell.
- **Directory listings** are metadata. A malicious listing cannot execute anything
  here; it can only mislead. That is why every entry needs on-device proof and a
  reviewable reproduction.
- **Verification reports** in the README describe third-party servers. They are
  observations, not endorsements. Audit any server before running it.

## What this project will not do

- Disabling Phantom Process Killer, `settings` or `device_config` is a manual,
  user-initiated action. Nothing in this repository performs it.
- We will not accept a listing that only works after turning off a security feature.
"""

CHANGELOG = """# Changelog

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
"""

FILES = {
    ".github/workflows/ci.yml": CI,
    ".github/ISSUE_TEMPLATE/new_listing.yml": NEW_LISTING,
    ".github/ISSUE_TEMPLATE/bug_report.yml": BUG_REPORT,
    ".github/ISSUE_TEMPLATE/config.yml": CONFIG,
    ".github/PULL_REQUEST_TEMPLATE.md": PR_TEMPLATE,
    "CONTRIBUTING.md": CONTRIBUTING,
    "SECURITY.md": SECURITY,
    "CHANGELOG.md": CHANGELOG,
}

for rel, content in FILES.items():
    p = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    print("wrote", rel, len(content), "bytes")
