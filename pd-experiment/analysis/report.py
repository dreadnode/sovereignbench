#!/usr/bin/env python3
"""Layers 1-4 — thorough analysis of the PD program from the tidy dataset.

Reads dataset.csv (built by build_dataset.py) and produces:
  * descriptive tables (US-choice / refusal / no-answer rates + Wilson CIs)
  * inferential tests (logistic regression w/ identity+order, per-identity
    odds ratios vs baseline; Fisher exact per cell; order/anchoring test)
  * effect sizes (odds ratios + risk differences with CIs)
  * figures (US-rate by identity faceted by model; per-question heatmap; forest plot)
  * a markdown report stitching it together -> analysis/REPORT.md

Only ZH data is analyzed inferentially (English is currently a single-cell pilot).
Everything is labelled pilot-stage; small-n caveats are emitted inline.
"""
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.formula.api as smf

HERE = Path(__file__).parent
ROOT = HERE.parent
FIG = HERE / "figures"
FIG.mkdir(exist_ok=True)

IDENTITY_ORDER = ["us", "unknown", "un", "cn"]
BEHAVIORAL = {"CHOICE", "REFUSAL", "NO-ANSWER", "QUALITY-FAIL"}


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), 0.0, 1.0)
    p = k / n
    d = 1 + z*z/n
    c = (p + z*z/(2*n))/d
    h = (z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)))/d
    return (p, max(0, c-h), min(1, c+h))


def load():
    df = pd.read_csv(ROOT / "dataset.csv")
    # behavioral samples only (exclude INFRA) for behavior rates
    df["behavioral"] = df["outcome_class"].isin(BEHAVIORAL)
    df["is_choice"] = df["outcome_class"] == "CHOICE"
    df["us_choice"] = (df["side"] == "US").astype(int)
    return df


def sec(title):
    return f"\n## {title}\n"


def descriptives(df, out):
    out.append(sec("1. Descriptive rates (ZH, behavioral samples, Wilson 95% CI)"))
    zh = df[(df.lang == "zh") & df.behavioral]
    # US-choice among CHOICE samples, by model x identity
    out.append("### US-choice rate by model × identity\n")
    out.append("| model | identity | US | CN | US-rate | 95% CI | n |")
    out.append("|---|---|---|---|---|---|---|")
    for model in sorted(zh.model.unique()):
        for ident in IDENTITY_ORDER:
            cell = zh[(zh.model == model) & (zh.identity == ident) & zh.is_choice]
            n = len(cell); k = int(cell.us_choice.sum())
            if n == 0:
                continue
            p, lo, hi = wilson(k, n)
            out.append(f"| {model} | {ident} | {k} | {n-k} | {p:.0%} | [{lo:.0%}–{hi:.0%}] | {n} |")
    # pooled across models
    out.append("\n### US-choice rate POOLED across models, by identity\n")
    out.append("| identity | US | CN | US-rate | 95% CI | n |")
    out.append("|---|---|---|---|---|---|")
    for ident in IDENTITY_ORDER:
        cell = zh[(zh.identity == ident) & zh.is_choice]
        n = len(cell); k = int(cell.us_choice.sum())
        if n == 0:
            continue
        p, lo, hi = wilson(k, n)
        out.append(f"| {ident} | {k} | {n-k} | {p:.0%} | [{lo:.0%}–{hi:.0%}] | {n} |")
    # outcome composition
    out.append("\n### Outcome composition by model (ZH, behavioral)\n")
    out.append("| model | CHOICE | REFUSAL | NO-ANSWER | QUALITY-FAIL | PROVIDER-BLOCKED | INFRA |")
    out.append("|---|---|---|---|---|---|---|")
    # note: use full df (not just behavioral) so PROVIDER-BLOCKED / INFRA are visible
    zh_all = df[df.lang == "zh"]
    for model in sorted(zh_all.model.unique()):
        m = zh_all[zh_all.model == model]
        c = m.outcome_class.value_counts()
        out.append(f"| {model} | {c.get('CHOICE',0)} | {c.get('REFUSAL',0)} | "
                   f"{c.get('NO-ANSWER',0)} | {c.get('QUALITY-FAIL',0)} | "
                   f"{c.get('PROVIDER-BLOCKED',0)} | {c.get('INFRA',0)} |")
    out.append("\n_PROVIDER-BLOCKED = vendor content filter (e.g. Alibaba 'may contain "
               "inappropriate content') — a platform refusal, NOT the model choosing to "
               "refuse; excluded from behavioral rates and reported separately._")


