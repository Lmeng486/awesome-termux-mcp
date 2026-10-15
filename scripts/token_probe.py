#!/usr/bin/env python3
"""Real-tokenizer re-count of the tools/list payload measured in
docs/MCP-ON-MOBILE-OVERHEAD.md.

Offline by design: no network access is attempted, ever. Token counts come from
two independent vocabularies so the result is reported as a *range* rather than
a single number:

  * Qwen2.5 BPE  -- large vocab, packs JSON punctuation tightly -> lower bound
  * GPT-2 BPE    -- classic byte-level baseline                 -> upper bound

The legacy `chars / 4` heuristic is printed alongside for continuity with
earlier revisions of the report. It is *not* the reported figure.

Vocabulary files are looked up in this order: the environment variable, the
script's own directory, `/root/tokcheck`, then the current directory.

Usage:
    python3 token_probe.py                      # defaults to /tmp/nano-mcp-termux
    python3 token_probe.py /path/to/server.py
    MCP_SERVER=/path/to/server.py python3 token_probe.py
    TOKENIZER_FILE=/path/to/tokenizer.json python3 token_probe.py
    python3 token_probe.py --json
"""
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SEARCH_DIRS = [HERE, "/root/tokcheck", os.getcwd()]

DEFAULT_SERVER = "/tmp/nano-mcp-termux/nano_mcp_termux.py"


def resolve_server():
    for arg in sys.argv[1:]:
        if not arg.startswith("-"):
            return arg
    return os.environ.get("MCP_SERVER") or DEFAULT_SERVER


def find_asset(env_var, *candidates):
    """First existing path wins: env var, then the search dirs."""
    if os.environ.get(env_var):
        return os.environ[env_var]
    for d in SEARCH_DIRS:
        for name in candidates:
            p = os.path.join(d, name)
            if os.path.exists(p):
                return p
    return None


