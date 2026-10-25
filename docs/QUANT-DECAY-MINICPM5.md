# MiniCPM5-2B Quantization Decay on a Real Phone: SKILL.md-on-Termux, Q4_K_M vs Q8_0

> **Does quantization break agent tool-calling on-device — and can a bigger token budget buy the accuracy back?**
> Every number below was measured end to end on the device listed: 84 raw model
> outputs, a zero-dependency POSIX-sh skill loader, pre-registered falsification
> thresholds. Part of the 648 plan · 2026-10-20.
>
> Device: Xiaomi 23013RK75C, Android 15 (SDK 35), aarch64, 7 cores, no root
> Runtime: Termux + llama.cpp 0.7.0 (llama-server, 7 threads, 4 slots × 4096 ctx)
> Model: openbmb/MiniCPM5-2B-GGUF (2.52B dense Llama arch, XML-style tool calls, thinking model)
> Upstream: the SKILL.md open standard (Anthropic, 2025-12); downstream: nano-mcp-termux (the 486 plan)

---

## Verdict

**SKILL.md-on-Termux works at Q4_K_M, and the quantization decay is attributable: it happens at the decision layer (trigger rate), not at the format layer (parse rate).**

Pre-registered falsification thresholds:

| Threshold | Falsified if | Measured | Verdict |
|---|---|---|---|
| Trigger rate | Q4_K_M < Q8_0 × 70% | 66.7% vs 81.5% → ratio **81.8%** | **not falsified** |
| Parse failure rate | > 30% | **0%** (100% parse success at both quants) | **not falsified** |

**Attribution experiment (added)**: the pre-registered hypothesis — "trigger-rate decay is mainly EMPTY_THINKING burning through the token budget; raising max_tokens compensates" — was confirmed by an independent Q4_K_M @ max_tokens=512 run: trigger rate 66.7% → **88.9% (8/9)**, EMPTY_THINKING **8 → 1**, overtaking Q8_0's 81.5% (table and conclusions below).

**Dimension qualifier**: "overtaking" refers only to the binary SKILL.md tool-trigger decision, not to language-modeling quality — external measurement (OpenTeams, 2026-09) shows Q8_0 beats Q4_K_M on KLD/perplexity, which is settled. This report's distinct finding is that **on the trigger-rate dimension, budget compensation closes the quantization gap** (see "Relation to existing quantization measurements" under Limitations).

---

## Core numbers

| Metric | Q4_K_M@384 (1.49GB) | Q4_K_M@512 (1.49GB) | Q8_0@384 (2.68GB) |
|---|---|---|---|
| Trigger rate | 18/27 = 66.7% | **8/9 = 88.9%** (attribution exp.) | 22/27 = 81.5% |
| Correct abstention (negatives) | 9/9 = 100% | 4/4 = 100% | 12/12 = 100% |
| Parse rate | 18/18 = 100% | 8/8 = 100% | 22/22 = 100% |
| Param fill rate | 18/18 = 100% | 8/8 = 100% | 20/22 = 90.9% |
| EMPTY_THINKING (positives) | 8 | **1** | 2 |
| Positive-case mean latency | 27.9s | 33.9s | 41.6s |
| Generation speed | ~6 tok/s | ~6 tok/s | 3.69 tok/s (log-measured) |
| Resident memory | 1.49GB | 1.49GB | 2.68GB |

Per-skill trigger rate (post-hoc corrected):

| Skill | Q4_K_M@384 | Q4_K_M@512 (attribution, n=3/skill) | Q8_0@384 |
|---|---|---|---|
| word-count | 6/9 = 66.7% | 2/3 = 66.7% | 6/9 = 66.7% |
| text-reverse | 5/9 = 55.6% | 3/3 = 100% | 8/9 = 88.9% |
| base64-encode | 7/9 = 77.8% | 3/3 = 100% | 8/9 = 88.9% |

---

## Failure-mode taxonomy (attribution of parse_ok=0 positives)

| Failure mode | Q4_K_M | Q8_0 | Notes |
|---|---|---|---|
| EMPTY_THINKING | **8** | **2** | entire 384-token budget burned in reasoning_content, content empty |
| NO_TOOL_CALL | 0 | 3 | plain-prose answer, no tool-call attempt |
| FORMAT_DRIFT_JSON | 1 | 0 | JSON-style call instead of XML (Q4-only) |
| EMPTY_PARAM | 0 | 2 | `<function name="word-count"></function>` — right call, empty params |
| TRUNCATED_XML / MALFORMED_XML | 0 | 0 | did not occur |

