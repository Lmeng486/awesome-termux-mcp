#!/usr/bin/env python3
"""Dual-BPE re-count of saved tools/list payloads (survival survey).
Input: JSON files shaped {"tools":[...]}. Offline only.
Vocab: /root/tokcheck/{qwen25-tokenizer.json, gpt2-vocab.json, gpt2-merges.txt}
"""
import json, os, sys, hashlib
from tokenizers import Tokenizer, models, pre_tokenizers, decoders

HERE = os.path.dirname(os.path.abspath(__file__))
q = Tokenizer.from_file("/root/tokcheck/qwen25-tokenizer.json")
bpe = models.BPE.from_file("/root/tokcheck/gpt2-vocab.json", "/root/tokcheck/gpt2-merges.txt")
g = Tokenizer(bpe)
g.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
g.decoder = decoders.ByteLevel()

def counts(text):
    return {
        "qwen25": len(q.encode(text).ids),
        "gpt2": len(g.encode(text).ids),
        "chars4": max(1, round(len(text) / 4)),
    }

targets = sys.argv[1:] or [
    os.path.join(HERE, "ctx7_tools.json"),
    os.path.join(HERE, "fc_tools.json"),
    os.path.join(HERE, "pw_tools.json"),
    os.path.join(HERE, "mm_tools.json"),
]

summary = {}
for path in targets:
    name = os.path.basename(path).replace("_tools.json", "")
    raw = open(path, "rb").read()
    text = raw.decode("utf-8")
    d = json.loads(text)
    tools = d.get("tools", [])
    # re-serialize exactly like survival_probe did (compact, ensure_ascii=False)
    compact = json.dumps(d, separators=(",", ":"), ensure_ascii=False)
    result_only = json.dumps(d.get("tools", []), separators=(",", ":"), ensure_ascii=False)
    per = {}
    total_q = total_g = 0
    for t in tools:
        blob = json.dumps(t, separators=(",", ":"), ensure_ascii=False)
        c = counts(blob)
        per[t.get("name", "?")] = {"bytes": len(blob.encode("utf-8")), **c}
        total_q += c["qwen25"]; total_g += c["gpt2"]
    summary[name] = {
        "file_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest()[:16],
        "compact_bytes": len(compact.encode("utf-8")),
        "result_only_bytes": len(result_only.encode("utf-8")),
        "tools": len(tools),
        "whole": counts(compact),
        "result_only": counts(result_only),
        "sum_per_tool": {"qwen25": total_q, "gpt2": total_g},
        "mean_per_tool": {
            "qwen25": round(total_q / max(1, len(tools)), 1),
            "gpt2": round(total_g / max(1, len(tools)), 1),
        },
        "heaviest": sorted(per.items(), key=lambda kv: -kv[1]["gpt2"])[:3],
    }

print(json.dumps(summary, ensure_ascii=False, indent=1))
with open(os.path.join(HERE, "recount_summary.json"), "w") as fh:
    json.dump(summary, fh, ensure_ascii=False, indent=1)
