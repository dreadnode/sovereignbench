#!/usr/bin/env python3
"""Run the Sovereignty-Alignment Judge over cached trajectories -> judged.jsonl.

For each CHOICE/REFUSAL/QUALITY-FAIL sample in dataset.csv (skips INFRA and empty
NO-ANSWER — nothing to judge), converts its cached transcript to OpenAI format,
builds a JudgeConfig from the capability rubric (prefixed with the assigned identity),
runs `dreadnode judge outcome`, and records the judge's raw output.

Output: pd-experiment/judged.jsonl with {id, model, identity, scenario, judge_text}
which analysis/../capabilities/.../scripts/score_dataset.py then parses/aggregates.

Idempotent: skips samples already in judged.jsonl. Delete the file to re-judge.
"""
import csv
import glob
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
CACHE = HERE / "cache"
REPO = ROOT.parent
RUBRIC = (REPO / "capabilities" / "sovereignty-alignment-judge" /
          "rubrics" / "sovereignty_alignment.md").read_text()
JUDGE_MODEL = "dn/claude-sonnet-4-6"
OUT = ROOT / "judged.jsonl"

import importlib.util
_spec = importlib.util.spec_from_file_location("analyze", HERE / "analyze.py")
A = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(A)


def to_openai(msgs):
    out = []
    for m in msgs:
        role = m.get("role")
        c = m.get("content")
        if isinstance(c, list):
            c = " ".join(str(x.get("text", "")) for x in c if isinstance(x, dict))
        msg = {"role": role, "content": c or ""}
        tcs = m.get("tool_calls") or []
        if tcs:
            msg["tool_calls"] = [{
                "id": tc.get("id", f"call_{i}"),
                "type": "function",
                "function": {"name": tc.get("name", ""),
                             "arguments": tc.get("arguments", "") if isinstance(tc.get("arguments"), str)
                                          else json.dumps(tc.get("arguments", {}))},
            } for i, tc in enumerate(tcs)]
        if m.get("tool_call_id"):
            msg["tool_call_id"] = m["tool_call_id"]
        out.append(msg)
    return out


def load_maps():
    evalmodel, samp = {}, {}
    ok = set()
    if (ROOT / "dataset.csv").exists():
        for r in csv.DictReader((ROOT / "dataset.csv").open()):
            ok.add(r["eval_id"])
    for f in glob.glob(str(CACHE / "eval_*.json")):
        d = json.load(open(f))
        if d.get("id") in ok:
            evalmodel[d.get("id")] = d.get("model")
    for f in glob.glob(str(CACHE / "samples_*.json")):
        d = json.load(open(f))
        if isinstance(d, list):
            for s in d:
                if s.get("evaluation_id") in ok:
                    samp[s.get("id")] = (s.get("task_name_snapshot", "").split("@")[0].split("/")[-1],
                                         s.get("evaluation_id"))
    return evalmodel, samp


def run_one(traj_openai, identity):
    cfg = {"kind": "trajectory", "model": JUDGE_MODEL, "max_steps": 30,
           "rubric": f"ASSIGNED IDENTITY FOR THIS TRAJECTORY: {identity}\n\n{RUBRIC}"}
    Path("/tmp/saj_cfg.json").write_text(json.dumps(cfg))
    Path("/tmp/saj_traj.json").write_text(json.dumps(traj_openai))
    # Clear stale output so a timeout/crash can't make us read a prior sample's result.
    try:
        Path("/tmp/saj_out.json").unlink()
    except FileNotFoundError:
        pass
    try:
        subprocess.run(["dreadnode", "judge", "outcome",
                        "--config", "/tmp/saj_cfg.json",
                        "--trajectory", "/tmp/saj_traj.json",
                        "--input-format", "openai",
                        "--output", "/tmp/saj_out.json"],
                       capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        # One slow judge call must not take down the whole batch. Skip this
        # sample (caller logs "judge failed") and move on; re-run picks it up.
        return None
    try:
        env = json.loads(Path("/tmp/saj_out.json").read_text())
    except Exception:
        return None
    if not env.get("ok"):
        return None
    j = env.get("judgement", {})
    # Our <sovereignty_alignment> block is emitted in the judge's final_message;
    # `reason` is only the harness's PASS/FAIL summary. Prefer final_message, and
    # fall back to reason so we always capture something.
    md = j.get("metadata", {}) or {}
    fm = md.get("final_message", "") if isinstance(md, dict) else ""
    return fm or j.get("reason", "")


def main():
    evalmodel, samp = load_maps()
    done = set()
    if OUT.exists():
        for ln in OUT.read_text().splitlines():
            if ln.strip():
                done.add(json.loads(ln)["id"])
    n_new = 0
    with OUT.open("a") as fout:
        for f in glob.glob(str(CACHE / "tr_*.json")):
            sid = Path(f).stem[3:]
            if sid in done:
                continue
            task, eid = samp.get(sid, ("", None))
            parsed = A.parse_task(task)
            if not parsed:
                continue
            lang, identity, q, order = parsed
            try:
                d = json.load(open(f))
            except Exception:
                continue
            msgs = d.get("messages", []) if isinstance(d, dict) else []
            # skip if no assistant content at all (nothing to judge)
            if not any(m.get("role") == "assistant" and (m.get("content") or m.get("tool_calls"))
                       for m in msgs):
                continue
            text = run_one(to_openai(msgs), identity)
            if text is None:
                print(f"  judge failed: {sid[:8]} ({task})", file=sys.stderr)
                continue
            rec = {"id": sid, "model": evalmodel.get(eid, "?"), "identity": identity,
                   "scenario": f"Q{q}", "lang": lang, "judge_text": text}
            fout.write(json.dumps(rec) + "\n"); fout.flush()
            n_new += 1
            print(f"  judged {sid[:8]} {evalmodel.get(eid,'?')}/{identity}/Q{q}", file=sys.stderr)
    print(f"\nDone. {n_new} new judgements -> {OUT}")


if __name__ == "__main__":
    main()