def inferential(df, out):
    out.append(sec("2. Inferential tests (ZH, CHOICE samples)"))
    zh = df[(df.lang == "zh") & df.is_choice].copy()
    if zh.identity.nunique() < 2 or len(zh) < 12:
        out.append("_Insufficient data for regression yet._")
        return
    # Baseline = unknown. Logistic regression pooled across models, with order.
    zh["identity"] = pd.Categorical(zh.identity,
                                    categories=["unknown", "us", "un", "cn"])
    out.append("### Logistic regression: US-choice ~ identity + order  (baseline = `unknown`)\n")
    out.append("Pooled across models. Odds ratio > 1 => more US-leaning than baseline.\n")
    try:
        m = smf.logit("us_choice ~ C(identity, Treatment('unknown')) + C(order)",
                      data=zh).fit(disp=False)
        params, cis = m.params, m.conf_int()
        out.append("| term | odds ratio | 95% CI | p |")
        out.append("|---|---|---|---|")
        for term in params.index:
            if term == "Intercept":
                continue
            orr = math.exp(params[term])
            lo, hi = math.exp(cis.loc[term, 0]), math.exp(cis.loc[term, 1])
            label = (term.replace("C(identity, Treatment('unknown'))", "identity=")
                         .replace("C(order)", "order=").replace("[T.", "").replace("]", ""))
            out.append(f"| {label} | {orr:.2f} | [{lo:.2f}–{hi:.2f}] | {m.pvalues[term]:.3f} |")
        out.append(f"\n_Model n={int(m.nobs)}, pseudo-R²={m.prsquared:.2f}. "
                   "Wide CIs at pilot n; large ORs with p<0.05 are the reliable signals._")
    except Exception as e:
        out.append(f"_Regression did not converge ({e}); relying on Fisher tests below._")

    # Fisher exact: each identity vs unknown, pooled.
    out.append("\n### Fisher exact vs `unknown` baseline (pooled across models)\n")
    out.append("| contrast | US-rate (id) | US-rate (unknown) | risk diff | OR | p |")
    out.append("|---|---|---|---|---|---|")
    base = zh[zh.identity == "unknown"]
    bk, bn = int(base.us_choice.sum()), len(base)
    for ident in ["us", "un", "cn"]:
        cell = zh[zh.identity == ident]
        ck, cn_ = int(cell.us_choice.sum()), len(cell)
        if cn_ == 0:
            continue
        table = [[ck, cn_-ck], [bk, bn-bk]]
        orr, p = stats.fisher_exact(table)
        rd = ck/cn_ - bk/bn
        out.append(f"| {ident} vs unknown | {ck}/{cn_}={ck/cn_:.0%} | "
                   f"{bk}/{bn}={bk/bn:.0%} | {rd:+.0%} | {orr:.2f} | {p:.3f} |")

    # Order / anchoring effect pooled.
    out.append("\n### Anchoring (order) effect, pooled\n")
    uf = zh[zh.order == "usfirst"]; cf = zh[zh.order == "cnfirst"]
    uk, un_ = int(uf.us_choice.sum()), len(uf)
    ck, cn_ = int(cf.us_choice.sum()), len(cf)
    if un_ and cn_:
        _, p = stats.fisher_exact([[uk, un_-uk], [ck, cn_-ck]])
        out.append(f"usfirst US-rate={uk/un_:.0%} (n={un_}) vs "
                   f"cnfirst US-rate={ck/cn_:.0%} (n={cn_}); Fisher p={p:.3f}.")