Key observations:

1. **EMPTY_THINKING scales with quantization (2 → 8, ×4) and is proven to be a token-budget problem**: quantization makes the thinking trace more verbose; once it burns through max_tokens=384, content comes back empty. **Attribution experiment**: same Q4_K_M, only max_tokens raised to 512 — EMPTY_THINKING drops 8 → 1 and trigger rate rises 66.7% → 88.9%. The decay's main cause is budget, not capability.
2. **Zero decay at the format layer**: parse rate is 100% at both quants. Whenever the model emits an XML tool call, the 158-line zero-dependency loader (skillmd.sh) catches it 100% of the time. **The loader needs no fault-tolerance hardening for quantized models.**
3. **EMPTY_PARAM appeared on the higher-precision Q8_0** (2 cases) and never on Q4_K_M: the sample is too small (2 vs 0) to infer from — recorded, not interpreted — but the direction contradicts the naive "quantization hurts quality" intuition.
4. **Double-100% abstention on negatives**: quantization did not damage boundary judgment — where tool use is inappropriate, both quants abstain reliably.

---

## Speed & memory cost

- Q8_0 positive-case mean 41.6s vs Q4_K_M 27.9s (**49% longer**); log-measured generation 3.69 tok/s vs ~6 tok/s (**38% slower**).
- Q8_0 costs +1.19GB memory (+80%). During the runs, MIUI's memory manager killed the Q8_0 llama-server once (never the Q4_K_M) — a 2.68GB resident process is a real risk on an 8GB phone.
- Negative cases are much slower than positives (Q4: 64.9s vs 27.9s; Q8: 83.7s vs 41.6s): abstaining requires thinking through the whole budget, while triggering exits early.

---

## Engineering conclusions

1. **For on-device deployment, prefer Q4_K_M**: saves 1.19GB RAM; Q8_0 generates ~38% slower (3.69 vs ~6 tok/s). The price is −14.8pp trigger rate — and the trigger-rate loss has an engineering fix (below), while the memory and speed costs do not.
2. **EMPTY_THINKING is engineerable (verified)**: Q4_K_M @ max_tokens=512 attribution run (9 positives × 1 repeat + 4 negatives): trigger rate 66.7% → **88.9%**, EMPTY_THINKING **8 → 1**, fill rate stays 100%, abstention stays 100%. Cost: positive mean 27.9s → 33.9s (+21%), negative mean 64.9s → 111.2s (deciding to abstain takes longer). **Conclusion: Q4_K_M + 512 budget overtakes Q8_0@384 on trigger rate (88.9% vs 81.5%) while saving 1.19GB RAM and with Q8_0 taking ~23% longer per positive (41.6s vs 33.9s) — the on-device optimum is "smaller quant + bigger budget", not "bigger quant + smaller budget" (trigger-rate dimension only: Q8_0 remains better than Q4_K_M on language-modeling quality; see Limitations).**
3. **Trigger-rate variance is a skill-semantics problem**: word-count sits at 66.7% on both quants — the most stable weak spot of the three. Its trigger phrasings ("Count the characters" / "How long is this passage") are the most semantically ambiguous. **The attribution experiment supports this**: even at 512, word-count stays 2/3 (the single failure, wc2, is still EMPTY_THINKING at 137s) — budget compensation helps it least; the bottleneck is semantics, not budget. Fix: write more "triggerable" skill descriptions in the catalog.
4. **Chains into the 486 plan**: this report's skill runtime (orchestration) + nano-mcp-termux (tools) = a complete on-device agent loop: SKILL.md decides *what to do*, MCP tools execute *how to do it*.

---

## Scope & limitations

