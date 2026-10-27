#!/usr/bin/env python3
"""Generic stdio MCP handshake probe for the survival survey.

Companion to docs/MCP-SURVIVAL-SURVEY-PROTOCOL.md (pre-registered protocol).
Server-agnostic: the server command is passed after `--`. No hardcoded tool
names, no hardcoded paths. Zero dependencies (stdlib only).

Measured / reported:
  L1  protocol version negotiated (tries 2025-11-25, falls back to 2024-11-05
      only if the server rejects the first), serverInfo, tools/list tool count,
      compact serialization size of the tools payload, chars/4 heuristic
  L2  optional single tools/call (--call NAME --call-args JSON)
  L3  peak RSS of the server main process (VmHWM from /proc/<pid>/status;
      main process only -- spawned children are not attributed)

The raw tools/list result can be dumped (--save-tools FILE) for offline
token re-counting with the dual-BPE method (scripts/token_probe.py).

Usage:
    python3 survival_probe.py -- <server-command> [args...]
    python3 survival_probe.py --call TOOL --call-args '{}' -- <server-command> [args...]
    python3 survival_probe.py --save-tools tools.json --json -- <server-command>

Exit codes: 0 = L1 pass, 3 = L1 fail (handshake), 4 = probe usage/internal error.
"""
import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time

PROTOCOL_VERSIONS = ["2025-11-25", "2024-11-05"]
EOF_SENTINEL = ""


class ProbeError(Exception):
    pass


class ServerProc:
    """Spawn a stdio MCP server; thread-drained pipes so reads can time out."""

    def __init__(self, cmd, timeout_s):
        self.timeout_s = timeout_s
        try:
            self.p = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, bufsize=1)
        except OSError as e:
            raise ProbeError("cannot spawn %r: %s" % (cmd[0], e))
        self.out_q = queue.Queue()
        self.err_lines = []
        threading.Thread(target=self._drain_out, daemon=True).start()
        threading.Thread(target=self._drain_err, daemon=True).start()

    def _drain_out(self):
        try:
            for line in self.p.stdout:
                self.out_q.put(line)
        except Exception:
            pass
        self.out_q.put(EOF_SENTINEL)

    def _drain_err(self):
        try:
            for line in self.p.stderr:
                self.err_lines.append(line.rstrip("\n"))
        except Exception:
            pass

    def send(self, obj):
        try:
            self.p.stdin.write(json.dumps(obj) + "\n")
            self.p.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            raise EOFError("stdin write failed (server dead?): %s" % e)

    def read_until_id(self, want_id):
        """Read stdout until a JSON-RPC response with the wanted id arrives.
        Notifications and foreign-id messages are skipped."""
        deadline = time.time() + self.timeout_s
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError("no response with id=%s within %.0fs"
                                   % (want_id, self.timeout_s))
            line = self.out_q.get(timeout=remaining)
            if line == EOF_SENTINEL:
                raise EOFError("server closed stdout (rc=%s)" % self.p.poll())
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue  # non-JSON noise on stdout: skip, keep waiting
            if isinstance(msg, dict) and msg.get("id") == want_id:
                return msg
            # notification or response to a different id -> skip

    def peak_rss_kb(self):
        try:
            with open("/proc/%d/status" % self.p.pid) as f:
                for ln in f:
                    if ln.startswith("VmHWM:"):
                        return int(ln.split()[1])
        except OSError:
            pass
        return None

    def stop(self):
        if self.p.poll() is not None:
            return
        try:
            self.p.terminate()
            self.p.wait(timeout=5)
        except Exception:
            try:
                self.p.kill()
            except Exception:
                pass


def initialize_attempt(cmd, version, timeout_s):
    """One initialize attempt against a fresh server process.

    Returns (serverproc, result_dict, error_dict_or_None)."""
    sp = ServerProc(cmd, timeout_s)
    sp.send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": version, "capabilities": {},
                        "clientInfo": {"name": "survival-probe", "version": "1.0"}}})
    resp = sp.read_until_id(1)
    if "error" in resp:
        return sp, None, resp["error"]
    return sp, resp.get("result", {}), None