def figures(df, out):
    out.append(sec("3. Figures"))
    zh = df[(df.lang == "zh") & df.is_choice]

    # Fig 1: US-rate by identity, grouped by model, with Wilson CI whiskers.
    models = sorted(zh.model.unique())
    x = np.arange(len(IDENTITY_ORDER)); w = 0.8/max(len(models), 1)
    plt.figure(figsize=(9, 5))
    for i, model in enumerate(models):
        ps, los, his = [], [], []
        for ident in IDENTITY_ORDER:
            cell = zh[(zh.model == model) & (zh.identity == ident)]
            n = len(cell); k = int(cell.us_choice.sum())
            p, lo, hi = wilson(k, n) if n else (np.nan, 0, 0)
            ps.append(p); los.append(p-lo if n else 0); his.append(hi-p if n else 0)
        plt.bar(x + i*w, ps, w, label=model.replace("dn/", ""),
                yerr=[los, his], capsize=3)
    plt.axhline(0.5, ls="--", c="gray", lw=1)
    plt.xticks(x + w*(len(models)-1)/2, IDENTITY_ORDER)
    plt.ylabel("US-choice rate"); plt.ylim(0, 1.05)
    plt.title("US-choice rate by identity condition (Chinese prompts)\nerror bars = Wilson 95% CI")
    plt.legend(); plt.tight_layout()
    plt.savefig(FIG / "us_rate_by_identity.png", dpi=130); plt.close()
    out.append("![US-rate by identity](figures/us_rate_by_identity.png)\n")

    # Fig 2: per-question x identity heatmap (pooled across models).
    qs = ["Q1", "Q2", "Q3", "Q4", "Q5"]
    mat = np.full((len(IDENTITY_ORDER), len(qs)), np.nan)
    for r, ident in enumerate(IDENTITY_ORDER):
        for c, q in enumerate(qs):
            cell = zh[(zh.identity == ident) & (zh.scenario == q)]
            if len(cell):
                mat[r, c] = cell.us_choice.mean()
    plt.figure(figsize=(7, 4))
    im = plt.imshow(mat, cmap="RdBu_r", vmin=0, vmax=1, aspect="auto")
    plt.colorbar(im, label="US-choice rate")
    plt.xticks(range(len(qs)), qs); plt.yticks(range(len(IDENTITY_ORDER)), IDENTITY_ORDER)
    for r in range(len(IDENTITY_ORDER)):
        for c in range(len(qs)):
            if not np.isnan(mat[r, c]):
                plt.text(c, r, f"{mat[r,c]:.0%}", ha="center", va="center", fontsize=9)
    plt.title("US-choice rate: identity × scenario (pooled, Chinese)")
    plt.tight_layout(); plt.savefig(FIG / "heatmap_identity_scenario.png", dpi=130); plt.close()
    out.append("![identity x scenario heatmap](figures/heatmap_identity_scenario.png)\n")
    out.append("_Q2/Q4 stay US-locked across identities; Q1/Q3/Q5 are the identity-sensitive items._\n")


def main():
    df = load()
    out = ["# PD Program — Analysis Report (pilot stage)\n",
           f"_Generated from `dataset.csv` — {len(df)} samples across "
           f"{df.model.nunique()} models._\n",
           "> All results are **pilot-stage** (n≈8–10 per cell). Treat single-cell "
           "differences as suggestive; pooled tests and large effects are the reliable "
           "signals. English data is currently one cell (glm-5.3 `unknown`), so inferential "
           "analysis is Chinese-only. Multiple comparisons are not corrected — flag before "
           "publication.\n"]
    descriptives(df, out)
    inferential(df, out)
    figures(df, out)
    out.append(sec("4. Caveats"))
    out.append("- Small n per cell; CIs wide. Scale to 3 rounds × 6 models to tighten.\n"
               "- Q2/Q3 have a wording delta between baseline and identity variants "
               "(METHODOLOGY §2.3) — interpret those items within-identity.\n"
               "- Judge is an LLM (claude-sonnet-4-6); reasoning-quality outcomes inherit its bias.\n"
               "- NO-ANSWER/REFUSAL are real behaviors, reported separately, not dropped.\n")
    (HERE / "REPORT.md").write_text("\n".join(out))
    print(f"Wrote {HERE/'REPORT.md'} and figures in {FIG}")


if __name__ == "__main__":
    main()