- 12 cases × 3 repeats per quant; 27 positives (3 skills × 3 phrasings × 3 repeats); negatives: 9 for Q4_K_M / 12 for Q8_0 (a duplicated neg3 row in cases.tsv made Q8_0 run one extra group; all abstained correctly; does not affect conclusions).
- Attribution experiment (Q4_K_M@512): 9 positives × 1 repeat + 4 negatives, single repeat (n=9 — point estimates are noisier than the main experiment); same harness, same case set, same judging criteria as the main experiment; only max_tokens (384→512) and REPEATS (3→1) changed. The plan was positives-only, but the case-filter step silently failed and the negatives ran too — happily, this added the "does a bigger budget cause over-triggering?" check: 4/4 correct abstentions, so boundary judgment did not degrade with the larger budget.
- Sampling: temperature=1.0, top_p=0.95, **min_p=0.0** (llama.cpp's default 0.05 filters the tokens needed to escape a reasoning loop — it must be zeroed explicitly), max_tokens=384.
- In the Q8_0 main run, 2 CURL_ERR cases (curl 180s timeout — an infrastructure failure) were re-run at 300s (noted in the tally); the re-runs produced 1 EMPTY_THINKING + 1 success, already counted in the tables.
- Judging: trigger_ok was recomputed post hoc by posthoc.py (the harness had a scenario-name vs skill-name mapping bug; the TSVs store the raw func_seen ground truth, so recomputation needed no re-run).
- n=27 per quant: the 95% CI on 66.7% is roughly ±17pp; 3 repeats cannot pin single-cell point estimates. The report's value is the **failure-mode taxonomy and the attribution structure**, not precise point estimates.
- One model family only (MiniCPM5-2B); conclusions do not transfer to other models.
- **Relation to existing quantization measurements (extrapolation boundary)**: external MiniCPM5-2B quantization measurements exist, but at different endpoints — the OpenTeams report (Guido Imperiale, 2026-09-22, openteams.com/engineering-blog/minicpm5-2b-quantization-report/) measures KLD and Same-Sampled-Token, finding Q6_K indistinguishable from F16 and IQ4_XS the last usable quant before the quality cliff; a Tencent Cloud hands-on (cloud.tencent.cn/developer/article/2741314) verified Q4_K_M can make a tool call (a single get_weather demo), with no Q4/Q8 trigger-rate comparison and no budget variable. **Nobody outside has measured "quant level × max_tokens budget → agent tool-trigger rate"** — that is the dimension on which this report's three-way comparison is unique. Extrapolation boundary: the conclusions hold for the SKILL.md trigger scenario + this harness's prompt format; they do not extrapolate to "Q4 beats Q8 overall" (on KLD, Q8_0 is indeed better) nor to "all agent capabilities of MiniCPM5-2B".

## Upstream response
- 2026-10-23: the report was filed upstream as [OpenBMB/MiniCPM#388](https://github.com/OpenBMB/MiniCPM/issues/388) and **reviewed and closed as completed by the MiniCPM maintainers**, who confirmed the experiments are reproducible and the limitations clearly documented. Thank-you note from the maintainer on the issue thread.
- What this does *not* mean: it is not an endorsement of the conclusion, not a product decision, and not a claim that Q4_K_M is preferred upstream. The scope stays exactly as written under Scope & limitations above (one model family, one trigger scenario, n=27 per quant, point estimates +/-17pp).

## Reproduce

```bash
# Models (SHA256 verified against the HF tree API lfs.oid)
# Q4_K_M.gguf 1,561,318,368 B  ec2d5801…86602fd
# Q8_0.gguf   2,679,710,688 B  c5415f89…cfaba078
llama-server -m Q4_K_M.gguf --host 127.0.0.1 --port 8080 -c 4096 -t 7 &
TAG=q4km   REPEATS=3 MAXTOK=384 sh run_tests.sh   # main experiment: full 12-case set × 3
TAG=q4v512 REPEATS=1 MAXTOK=512 sh run_tests.sh   # attribution experiment: same harness, only the budget changes
python3 posthoc.py results_q4km_main.tsv outs/ q4km
python3 posthoc.py results_q4v512.tsv  outs/ q4v512
```

All artifacts ship in the companion repo [`skillmd-termux`](https://github.com/Lmeng486/skillmd-termux): results_q4km_main.tsv (37 rows), results_q8km_final.tsv (40 rows), results_q4v512.tsv (14 rows), 36+36+12 raw .out model outputs, posthoc.py, skillmd.sh, run_tests.sh, cases.tsv, skills/ (word-count, text-reverse, base64-encode).
