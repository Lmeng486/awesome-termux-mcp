#!/usr/bin/env python3
"""Schema-keyword density analysis for the 5 survival payloads.
Goal: explain why chars/4 UNDER-estimates gh by ~2x while OVER-estimating
the other four by 11-15%. Hypothesis: gh schemas are draft-07-heavy
($schema/enum/required/additionalProperties) -> many short tokens per char.
"""
import json, os

D = os.path.dirname(os.path.abspath(__file__))
FILES = {
    "ctx7": "ctx7_tools.json",
    "fc":   "fc_tools.json",
    "pw":   "pw_tools.json",
    "mm":   "mm_tools.json",
    "gh":   "gh_tools.json",
}
KW = ["$schema", "enum", "required", "additionalProperties", "oneOf", "anyOf",
      "properties", "description", "type", "default", "items", "format",
      "minimum", "maximum", "pattern", "title"]


def desc_len(x):
    """total chars of all 'description' string values (recursive)"""
    s = 0
    stack = [x]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                if k == "description" and isinstance(v, str):
                    s += len(v)
                else:
                    stack.append(v)
        elif isinstance(cur, list):
            stack.extend(cur)
    return s


out = {}
for key, fn in sorted(FILES.items()):
    with open(os.path.join(D, fn)) as f:
        tools = json.load(f)["tools"]
    blobs = [json.dumps(t, separators=(",", ":"), ensure_ascii=False) for t in tools]
    total_chars = sum(len(b) for b in blobs)
    cnt = {k: 0 for k in KW}
    dc = 0
    for t, b in zip(tools, blobs):
        for k in KW:
            cnt[k] += b.count('"' + k + '"')
        dc += desc_len(t)
    kw_chars = sum(cnt[k] * (len(k) + 2) for k in KW)  # +2 for the quotes
    row = {
        "tools": len(tools),
        "chars": total_chars,
        "desc_chars": dc,
        "desc_pct": round(100.0 * dc / max(1, total_chars), 1),
        "kw_count": sum(cnt.values()),
        "kw_chars_pct": round(100.0 * kw_chars / max(1, total_chars), 1),
        "per_kb": {k: round(cnt[k] * 1024.0 / max(1, total_chars), 1)
                   for k in ("$schema", "enum", "required",
                             "additionalProperties", "properties", "type")},
    }
    out[key] = row
    print("%-5s tools=%-3d chars=%-7d desc%%=%5.1f kw_chars%%=%5.1f  per-KB: %s"
          % (key, row["tools"], row["chars"], row["desc_pct"], row["kw_chars_pct"],
             " ".join("%s=%.1f" % (k.replace("$", "\\$"), v)
                      for k, v in row["per_kb"].items())))

with open(os.path.join(D, "density_summary.json"), "w") as f:
    json.dump(out, f, indent=1, ensure_ascii=False)
print("\nsaved -> density_summary.json")

# gh top-10 heaviest tools, cross-ref recount_summary.json
try:
    with open(os.path.join(D, "recount_summary.json")) as f:
        rs = json.load(f)
    heaviest = rs["gh"]["heaviest"][:10]
    print("\n--- gh top heaviest (name, bytes, qwen25, gpt2, chars4) ---")
    for name, m in heaviest:
        print("%-30s bytes=%6d q25=%6d gpt2=%6d c4=%6d  tok/KB=%.0f"
              % (name, m["bytes"], m["qwen25"], m["gpt2"], m["chars4"],
                 m["qwen25"] * 1024.0 / max(1, m["bytes"])))
except Exception as e:
    print("recount cross-ref skipped:", e)
