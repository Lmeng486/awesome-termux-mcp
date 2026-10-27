# MCP Survival Survey on Android/Termux — Measured Results

**Verdict:** we froze the judging criteria *before* running anything (see `MCP-SURVIVAL-SURVEY-PROTOCOL.md`, commit `e72cf6e`), then ran 5 popular MCP servers through four escalating levels (L0 install → L1 list tools → L2 call a tool → L3 real task) on one phone. **3 predictions held, 1 missed in the interesting direction, 1 is pending a user-side pairing step.** 2/5 run as-shipped, 3/5 need patches or a different runtime, 0/5 are architecturally impossible. All token numbers below are real offline BPE counts (Qwen2.5 + GPT-2), not `chars/4` estimates.

Measured: 2026-10-26 → 2026-10-27 · Xiaomi 23013RK75C · Android 15 (SDK 35) · aarch64 · no root · Termux (node v26.4.0, Python 3.14.6, npm 11.20.0) + proot Ubuntu 24.04 (Python 3.12.3) · interactive sessions only, nothing left running in background.

## 1. TL;DR

| Server | Version | Tools | L0 install | L1 list tools | L2 call tool | Verdict | §5 predicted |
|---|---|---|---|---|---|---|---|
| context7 | latest (npx) | 2 | ✅ | ✅ | ✅ | ✅ runs as-shipped | ✅ |
| firecrawl-mcp | latest (npx) | 26 | ✅ | ✅ | ✅* keyless: 2/26 tools | ✅ runs as-shipped* | ✅ |
| playwright-mcp | latest (npx) | 25 | ✅ | ❌ crash at import | ✅ with `PLAYWRIGHT_BROWSERS_PATH` | ⚠️ one env var from working | ❌ |
| github-mcp-server | v2.x (Go binary) | 46 | ❌ native / ✅ proot | ✅ (proot) | ✅ (proot) | ⚠️ needs proot | ⚠️ |
| mobile-mcp | latest (npm) | 9 | ⚠️ 2 patches | ✅ | ⏳ pending user pairing | ⚠️ pending L2 | ⚠️ |
| *nano-mcp-termux* (control) | 1.1.1 | 4 | ✅ | ✅ | ✅ | ✅ control | — |

**Survival rate: 2/5 run as-shipped (context7, firecrawl), 3/5 need patches or a different runtime, 0/5 are architecturally impossible.** The control server (our own zero-dependency `nano-mcp-termux`) runs natively with 4 tools in ~16 MB RSS, confirming that the failure classes below are avoidable *by construction*, not inherent to Android.

## 2. Prediction scorecard (frozen before testing)

The protocol froze five predictions before any server was launched. Results:

| # | Server | Stars at freeze | Prediction | Measured outcome | Score |
|---|---|---|---|---|---|
| 1 | context7 | 63,719 | runs natively | ✅ L0–L3 all pass | **HIT** |
| 2 | firecrawl-mcp | 7,691 | runs natively | ✅ runs, but keyless mode covers only 2/26 tools | **HIT** (with coverage caveat) |
| 3 | playwright-mcp | 38,656 | fails natively | ❌ at L1 *without* env var / ✅ at L2 *with* `PLAYWRIGHT_BROWSERS_PATH` | **MISS at L1, HIT at L2** |
| 4 | github-mcp-server | 33,977 | needs non-native runtime | ❌ native (ELF type rejected) / ✅ full pass under proot | **HIT** (sharper split than predicted) |
| 5 | mobile-mcp | 10,011 | needs patches | L0 ✅ after 2 patches, L1 ✅, L2 pending user pairing | **HIT so far** (provisional) |

**Total: 3 HIT, 1 partial MISS (in the direction of *more* survivable than predicted), 1 pending.** No result was adjusted to fit the table. Where reality disagreed with the frozen table, the table lost — and that disagreement is itself a result (see §5.2).

## 3. Survival cards

Failure classes refer to `EDGE-MCP-FAILURE-TAXONOMY.md` (F1–F9).

### Card 1 — context7 (2 tools) ✅

