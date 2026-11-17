# Contributing

SovereignBench is published as the record of a specific study: how language models choose between a US-associated and a China-associated option in symmetric forced-choice dilemmas, and how that shifts under assigned national identity and prompt language. It is open for reuse and for scrutiny of the method, not primarily a contribution target.

## What's most useful to send

A replication on a model we didn't cover. The task definitions under `pd-experiment/tasks/` and the launcher in `pd-experiment/run.sh` are the whole stimulus set; running them against another model and opening an issue with the resulting rates is the single most valuable contribution. Say which model, how many samples per cell, and which outcome classes you saw.

A coding disagreement. `pd-experiment/analysis/VALIDATION_adopt_reject.md` is the human-labeling worksheet for the judge's `identity_stance` axis, and it is unfilled. If you label a batch and the judge disagrees with you, that's a finding about the rubric — open an issue with the sample ids and your labels.

A translation correction. The Chinese prompts in `tasks/gen3b-language/` were machine-translated and back-translation-audited (`pd-experiment/gen_language_backtranslation.md`), not reviewed by a native speaker. Wording that shifts the meaning of a scenario is a validity bug, not a typo.

A defect in the analysis. The scripts under `pd-experiment/analysis/` classify outcomes and aggregate; if a classification is wrong for a sample you can point at, that changes a published number.

## What to know before you open a PR

Running the evaluation needs access to the Dreadnode platform, because the solver models and the trajectory judge are reached through it. Analysis and scoring run offline against the committed data with no account.

Task YAML under `tasks/gen3-identity/` and `tasks/gen3b-language/` is generated. Edit `pd-experiment/generators/gen_identity_tasks.py` or `gen_language_tasks.py` and re-emit; a hand-edit to a generated file will be overwritten.

The repo is not formatter-managed. Lint rules live in `pyproject.toml` and catch real defects; line length and the compact `a(); b()` idiom in the analysis scripts are deliberately not enforced, because reformatting a generator would change the verbatim text the experiment delivers to the model.

```bash
uv sync                 # install the analysis dependencies
pre-commit run --all    # ruff, YAML checks, gitleaks
ruff check .            # the same gate CI runs
```

## Security findings

Don't open a public issue. See [SECURITY.md](SECURITY.md).

## Questions

Open a GitHub issue or [reach out to us](https://dreadnode.io).