def main():
    as_json = "--json" in sys.argv
    server = resolve_server()

    init_req = {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "token-probe", "version": "1.0"}},
    }
    list_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

    payload = "".join(json.dumps(m) + "\n" for m in (init_req, list_req))
    try:
        proc = subprocess.run([sys.executable, server], input=payload.encode(),
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              timeout=60)
    except FileNotFoundError:
        sys.exit("server not found: %s" % server)
    except subprocess.TimeoutExpired:
        sys.exit("server timed out after 60s: %s" % server)
    raw = proc.stdout.decode("utf-8", "replace")

    lines = {}
    for ln in raw.splitlines():
        s = ln.strip()
        if not s:
            continue
        try:
            o = json.loads(s)
        except Exception:
            continue
        lines[o.get("id")] = (s, o)

    if 2 not in lines:
        sys.exit("no tools/list response from %s" % server)

    with open(server, "rb") as fh:
        src = fh.read()
    server_sha = hashlib.sha256(src).hexdigest()

    line2, obj2 = lines[2]
    tools = (obj2.get("result") or {}).get("tools") or []
    n_measured = len(tools)

    # ---- byte / char geometry: three distinct conventions ---------------
    whole_compact_f = json.dumps(obj2, separators=(",", ":"), ensure_ascii=False)
    whole_compact_t = json.dumps(obj2, separators=(",", ":"), ensure_ascii=True)
    result_only_f = json.dumps(obj2["result"], separators=(",", ":"), ensure_ascii=False)
    result_only_t = json.dumps(obj2["result"], separators=(",", ":"), ensure_ascii=True)
    pretty = json.dumps(obj2, ensure_ascii=False, indent=2)

    # ---- offline tokenizers --------------------------------------------
    encoders = {}
    tokenizer_notes = []

    qwen_path = find_asset("TOKENIZER_FILE", "qwen25-tokenizer.json", "tokenizer.json")
    try:
        from tokenizers import Tokenizer
        if qwen_path:
            q = Tokenizer.from_file(qwen_path)
            encoders["qwen2.5"] = (lambda t, q=q: len(q.encode(t).ids))
            tokenizer_notes.append("qwen2.5 OK (vocab %d, %s)"
                                   % (q.get_vocab_size(), qwen_path))
        else:
            tokenizer_notes.append("qwen2.5 SKIPPED: no tokenizer.json found "
                                   "(set TOKENIZER_FILE)")
    except Exception as e:
        tokenizer_notes.append("qwen2.5 FAIL: %s: %s" % (type(e).__name__, e))

    vocab = find_asset("GPT2_VOCAB", "gpt2-vocab.json")
    merges = find_asset("GPT2_MERGES", "gpt2-merges.txt")
    try:
        from tokenizers import Tokenizer, models, pre_tokenizers, decoders
        if vocab and merges:
            bpe = models.BPE.from_file(vocab, merges)
            g = Tokenizer(bpe)
            g.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
            g.decoder = decoders.ByteLevel()
            encoders["gpt2"] = (lambda t, g=g: len(g.encode(t).ids))
            tokenizer_notes.append("gpt2 byte-level BPE OK (vocab %d)"
                                   % g.get_vocab_size())
        else:
            tokenizer_notes.append("gpt2 SKIPPED: need gpt2-vocab.json + "
                                   "gpt2-merges.txt (set GPT2_VOCAB/GPT2_MERGES)")
    except Exception as e:
        tokenizer_notes.append("gpt2 FAIL: %s: %s" % (type(e).__name__, e))

    tokenizer_notes.append(
        "tiktoken: skipped by design (requires network to fetch BPE files)")

    if not encoders:
        sys.exit("no tokenizer could be loaded offline; nothing to count")

    def counts(text):
        r = {nm: fn(text) for nm, fn in encoders.items()}
        r["chars/4-legacy"] = max(1, round(len(text) / 4))
        return r

    # ---- per-tool ------------------------------------------------------
    per_tool = {}
    for t in tools:
        blob = json.dumps(t, separators=(",", ":"), ensure_ascii=False)
        per_tool[t.get("name")] = dict(counts(blob),
                                       bytes=len(blob.encode("utf-8")))

    # ---- schema scaling -------------------------------------------------
    scaling = {}
    for key in list(encoders) + ["chars/4-legacy"]:
        total = sum(per_tool[t.get("name")][key] for t in tools)
        mean = total / max(1, n_measured)
        scaling[key] = {
            "mean_per_tool": round(mean, 2),
            "extrapolated": {n: int(round(mean * n))
                             for n in (4, 19, 29, 38, 52, 72)},
        }

    summary = {
        "server": server,
        "server_bytes": len(src),
        "server_sha256": server_sha,
        "tool_count": n_measured,
        "init_resp_bytes": len(lines[1][0].encode("utf-8")) if 1 in lines else None,
        "byte_conventions": {
            "wire_line_bytes": len(line2.encode("utf-8")),
            "whole_compact_bytes_ensure_ascii_false": len(whole_compact_f.encode("utf-8")),
            "whole_compact_chars_ensure_ascii_true": len(whole_compact_t),
            "result_only_compact_bytes": len(result_only_f.encode("utf-8")),
            "result_only_compact_chars": len(result_only_t),
            "pretty_chars": len(pretty),
            "pretty_bytes": len(pretty.encode("utf-8")),
        },
        "total_compact": counts(whole_compact_f),
        "total_pretty": counts(pretty),
        "total_result_only": counts(result_only_f),
        "per_tool": per_tool,
        "schema_scaling": scaling,
        "tokenizers": tokenizer_notes,
    }

    if as_json:
        print(json.dumps(summary, indent=2))
        return

    print("server            =", server)
    print("server bytes      =", len(src))
    print("server sha256     =", server_sha)
    print("init resp found   =", 1 in lines)
    print("list resp found   =", 2 in lines)
    print("tool count        =", n_measured)
    if 1 in lines:
        print("init resp bytes   =", len(lines[1][0].encode("utf-8")))

    print("\n--- byte / char geometry (three conventions, do not conflate) ---")
    print("wire line bytes            =", len(line2.encode("utf-8")))
    print("whole compact bytes (F)    =", len(whole_compact_f.encode("utf-8")))
    print("whole compact chars (T)    =", len(whole_compact_t))
    print("result-only compact bytes  =", len(result_only_f.encode("utf-8")))
    print("result-only compact chars  =", len(result_only_t))
    print("pretty chars               =", len(pretty))
    print("pretty bytes               =", len(pretty.encode("utf-8")))

    print("\n--- tokenizers ---")
    for note in tokenizer_notes:
        print(note)

    print("\n--- TOTAL tools/list payload (real tokenizers) ---")
    print("compact(F):", json.dumps(counts(whole_compact_f)))
    print("pretty    :", json.dumps(counts(pretty)))
    print("resultonly:", json.dumps(counts(result_only_f)))

    print("\n--- PER TOOL (compact, ensure_ascii=False) ---")
    for t in tools:
        name = t.get("name")
        print("%-16s bytes=%5d %s"
              % (name, per_tool[name]["bytes"],
                 json.dumps({k: v for k, v in per_tool[name].items()
                             if k != "bytes"})))

    print("\n--- SCHEMA SCALING (extrapolated from measured per-tool mean) ---")
    for key in list(encoders) + ["chars/4-legacy"]:
        row = scaling[key]
        cells = "  ".join("%d->%d%s" % (n, v, "*" if n == n_measured else "")
                          for n, v in row["extrapolated"].items())
        print("%-14s mean/tool=%7.2f  %s" % (key, row["mean_per_tool"], cells))
    print("(* = measured tool count; everything else is extrapolated)")


if __name__ == "__main__":
    main()