`npx @upstash/context7-mcp` runs as-shipped. L0 ✅, L1 ✅ (2 tools), L2 ✅ (`resolve-library-id` returned real library IDs). No patches, no env vars. The lightest schema of the batch (5,237 B payload).

### Card 2 — firecrawl-mcp (26 tools) ✅*

`npx firecrawl-mcp` runs as-shipped, L0–L2 all pass. The asterisk: without `FIRECRAWL_API_KEY` only 2/26 tools are actually usable (`scrape`-class calls return auth errors); the other 24 tools list fine but fail at call time. This is a business-model constraint, not an Android one — the server itself is fully portable. Heaviest schema of the batch after github (85,522 B).

### Card 3 — playwright-mcp (25 tools) ⚠️

**Death cause, captured verbatim:**

```
Error: Unsupported platform: android
    at computeDefaultCacheDirectory (playwright-core/lib/coreBundle.js:33904)
    at defaultCacheDirectory (:33907)
    at defaultRegistryDirectory (:33910)
    at launchApp.ts / recorderApp.ts __init__
```

The crash happens during **module evaluation** — the eager class-field initializer IIFE for `registryDirectory` (coreBundle.js:34353) runs at load time, and with no env var it calls `defaultRegistryDirectory()` → `computeDefaultCacheDirectory()`, whose platform switch has no `android` branch and throws. The server never sees a single JSON-RPC line. This is a **residual path**: upstream PR #41942 (commit `3e14efd6`, fixing #41852) already made `defaultCacheDirectory()` lazy (`??=`), but the `registryDirectory` initializer remains eager — that fix covers one of the two call paths only. No code patch needed: `PLAYWRIGHT_BROWSERS_PATH=0` and `PLAYWRIGHT_BROWSERS_PATH=$HOME/pw-browsers` both bypass the default-cache computation entirely and produce **byte-identical** transcripts (sha256 `cd2d27c5…`) listing all 25 tools. Classified **F7 + F9** (platform assumption + no graceful degradation). One env var away from working; L2+ depends on having browser binaries under Termux, which we did not pursue further in this round. Evidence: `measurements/survival-survey/bare-crash.log` (sha256 `3a2b6a31…`), `env0-tools-list.log` / `homepw-tools-list.log`, and `shipped-coreBundle-excerpt.txt` (verbatim source excerpts anchored to coreBundle.js sha256 `cd6730be…`).

### Card 4 — github-mcp-server (46 tools) ⚠️

**Native death cause, forensically confirmed on device:**

```
$ ./github-mcp-server --version
error: ".../github-mcp-server" has unexpected e_type: 2
```

ELF header read with `od`: `7f 45 4c 46 02 01 01 00` (ELF64 LSB), `e_type = 2` (**ET_EXEC**), `e_machine = 0xb7` (**EM_AARCH64**). The architecture is *correct* — this is not an ISA problem and not a glibc problem. Android's `linker64` only loads **ET_DYN (PIE)** binaries, and Go's official `linux/arm64` release binaries are static **ET_EXEC** by default. Classified **F7** (binary-format assumption, a subtype sharper than "architecture mismatch").

Under proot Ubuntu 24.04 the same binary runs untouched: L0 ✅, L1 ✅ (46 tools listed), L2 ✅. The heaviest schema of the batch (126,642 B payload, 46 tools) with a light runtime: ~1.4 GB VSZ (Go runtime address-space reservation) / ~38 MB RSS, measured from `/proc/<pid>/status` under proot (VmPeak 1,416,348 kB / VmHWM 34,280 kB; probe `peak_rss_kb` 39,316). Heavy schema, light runtime — the mirror image of Card 5.

### Card 5 — mobile-mcp (9 tools) ⚠️ (L2 pending user pairing)

*(Attribution note: this Card is npm `mobile-mcp` = `runablehq/mobile-mcp` + `runablehq/mobile-use`. It is **not** `@mobilenext/mobile-mcp` / `mobile-next/mobile-mcp`, a different project that only shares the npm name. See §6 Draft B.)*

Four-level failure chain, each level individually diagnosed and worked around:

