# Contributing

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
