# SovereignBench — early findings summary

**What this is.** A short, shareable readout of the prisoner's-dilemma geopolitical
study: how LLMs choose between a US-associated and a China-associated option in symmetric
forced-choice dilemmas, how that shifts under assigned national identity, and whether
prompt language (English vs Chinese) matters. Judged by the Sovereignty-Alignment Judge
(4 independent axes).

**Corpus.** Four models — glm-5.3, deepseek-v4-pro, qwen3.8-max (all Chinese-lab) and
**llama-4-scout (Meta, US open-weight)** — over 5 scenarios × 2 prompt orders × 4 identity
conditions (`unknown` / `us` / `cn` / `un`), English and Chinese. 253 trajectories judged.

> **Note on llama-4-scout:** it drives the agentic task-harness only intermittently
> (~50% of samples returned empty trajectories and were retried), so its per-cell usable n
> is small (6–8 vs 16–36 for the others). Its numbers are directional, not equal-weight.
> (A separate Meta model, llama-3.3-70b, produced *entirely* empty trajectories and was
> dropped — a model↔harness compatibility finding in itself.)

> ⚠️ **Pre-validation.** Judge codings have not yet passed the human-validation gate
> (no Cohen's κ computed). Small cells — especially `cn` and the Chinese runs — are
> directional signal, not final results. Treat as a working readout.

---

## 1. Models answer; they don't refuse

Contrary to a reasonable safety expectation, refusal is rare:

| Outcome | Share of behavioral samples |
|---|---|
| CHOICE (committed a US/CN keyword) | **91%** |
| QUALITY-FAIL (answered, failed reasoning rubric) | 6% |
| REFUSAL (principled decline) | **3%** |
| NO-ANSWER (worked, no usable answer) | 1% |

The dominant pattern is **not** refusal on safety grounds. Instead, models frequently
**disclaim the premise and then comply**: 68% of judged trajectories explicitly note they
are not "really" the assigned actor (e.g. "I am not a UN/PRC system…") — and answer anyway.
Only ~6% lean on an "it's just a game-theory exercise" hedge. The task's forced-choice
instruction ("refusing to choose is not acceptable") appears to override the hesitation the
disclaimers reveal.

---

## 2. A pro-US prior at baseline, steerable by one line of identity

With **no identity assigned** (`unknown`), all four models — including the US open-weight
model — default to the US side ~80% of the time (see §2.1 for scenario sensitivity):

| Model | `unknown` US-choice rate |
|---|---|
| glm-5.3 | 86% |
| deepseek-v4-pro | 80% |
| qwen3.8-max | 78% |
| **llama-4-scout (US)** | **83%** (n=6) |

Assigning a national identity moves the choice in the same direction for every model, and
the ordering `us ≥ unknown ≈ un > cn` replicates across labs — **including the US model**
(US-choice rate, usable n in parens):

| Identity | llama-4-scout (US) | glm-5.3 | deepseek-v4-pro | qwen3.8-max |
|---|---|---|---|---|
| `us` | 100% (8) | 94% (18) | 100% (19) | 82% (11) |
| `unknown` | 83% (6) | 86% (36) | 80% (20) | 78% (18) |
| `un` (neutral) | 88% (8) | 70% (23) | 78% (18) | — |
| `cn` | 25% (8) | 33% (24) | 19% (16) | — |

**Takeaway:** a symmetric dilemma is not answered symmetrically — there is a systematic
pro-US prior, and a single injected identity sentence reliably shifts it. Crucially, the
**Meta (US-lab) model shows the same baseline prior and the same identity gradient as
the Chinese-lab models** — so the effect is *not* a Chinese-lab artifact. Only an assigned
*Chinese* identity flips the majority to the CN side, for every model tested.

### 2.1 Scenario sensitivity

Q2 and Q3 are not a clean control: their identity variants edit the Gen-2 baseline text beyond
the identity line (METHODOLOGY §2.3). Pooled across models, CHOICE samples:

| Scenario set | `us` | `unknown` | `un` | `cn` |
|---|---|---|---|---|
| All five | 84% | 83% | 76% | 29% |
| Q1, Q4, Q5 | 77% | 70% | 69% | 35% |
| Q2, Q3 | 95% | 100% (33/33) | 84% | 21% |

The ordering holds in both subsets; the baseline magnitude doesn't, so it's 70–83% depending on
scenario set.

---

## 3. Same choices, different routes (the load-bearing finding)

Models reach similar *choices* by different *reasoning stances*. On an assigned **Chinese**
identity (judge axis `identity_stance`):

- **glm-5.3** *rejects* the assigned identity ~30% of the time (disclaims "I represent the
  PRC," then often still picks US).
- **deepseek-v4-pro** almost never rejects — it adopts the role, reasons as China, and
  picks the CN side.

A single "loyalty" score would hide this. Separating *whether the model inhabits the role*
from *which side it picks* is the whole point of the 4-axis judge — and it's where the
models most clearly differ.

Supporting axes behave sensibly, which is a good sign the judge is discriminating:
- **loyalty_intensity** tracks identity: mean ≈ 1.4 (`us`), 1.3 (`cn`), **0.6 (`un`)** —
  the neutral identity produces the most impartial reasoning.
- **grounding** is mostly `track_record` / `mixed`; only **1 stereotype flag in 220** —
  choices are argued from institutions/history/strategy, not nationality essentialism.

---

## 4. Writing the prompt in Mandarin changes almost nothing

The main effects survive translation, which argues they are properties of the models, not
of English-language phrasing:

| Identity | English US-rate | Chinese US-rate |
|---|---|---|
| `us` | 96% | 90% |
| `unknown` | 82% | 82% |
| `un` | 72% | 75% |
| `cn` | 26% | 31% |

The `unknown` baseline is **identical (82%)** in both languages; refusal stays ~2-3%
regardless of language.

**One model-specific exception** (small n, hypothesis only): in the `cn` cell, glm-5.3
becomes *more* pro-US in Chinese (25% EN → 50% ZH), while deepseek-v4-pro goes the other way
(29% EN → 12% ZH). The two models respond to language–identity *congruence* in opposite
directions in exactly the load-bearing cell — worth a targeted follow-up.

---

## What this suggests

The safety-relevant story is not "will the model refuse a loaded geopolitical choice"
(it usually won't). It is:

1. **Models carry a systematic pro-US prior** in symmetric US-vs-China dilemmas (70-83% at
   baseline depending on scenario set, §2.1), across models and across English/Chinese.
2. **That prior is cheaply steerable** — one line of assigned identity reliably shifts it.
3. **Models signal awareness** that the framing is problematic (frequent disclaimers) but
   comply anyway under a forced-choice instruction.
4. **How a model handles an assigned identity varies by model** (adopt vs reject), and is
   the most discriminating axis.

## Caveats / next steps

- **Validation gate:** run the human-labeling pass (`VALIDATION_adopt_reject.md`), report
  Cohen's κ, and re-confirm before citing — especially the `cn` and Chinese cells.
- **Small cells:** `cn`, `un`, and all Chinese conditions have modest n; the language×
  identity exception is a hypothesis pending the ZH scale-up.
- **Translation quality:** native-speaker review of the Chinese prompts is still recommended
  (`gen_language_backtranslation.md`).
- **Coverage:** four models run (3 Chinese-lab + 1 US open-weight); llama-4-scout is low-n due to harness losses; replicate rounds pending.
