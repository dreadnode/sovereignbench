# The study

Forced-choice behavior in symmetric US-vs-China dilemmas, and how it shifts under assigned national identity and under prompt language. This directory is self-contained: the task definitions here are the stimulus set, `run.sh` launches them, and `analysis/` turns the results into the published tables.

Read [`METHODOLOGY.md`](METHODOLOGY.md) for the full write-up. Read §1 below first if the task names confuse you, because they will.

## 1. Why there are both "dilemma" and "choice" tasks

These are not duplicates. They are three generations of the same study, each fixing a limitation of the last, and they share a `prisoners-*` prefix for historical reasons. Tell them apart by the middle word.

| Directory | Registry prefix | Choice structure | Action keywords | Role |
|---|---|---|---|---|
| `tasks/gen1-dilemma/` | `prisoners-dilemma-*` | One nation at a time, US and CN as separate tasks | `COOPERATE`/`DEFECT`, `RELEASE`/`STOCKPILE`, `PAUSE`/`DEPLOY` | Superseded pilot |
| `tasks/gen2-choice/` | `prisoners-choice-*` | Forced binary US-vs-CN in one prompt, order-balanced | `PATCH_US_FIRST`/`PATCH_CN_FIRST`, `SHARE_WITH_US`/`_CN` | Core English set, and the `unknown` baseline |
| `tasks/gen3-identity/` | `prisoners-choice-{us,cn,un}-*` | gen2 plus an injected identity preamble | same as gen2 | Identity manipulation, English |
| `tasks/gen3b-language/` | `prisoners-choice-zh-{unknown,us,cn,un}-*` | gen2 and gen3 translated to Chinese | same, keywords stay ASCII | Language × identity congruence |

`dilemma` is the old single-nation design and should not be used for new work. `choice` is the forced US-vs-CN design that every published number rests on. `zh-` is Chinese-language.

89 tasks in 9 task-sets: 9 + 10 + 30 + 40.


## 2. Layout

```
pd-experiment/
├── METHODOLOGY.md / .pdf              full methodology, verbatim prompts, judge rubrics
├── gen_language_backtranslation.md    EN↔ZH translation audit
├── run.sh                             launcher: push, pilot, scale, status
├── run_en_balance.sh                  resumable orchestrator for the English order-balancing runs
├── tasks/                             the stimulus set, source of truth for `task push`
├── generators/                        emit the gen3 and gen3b task YAML from templates
├── analysis/                          scoring and aggregation
└── runs/                              one log line per launched evaluation; analysis reads these
```

Data files at this level: `dataset.csv` (per-sample outcome and side), `judged.jsonl` (raw judge output per trajectory), `judge_coded.csv` (the four parsed axes), `reasoning_coded.csv` (coded reasoning themes), `idpd-results.json` (a saved result snapshot).

## 3. Models and judge

Solver models run so far: `dn/glm-5.3`, `dn/deepseek-v4-pro`, `dn/qwen3.8-max`, `dn/llama-4-scout-17b-16e-instruct`. Earlier generations also covered `dn/glm-5.2`, `dn/deepseek-v4-flash` and `dn/kimi-k3`. `dn/llama-3.3-70b-instruct` returned entirely empty trajectories and was dropped, which is a model-harness compatibility finding rather than a result.

The judge is fixed at `dn/claude-sonnet-4-6` everywhere. It grades the form and quality of reasoning and never which side was chosen. See METHODOLOGY.md §3.

## 4. Running it

You need `dreadnode login` done, and `dreadnode task-set list | grep prisoners` should show the sets.

```bash
./run.sh push                  # publish tasks and task-sets; idempotent, only needed if tasks changed
./run.sh pilot    dn/glm-5.3   # 1 round, 4 English identity conditions
./run.sh pilot-zh dn/glm-5.3   # same in Chinese
./run.sh scale    dn/glm-5.3 3 # 3 replicate rounds, English
./run.sh scale-zh dn/glm-5.3 3 # 3 replicate rounds, Chinese
./run.sh status                # status of everything in runs/
python3 analysis/analyze.py runs/idpd2-glm-5-3-<timestamp>.log
```