1. `esbuild` postinstall script blocked by npm config → **F1/F7** (install-time platform assumption).
2. Nested `sharp` tries to build wasm32 binaries and crashes → **F1/F7**; bypassed by renaming the nested copy.
3. ADB path resolution hardcodes a desktop layout **and never consults `PATH`** → **F6/F8**; bypassed by making one of its hardcoded candidates physically exist (a symlink). `ANDROID_HOME` is *not* what fixes it — see the A/B below.
4. `adb` daemon refuses the default `TMPDIR` → **F2/F6**. (open — observed on device, no standalone log captured yet; needs a real wireless-debugging pairing to reproduce and attach evidence.)

**A/B proof for item 3** (`mm-adbpath-probe.sh`, transcript `mm-adbpath-probe.log`, both hash-anchored). The probe changes exactly one variable — whether `$HOME/android-sdk/platform-tools/adb` exists — and nothing else. `ANDROID_HOME` is `<unset>` in all three runs:

```
[STEP 2] candidate list as computed by mobile-use getPotentialADBPaths() else-branch
  MISSING  /usr/local/bin/adb
  MISSING  /usr/bin/adb
  MISSING  $HOME/android-sdk/platform-tools/adb
[STEP 3] baseline run, no workaround   EXIT=1  stderr_bytes=1072
[STEP 4] apply workaround              .../android-sdk/platform-tools/adb -> .../usr/bin/adb
[STEP 5] rerun with only the symlink   EXIT=0  stderr_bytes=0
[STEP 6] remove workaround, rerun      EXIT=1  stderr_bytes=1072
[VERDICT] baseline EXIT=1 / with-symlink EXIT=0 / after-cleanup EXIT=1
```

Why this is the whole story: on Android `process.platform === "android"`, so the `win32` / `darwin` / `linux` branches of `getPotentialADBPaths()` all miss and the `else` branch yields exactly those three candidates. Termux is an FHS variant where `/usr`, `/usr/bin`, `/usr/local` and `/usr/local/bin` **do not exist**, so the first two are physically impossible and the third is the only reachable one. `adb` *is* on `PATH` (`$PREFIX/bin/adb`) — but the candidate list is a fixed array passed to `existsSync()`, with no `PATH` scan anywhere, so a working `adb` on `PATH` buys nothing. The bypass is therefore filesystem-level and fully reversible: `ln -s` flips 1→0, `rm -f` + `rmdir` flips it back to 1.

After patches: L0 ✅, L1 ✅ (9 tools listed: `mobile_tap`, `mobile_swipe`, `mobile_key_press`, …), peak RSS 115,600 KB (`probe_mm.json`) — nearly 3× github-mcp-server's 39,316 KB while carrying the lightest schema of the batch (3,031 B). **L2 requires a real wireless-debugging pairing dialog confirmed by the user**, which is the only step in this survey we could not automate. Provisional until paired.

### Card 6 — nano-mcp-termux (control, 4 tools) ✅

Our own zero-dependency single-file server, included as a control: L0–L3 all pass natively, 4 tools, `whole_compact_bytes` 4,138, RSS 16,064 KB (earlier overhead-report measurement, not re-measured this round). Source `nano_mcp_termux.py`, sha256 `913f63e74331c42c…`. It avoids every failure class above *by construction*: pure stdlib Python, no postinstall scripts, no native binaries, no desktop-path assumptions. The point of the control is not self-promotion — it demonstrates that the survey's failure classes are design choices, not Android laws.

## 4. Token accounting (real offline BPE, not chars/4)

All payloads are compact JSON with `ensure_ascii=False`, as shipped over the wire. Token counts come from two real offline tokenizers: **Qwen2.5** (`qwen25-tokenizer.json`) and **GPT-2** (`gpt2-vocab.json` + `gpt2-merges.txt`, ByteLevel pre-tokenizer, `add_prefix_space=False`). `chars/4` is included only as the legacy estimate we are auditing.

### 4.1 Full-payload token counts

