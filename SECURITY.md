# Security Policy

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