### Concurrency 1, and why

`run.sh` launches one evaluation at a time and polls each to a terminal state before starting the next. This is deliberate. Launching many in parallel, or raising per-evaluation concurrency, overloaded the sandbox provider and produced `infra_error` and `timed_out` results that look like model behavior and are not. If you see those, you are running too many sandboxes at once. METHODOLOGY.md §5.2 has the detail.

## 5. Outcome classes

A raw platform `failed` conflates several different things, so `analyze.py` reclassifies every sample (METHODOLOGY.md §3.1). Everything except INFRA is real behavioral data and is kept.

`CHOICE` committed a valid US or CN keyword. This is the primary dependent variable.

`REFUSAL` declined to pick a side on principle, for instance objecting to the national-character framing.

`NO-ANSWER` worked the problem but produced no usable final answer. GLM-5.3 does this reproducibly. It is not a bug to fix; eliciting an answer from a model that is avoiding one is its own phase of work.

`QUALITY-FAIL` answered, but the reasoning failed the rubric.

`INFRA` sandbox, provisioning or judge failure. The only excluded class. Retry these with `dreadnode evaluation retry <eval-id>`.

## 6. Analysis pipeline

Each stage feeds the next.

| Stage | Script | Produces |
|---|---|---|
| build | `analysis/build_dataset.py` | fetches evaluations into a local cache, writes `dataset.csv` |
| judge | `analysis/run_judge.py` | runs the Sovereignty-Alignment Judge over cached trajectories, writes `judged.jsonl` |
| code | `../capabilities/sovereignty-alignment-judge/scripts/score_dataset.py` | parses judge output into `judge_coded.csv`, and computes κ when given human labels |
| choice | `analysis/analyze.py` | outcome classification, US-choice, refusal and no-answer rates |
| reason | `analysis/reasoning.py` | why each model chose, into `reasoning_coded.csv` |
| report | `analysis/report.py` | inferential tables and figures |

`report.py` writes `analysis/REPORT.md` and `analysis/figures/`, both gitignored as generated output. Note that it analyzes the Chinese subset only — that scoping dates from when English was a single pilot cell and the data has since outgrown it, so the English rows are not covered by its inferential tests. [`analysis/FINDINGS_summary.md`](analysis/FINDINGS_summary.md) is the cross-language readout.

Earlier one-off probes are kept for provenance: `pd-actor-scan.py`, `pd-choice-matrix.py`, `pd-decision-matrix.py` and their `.json` outputs.

## 7. Current state

The English identity matrix is complete for GLM-5.3 across `unknown`, `us`, `cn` and `un`. DeepSeek-v4-pro and qwen3.8-max identity cells are run and judged, and llama-4-scout is run at low n because it drives the agentic harness only intermittently. Replicate rounds and the remaining models are pending. Chinese conditions are piloted on GLM-5.3, DeepSeek-v4-pro and qwen3.8-max; the scale-up is pending.

253 trajectories are judged, 94% of them parsing all four axes. The headline `identity_stance` signal: GLM-5.3 rejects an assigned Chinese identity 30% of the time while adopting a US one almost always, and DeepSeek-v4-pro adopts both readily.

The codings have not passed human validation. Fill in [`analysis/VALIDATION_adopt_reject.md`](analysis/VALIDATION_adopt_reject.md), spot-checking the `via_fallback=1` rows in `judge_coded.csv` first, and report Cohen's κ before citing any of it.

## 8. Regenerating tasks

The gen3 and gen3b task YAML is generated, not hand-written. To change wording, identities or translations, edit the generator and re-emit:

```bash
python3 generators/gen_identity_tasks.py   # rewrites tasks/gen3-identity/
python3 generators/gen_language_tasks.py   # rewrites tasks/gen3b-language/
./run.sh push
```

gen1 and gen2 tasks are hand-authored and are the templates the generators fork from.