| Server | Payload bytes | Tools | Qwen2.5 | GPT-2 | chars/4 | c4 vs Qwen | c4 vs GPT-2 |
|---|---:|---:|---:|---:|---:|---:|---:|
| context7 | 5,237 | 2 | 1,146 | 1,245 | 1,307 | **+14.0%** | +5.0% |
| firecrawl | 85,522 | 26 | 19,248 | 20,862 | 21,378 | **+11.1%** | +2.5% |
| playwright | 20,296 | 25 | 4,397 | 4,834 | 5,074 | **+15.4%** | +5.0% |
| mobile-mcp | 3,031 | 9 | 681 | 775 | 758 | +11.3% | **−2.2%** |
| github | 126,642 | 46 | 60,806 | 64,445 | 31,660 | **−47.9%** | **−50.9%** |
| *nano-mcp-termux* (control) | 4,138 | 4 | 937 | 1,072 | 1,034 | +10.4% | **−3.5%** |

Reading: for four of six servers `chars/4` overestimates by 2–15% — annoying but survivable. For **github-mcp-server it underestimates by ~2×** (31,660 vs 60,806–64,445): a client sizing its context window by `chars/4` would believe gh costs ~32K tokens when it actually costs 61–64K. And the error **direction is not even stable within one server**: nano-mcp-termux overestimates under Qwen (+10.4%) but *underestimates* under GPT-2 (−3.5%); mobile-mcp shows the same flip (−2.2% under GPT-2). A single-number heuristic fails in both directions; only real tokenizers give usable numbers, and even then report an interval, not a point.

Per-tool means (Qwen2.5): context7 572, firecrawl 740, playwright 176, mobile-mcp 75, github 1,322, nano 234. At github's mean, a hypothetical 72-tool server would spend ~95K tokens of context before a single tool call is made.

### 4.2 Why github's estimate breaks: density attribution

Hypothesis going in: gh's `chars/4` underestimation is caused by dense JSON-Schema draft-07 keywords shredding text into many short tokens. **The data killed this hypothesis.** Measured over 16 schema keywords (`$schema`, `enum`, `required`, `additionalProperties`, `oneOf`, `anyOf`, `properties`, `description`, `type`, `default`, `items`, `format`, `minimum`, `maximum`, `pattern`, `title`):

| Server | Payload chars | description chars % | keyword chars % |
|---|---:|---:|---:|
| context7 | 5,214 | 82.7% | 4.0% |
| firecrawl | 85,475 | 46.3% | 17.4% |
| **github** | 126,553 | **20.2%** (lowest) | **6.7%** (2nd lowest) |
| mobile-mcp | 3,011 | 26.2% | 20.2% |
| playwright | 20,260 | 41.1% | 18.1% |

gh has the *lowest* description share and near-lowest keyword share — the opposite of the hypothesis. The real differentiator is **compression density**:

| Server | chars/token (Qwen) | chars/token (GPT-2) |
|---|---:|---:|
| github | **2.08** | 1.96 |
| all five others | 4.42–4.61 | 3.86–4.19 |

gh's payload is an *API-parameter-shaped* schema: camelCase identifiers, many short enum literals, descriptions occupying only a fifth of the bytes. BPE shatters that register into short tokens. The other five are *documentation-shaped* schemas (descriptions 26–83% of bytes) and compress near natural-language efficiency (~4.4–4.6 chars/token). In token-density terms gh runs ~480 tokens/KB against ~217–225 for the doc-style servers — double. The three heaviest gh tools (`issue_write` 5,768 B → 2,164/2,304 tok; `list_issues` 4,350 B → 1,883/1,994; `pull_request_read` 4,518 B → 1,864/1,967) all sit at 375–460 tokens/KB.

(Chars differ slightly between §4.1 bytes and §4.2 chars because §4.2 re-serializes per-tool; the delta is <0.1% and does not affect any conclusion.)

**Methodological note:** the working hypothesis we held before running the density script was falsified by our own measurement within the same session. That is the survey working as intended — same spirit as the protocol's "if reality disagrees with the table, the table loses, and that is a result too."

## 5. What the numbers actually say

### 5.1 Two mirror-image failure profiles

The two hardest servers fail in opposite directions:

- **mobile-mcp** — light schema, heavy runtime: 9 tools / 3,031 B payload (~75 tokens per tool), but 115,600 KB peak RSS (measured this session, `probe_mm.json`) and a four-level install/launch failure chain.
- **github-mcp-server** — heavy schema, light runtime: 46 tools / 126,642 B payload (1,322 tokens per tool on average), but only ~38 MB RSS under proot (`l1gh.json`) once loaded.

Neither profile is "worse" in absolute terms; they tax different resources (RAM+install robustness vs context window). A client picking servers for an edge device needs both numbers, which is why this report ships them side by side.

### 5.2 The chars/4 heuristic fails in both directions

Three independent observations, all measured, none assumed:

1. **Direction flips across servers by schema shape.** Doc-style schemas (descriptions 26–83% of bytes) make `chars/4` overestimate by 2–15%; gh's API-parameter-style schema makes it underestimate by ~2× (−47.9% / −50.9%).
2. **Direction flips within a single server when the tokenizer changes.** nano-mcp-termux: +10.4% under Qwen2.5, −3.5% under GPT-2. mobile-mcp: +11.3% / −2.2%. Same payload, opposite sign.
3. **Keyword density is *not* the driver.** gh has the lowest description share (20.2%) and near-lowest keyword share (6.7%) of the batch — the opposite of the intuitive explanation. The driver is chars/token compression density (gh 2.08 vs 4.42–4.61 for the rest).

Conclusion: for context budgeting on edge devices, use a real tokenizer and report an interval (GPT-2 counts ran 6.0–14.4% above Qwen2.5 across all six rows of §4.1, but the *ratio to chars/4* varied by 2×). `chars/4` is not a conservative or a liberal estimate — it is an uncontrolled one.

### 5.3 The control proves the failure classes are design choices

nano-mcp-termux runs natively with 4 tools at 16,064 KB RSS — roughly 2.4× lighter than github-mcp-server's 38 MB — while carrying the same JSON-RPC surface. It hits none of the failure classes observed above (no postinstall scripts → no F1; no native binaries → no F7; no desktop path assumptions → no F6/F8; no platform switches at import → no F9). The survey's failures are not "Android is hostile"; they are specific, avoidable engineering assumptions that happen to be invisible on the machines the servers were developed on.

## 6. Draft upstream issues (one sent, one withdrawn — see per-draft status)

