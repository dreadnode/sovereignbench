#!/usr/bin/env python3
"""Layer 0 — build the tidy per-sample dataset for the whole PD program.

Scans every runs/*.log (and *.txt), pulls each eval's samples + transcripts + judge
results, classifies each sample (reusing analyze.py's logic), and emits one
long-format row per sample to analysis/dataset.csv.

Transcripts and judge results are cached under analysis/cache/ so re-runs are fast
and offline. Delete the cache to force a refresh.

Row schema:
  eval_id, eval_name, model, lab, lang, identity, scenario, order, round,
  status, outcome_class, side, judge_pass, steps, tool_calls, msg_count
"""
import csv
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
CACHE = HERE / "cache"
CACHE.mkdir(exist_ok=True)
RUNS = ROOT / "runs"

# reuse the classifier + parsers from analyze.py
import importlib.util
_spec = importlib.util.spec_from_file_location("analyze", HERE / "analyze.py")
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)

LAB = {  # model -> originating lab
    "dn/glm-5.3": "Zhipu", "dn/glm-5.2": "Zhipu",
    "dn/deepseek-v4-pro": "DeepSeek", "dn/deepseek-v4-flash": "DeepSeek",
    "dn/qwen3.8-max": "Alibaba", "dn/kimi-k3": "Moonshot",
    "dn/llama-4-scout-17b-16e-instruct": "Meta", "dn/llama-3.3-70b-instruct": "Meta",
}


def cli(args, timeout=120):
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    return r.stdout if r.returncode == 0 else ""


def cached(key, fetch):
    """Return JSON for `key`, fetching + caching on miss. None cached as {}."""
    f = CACHE / f"{key}.json"
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            pass
    val = fetch()
    f.write_text(json.dumps(val) if val is not None else "{}")
    return val or {}


# Cancelled / superseded runs to skip entirely (all-INFRA, excluded from analysis).
SKIP_LOGS = {
    "idpd-cancelled-gen3-v1.txt",
    "en-balance.raw.txt",  # messy pre-dedup EN log; superseded by en-balance-final.log
}


def load_all_runs():
    """Yield (eval_name, eval_id) from every run log, de-duped by eval_id."""
    seen = set()
    logs = [p for p in (list(RUNS.glob("*.log")) + list(RUNS.glob("*.txt")))
            if p.name not in SKIP_LOGS]
    for log in sorted(logs):
        for ln in log.read_text().splitlines():
            if "->" not in ln:
                continue
            parts = [p.strip() for p in ln.split("->")]
            eid = parts[-1]
            name = parts[-2] if len(parts) >= 2 else parts[0]
            if len(eid) >= 20 and eid not in seen:
                seen.add(eid)
                yield name, eid


def eval_meta(eid):
    d = cached(f"eval_{eid}", lambda: json.loads(cli(
        ["dreadnode", "evaluation", "get", eid, "--json"]) or "{}"))
    return d


def eval_samples(eid):
    return cached(f"samples_{eid}", lambda: json.loads(cli(
        ["dreadnode", "evaluation", "list-samples", eid, "--json"]) or "[]"))


def transcript(eid, sid):
    return cached(f"tr_{sid}", lambda: json.loads(cli(
        ["dreadnode", "evaluation", "get-transcript", f"{eid}/{sid}"]) or "{}"))


def sample_detail(eid, sid):
    """Cached full get-sample; return (result_json, error_str)."""
    d = cached(f"det_{sid}", lambda: json.loads(cli(
        ["dreadnode", "evaluation", "get-sample", f"{eid}/{sid}", "--json"]) or "{}"))
    return (d.get("result_json") or {}), str(d.get("error") or "")


def main():
    rows = []
    for name, eid in load_all_runs():
        meta = eval_meta(eid)
        model = meta.get("model") or "?"
        rnd = "r1"
        for tok in name.replace("-", " ").split():
            if tok and tok[0] == "r" and tok[1:].isdigit():
                rnd = tok
        samples = eval_samples(eid)
        if not isinstance(samples, list):
            continue
        for s in samples:
            task = (s.get("task_name_snapshot") or "").split("@")[0].split("/")[-1]
            parsed = A.parse_task(task)
            if not parsed:
                continue
            lang, identity, q, order = parsed
            status = s.get("item_status")
            if status not in ("passed", "failed", "errored", "infra_error", "timed_out"):
                continue
            us_kw, cn_kw = A.KEYWORDS[q]
            tr = transcript(eid, s["id"])
            if status != "passed":
                rj, serr = sample_detail(eid, s["id"])
            else:
                rj, serr = {}, ""
            cls, side = A.classify_sample(status, rj, tr, us_kw, cn_kw, sample_error=serr)
            j = (rj or {}).get("judgement") or {}
            m = j.get("metrics") or {}
            sess = (tr or {}).get("session", {}) if tr else {}
            rows.append({
                "eval_id": eid, "eval_name": name, "model": model,
                "lab": LAB.get(model, "?"), "lang": lang, "identity": identity,
                "scenario": f"Q{q}", "order": order, "round": rnd,
                "status": status, "outcome_class": cls,
                "side": side or "", "judge_pass": int(status == "passed"),
                "steps": m.get("steps_used", ""), "tool_calls": m.get("tool_calls", ""),
                "msg_count": sess.get("message_count", ""),
            })
        print(f"  scanned {name} ({len(samples)} samples)", file=sys.stderr)

    out = ROOT / "dataset.csv"
    cols = ["eval_id", "eval_name", "model", "lab", "lang", "identity", "scenario",
            "order", "round", "status", "outcome_class", "side", "judge_pass",
            "steps", "tool_calls", "msg_count"]
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {len(rows)} rows -> {out}")
    # quick sanity summary
    from collections import Counter
    by = Counter((r["model"], r["lang"], r["identity"]) for r in rows)
    print("cells (model,lang,identity): n samples")
    for k in sorted(by):
        print(f"  {k}: {by[k]}")


if __name__ == "__main__":
    main()