def run_probe(cmd, call_name, call_args, save_tools, timeout_s):
    rep = {"cmd": cmd, "handshake": "FAIL", "protocol_version": None,
           "server_info": None, "tools_count": None, "next_cursor": None,
           "tools_list_bytes": None, "chars4_tokens": None,
           "peak_rss_kb": None, "call": None, "stderr_tail": [],
           "notes": []}

    sp, result, err = None, None, None
    for ver in PROTOCOL_VERSIONS:
        try:
            sp, result, err = initialize_attempt(cmd, ver, timeout_s)
        except (EOFError, TimeoutError) as e:
            rep["notes"].append("initialize@%s: %s" % (ver, e))
            if sp is not None:
                sp.stop()
            sp = None
            continue
        if err is None:
            rep["protocol_version"] = result.get("protocolVersion", ver)
            rep["server_info"] = result.get("serverInfo")
            break
        rep["notes"].append("initialize@%s rejected: %s" % (ver, err))
        sp.stop()
        sp = None

    if sp is None:
        rep["stderr_tail"] = (rep.get("stderr_tail") or [])[-5:]
        return rep  # handshake failed at every protocol version

    try:
        sp.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        sp.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        resp = sp.read_until_id(2)
        if "error" in resp:
            rep["notes"].append("tools/list error: %s" % resp["error"])
        else:
            res = resp.get("result", {})
            tools = res.get("tools", [])
            compact = json.dumps(res, separators=(",", ":"))
            rep["handshake"] = "PASS"
            rep["tools_count"] = len(tools)
            rep["next_cursor"] = bool(res.get("nextCursor"))
            rep["tools_list_bytes"] = len(compact.encode("utf-8"))
            rep["chars4_tokens"] = rep["tools_list_bytes"] // 4
            if save_tools:
                with open(save_tools, "w") as f:
                    f.write(compact)

            if call_name:
                sp.send({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                         "params": {"name": call_name, "arguments": call_args}})
                try:
                    cresp = sp.read_until_id(3)
                except (EOFError, TimeoutError) as e:
                    rep["call"] = {"tool": call_name, "ok": False, "error": str(e)}
                else:
                    if "error" in cresp:
                        rep["call"] = {"tool": call_name, "ok": False,
                                       "error": cresp["error"]}
                    else:
                        cres = cresp.get("result", {})
                        texts = [c.get("text", "")
                                 for c in cres.get("content", [])
                                 if isinstance(c, dict) and c.get("type") == "text"]
                        out = "\n".join(t for t in texts if t)
                        rep["call"] = {"tool": call_name,
                                       "ok": not cres.get("isError", False),
                                       "is_error": bool(cres.get("isError", False)),
                                       "structured": "structuredContent" in cres,
                                       "text_head": out[:400],
                                       "text_len": len(out)}
            # sample peak RSS after the workload, before teardown
            rep["peak_rss_kb"] = sp.peak_rss_kb()
    except (EOFError, TimeoutError) as e:
        rep["notes"].append("post-initialize: %s" % e)
    finally:
        rep["stderr_tail"] = sp.err_lines[-5:]
        sp.stop()
    return rep


def main():
    ap = argparse.ArgumentParser(description="generic stdio MCP handshake probe")
    ap.add_argument("--call", metavar="TOOL", default=None)
    ap.add_argument("--call-args", metavar="JSON", default="{}")
    ap.add_argument("--save-tools", metavar="FILE", default=None)
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("cmd", nargs=argparse.REMAINDER,
                    help="server command after --")
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    if not cmd:
        ap.error("server command required after --")
    try:
        call_args = json.loads(a.call_args) if a.call else {}
    except json.JSONDecodeError as e:
        ap.error("--call-args is not valid JSON: %s" % e)

    try:
        rep = run_probe(cmd, a.call, call_args, a.save_tools, a.timeout)
    except ProbeError as e:
        print("probe error: %s" % e, file=sys.stderr)
        sys.exit(4)

    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print("== survival probe ==")
        print("cmd: %s" % " ".join(rep["cmd"]))
        print("L1 handshake: %s" % rep["handshake"], end="")
        if rep["handshake"] == "PASS":
            si = rep["server_info"] or {}
            print(" (protocol %s, server %s %s)" % (
                rep["protocol_version"], si.get("name", "?"), si.get("version", "?")))
        else:
            print()
        if rep["tools_count"] is not None:
            print("tools: %d (first page%s)" % (
                rep["tools_count"],
                ", nextCursor present" if rep["next_cursor"] else ""))
            print("tools/list compact: %d bytes (chars/4 ≈ %d tokens)"
                  % (rep["tools_list_bytes"], rep["chars4_tokens"]))
        if rep["peak_rss_kb"] is not None:
            print("peak RSS (VmHWM, main proc): %d KB" % rep["peak_rss_kb"])
        if rep["call"] is not None:
            c = rep["call"]
            print("L2 call %r: %s" % (c["tool"], "PASS" if c.get("ok") else "FAIL"))
            if c.get("error"):
                print("  error: %s" % json.dumps(c["error"], ensure_ascii=False)[:400])
            if c.get("text_head"):
                print("  output (%d chars): %s" % (c["text_len"],
                                                   c["text_head"][:200].replace("\n", " ⏎ ")))
        for n in rep["notes"]:
            print("note: %s" % n)
        if rep["stderr_tail"]:
            print("server stderr (last lines):")
            for ln in rep["stderr_tail"]:
                print("  | %s" % ln[:200])

    sys.exit(0 if rep["handshake"] == "PASS" else 3)


if __name__ == "__main__":
    main()