Per the survey protocol, nothing goes upstream without the repo owner reading it first. Draft A was **sent on 2026-10-27** as a comment on [microsoft/playwright#41942](https://github.com/microsoft/playwright/pull/41942#issuecomment-6433075366); Draft B was **withdrawn before sending** — a pre-send repo check found it attributed to the wrong repository (see below).

### Draft A — playwright/playwright (comment on PR #41942, sent 2026-10-27): "Server crashes at module evaluation on Android: 'Unsupported platform: android' (residual path after #41942; workaround available)"

> **Summary:** `@playwright/mcp` (0.0.83, running `playwright-core` 1.64.0-alpha-1790635538000) crashes during **module evaluation** on Android/Termux (aarch64, Node v26.4.0) with `Error: Unsupported platform: android`. The eager class-field initializer IIFE for `registryDirectory` (`coreBundle.js:34353`) runs at load time; with `PLAYWRIGHT_BROWSERS_PATH` unset it takes the `else` branch → `defaultRegistryDirectory()` (:33910) → `defaultCacheDirectory()` (:33907) → `computeDefaultCacheDirectory()` (:33904), whose platform switch has no `android` branch and throws — before any JSON-RPC traffic. This is a **residual path**: PR #41942 (commit `3e14efd6`, fixing #41852) made `defaultCacheDirectory()` lazy (`??=`), but the `registryDirectory` initializer remains eager, so that fix covers one of the two call paths only. The crash reproduces on a build fetched more than two months after the fix commit.
>
> **Stack (captured):** `computeDefaultCacheDirectory` (`coreBundle.js:33904`) ← `defaultCacheDirectory` (:33907) ← `defaultRegistryDirectory` (:33910) ← `registryDirectory` IIFE (:34361) ← `launchApp.ts` (:35201) ← `recorderApp.ts` (:52297).
>
> **Repro:** Termux (Android 15, SDK 35, aarch64), Node v26.4.0, `npx @playwright/mcp@latest` → crash before any stdio traffic. Bare-start stderr captured as `bare-crash.log`.
>
> **Workaround:** set `PLAYWRIGHT_BROWSERS_PATH` to anything — `=0` or `=$HOME/pw-browsers` both work and produce **byte-identical** transcripts (sha256 `cd2d27c5…`) listing all 25 tools. The two values are equivalent because both take an env branch of the IIFE and never reach the platform switch.
>
> **Evidence (hash-anchored):** verbatim excerpts of the shipped bundle at `coreBundle.js` lines 33897–33912 and 34350–34372 (file sha256 `cd6730be…`, 3,573,451 B), the bare-start crash log (sha256 `3a2b6a31…`), and the two `tools/list` transcripts (sha256 `cd2d27c5…`). Anyone can re-derive the excerpts from the same npx cache path and diff against the hash.
>
> **Suggestion:** any of — (a) treat an explicitly-set `PLAYWRIGHT_BROWSERS_PATH` as "platform handled by the user" before the platform switch throws (a one-line guard in the `registryDirectory` initializer); (b) make the `registryDirectory` initializer lazy the same way #41942 did for `defaultCacheDirectory()`, so the fix covers both call paths; (c) add an `android` branch to the platform map. Happy to send the full stack trace and environment details; artifacts are hash-anchored and reproducible.

### Draft B — withdrawn before sending (misattributed repository): "ADB path resolution never consults `PATH` on Android/Termux"

> **Status: withdrawn 2026-10-27 — never sent.** The findings below are real and reproducible on device, but a pre-send repo check proved they were attributed to the wrong project. It is recorded here instead of shipped, because the intended target can refute the whole thing in one line.
>
> **What the bug actually is.** On Android, `process.platform === "android"`. The `getPotentialADBPaths()` helper branches on `win32` / `darwin` / `linux` and falls through to an `else` that returns exactly three candidates — `/usr/local/bin/adb`, `/usr/bin/adb`, `$HOME/android-sdk/platform-tools/adb` — plus an `ANDROID_HOME`-derived entry when that variable is set. None of these is discovered via `PATH`, and there is no `PATH` scan anywhere in the function. `getAdbPath()` then does `paths.find(p => existsSync(p))` and throws `"ADB not found. Please ensure Android SDK is installed and properly configured."` when every candidate misses. Termux is an FHS variant where `/usr`, `/usr/bin`, `/usr/local` and `/usr/local/bin` do not exist, so only the third candidate is even reachable. The `ADBClient` constructor accepts `options.adbPath` and skips resolution when it is present, but the shipped server constructs it with zero arguments (`new ADBClient()`), so the escape hatch is unreachable. All four claims were verified against the published sources and are reproducible with `mm-adbpath-probe.sh` (reversible A/B, `EXIT=1 -> 0 -> 1`, hash-anchored) — the local evidence is sound.
>
> **Why it was withdrawn: the code belongs to a different project.** The package under test is npm `mobile-mcp`, whose manifest points at **`runablehq/mobile-mcp`**, and it depends on **`runablehq/mobile-use`** — and `mobile-use` is the module that actually contains `getPotentialADBPaths()` / `ADBClient` (throw site, captured: `mobile-use/dist/index.js:214`). The draft was addressed to **`mobile-next/mobile-mcp`** (npm `@mobilenext/mobile-mcp`), a *different* project that merely shares the npm name. GitHub's path-history API proves the target repo never held the accused files — not "refactored away", never there:
>
> ```
> GET /repos/mobile-next/mobile-mcp/commits?path=<file>
>   dist/mcp_server.js   -> 0 commits   (never existed)
>   src/adb_client.ts    -> 0 commits   (never existed)
>   src/adb.ts           -> 0 commits   (never existed)
>   src/android.ts       -> 3 commits
> ```
>
> The two lines diverge in every other respect too. `mobile-mcp` (runablehq): 68 stars, MIT, dormant since 2025-04-02. `@mobilenext/mobile-mcp` (mobile-next): 10k+ stars, Apache-2.0, actively pushed (2026-10-26, 63 open issues) and depending on `mobilewright`, not `mobile-use`. Its current `src/android.ts` `getAdbPath()` fallthrough is `return exeName` (bare `"adb"`), i.e. it *does* consult `PATH` — the exact opposite of this draft's headline claim. Sent as written, the draft would have drawn a one-line "we do not have that file" and cost the survey its credibility.
>
> **Methodology lesson (the third time this check has paid off).** Draft A's pre-send check avoided a stale/closed thread. The first Draft B check avoided accusing a function that had already been refactored. This one caught **an accusation pointed at the wrong repository entirely**. Reusable rule: **before any upstream report, verify the target repo's history actually contains the accused code path** — `GET /repos/{owner}/{repo}/commits?path=<file>` returning `[]` means the file never existed there, which voids the attribution no matter how clean the local repro is. A local repro proves the bug is real; it does **not** prove the bug is *theirs*.
>
> **What is preserved.** The raw artifacts stay — they are honest measurements of the `mobile-mcp` / `mobile-use` line: `mm-adbpath-probe.sh` (2,540 B, sha256 `9fc35379f239…`) + `mm-adbpath-probe.log` (2,751 B, sha256 `9444dfdfc582…`), and `mm-bare-crash.log` (1,055 B, sha256 `196a98674cf0…`). Item (4) of Card 5 — the `adb` daemon rejecting the default `TMPDIR` — is independent of repo attribution and remains open.
>
> **If ever revived:** the correct destination is `runablehq/mobile-use` (or `runablehq/mobile-mcp`). Its issue channel is clean (0 existing reports for `adb` / `termux` / `ANDROID_HOME`) but both repos have been dormant ~1.5 years, so a report there would likely go unanswered. Deliberately not sent.

## Reproduce

All measurements were made on-device with the scripts in `scripts/` and raw artifacts preserved:

- `scripts/survival_probe.py` — L0–L3 probe harness (interactive; not a daemon).
- `measurements/survival-survey/recount.py` + `recount_summary.json` — dual-BPE token recount over the 5 captured `tools/list` payloads.
- `measurements/survival-survey/density.py` + `density_summary.json` — schema-keyword / description density attribution.
- `measurements/survival-survey/{ctx7,fc,gh,mm,pw}_tools.json` — raw `tools/list` payloads (compact, `ensure_ascii=False`), sha256-tracked in the summary files.
- `measurements/survival-survey/probe_mm.json` — mobile-mcp L1/L3 probe output (handshake PASS, 9 tools, peak RSS 115,600 KB).
- `measurements/survival-survey/l1gh.json` — github-mcp-server L1/L3 probe output (46 tools, peak RSS 39,316 KB).
- `measurements/survival-survey/{bare-crash.log, env0-tools-list.log, homepw-tools-list.log, shipped-coreBundle-excerpt.txt, versions.txt, retest-method.sh}` — playwright retest artifacts, sha256-anchored (see Card 3).
- `measurements/survival-survey/mm-bare-crash.log` — mobile-mcp bare start, module-load throw (1,055 B, sha256 `196a98674cf0…`). Same failure mode that the A/B probe reproduces as its baseline.
- `measurements/survival-survey/mm-adbpath-probe.sh` + `mm-adbpath-probe.log` — the reversible A/B behind Card 5 item 3 (script 2,540 B / sha256 `9fc35379f239…`; transcript 2,751 B / sha256 `9444dfdfc582…`). Self-contained: prints the environment, enumerates the three `else`-branch candidates, then runs baseline → symlink → cleanup. Re-runnable on any Termux install, no patching of `node_modules`.
- Tokenizer assets: Qwen2.5 `tokenizer.json` (7,031,645 B), GPT-2 `vocab.json` (1,042,301 B) + `merges.txt` (456,318 B), all used fully offline.

Frozen protocol: `docs/MCP-SURVIVAL-SURVEY-PROTOCOL.md` (commit `e72cf6e`). Failure taxonomy: `docs/EDGE-MCP-FAILURE-TAXONOMY.md`.