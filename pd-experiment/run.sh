#!/usr/bin/env bash
#
# run.sh — reproducible launcher for the Prisoner's-Dilemma geopolitical eval program.
#
# Everything the experiment needs is a set of task-sets already published to the
# dreadnode registry (see `push`). Evals reference registry task-sets, NOT local
# folders, so you can run this from anywhere once the task-sets exist.
#
# USAGE:
#   ./run.sh push                 # (re)publish all local tasks + task-sets to the registry
#   ./run.sh pilot <model>        # 1 round of all English identity conditions (4 evals)
#   ./run.sh pilot-zh <model>     # 1 round of all Chinese identity conditions (4 evals)
#   ./run.sh scale <model> <R>    # R rounds of English identity conditions (4*R evals)
#   ./run.sh scale-zh <model> <R> # R rounds of Chinese identity conditions (4*R evals)
#   ./run.sh status               # show status of every eval logged in runs/
#
# All evals run at CONCURRENCY 1 (one sandbox at a time) — this is deliberate.
# Launching many evals in parallel overloaded the sandbox provider and produced
# infra_error/timeout failures (see METHODOLOGY.md §5.2). Slow and steady.
#
set -euo pipefail
cd "$(dirname "$0")"

ORG="dreadnode"
CONCURRENCY=1
TIMEOUT=600
MAX_STEPS=30
RUNS_DIR="runs"
mkdir -p "$RUNS_DIR"

# Identity conditions -> registry task-set names.
# Portable (works on macOS bash 3.2, which lacks `declare -A`): a condition maps
# to a task-set via a helper function. English gen2 baseline is reused for the
# English `unknown` cell; gen3 for us/cn/un; gen3b (zh-*) for all Chinese cells.
COND_ORDER="unknown us cn un"

set_for() {  # <lang> <cond> -> task-set name
  local lang="$1" cond="$2"
  if [ "$lang" = zh ]; then
    case "$cond" in
      unknown) echo "prisoners-choice-zh-unknown-set" ;;
      us)      echo "prisoners-choice-zh-us-set" ;;
      cn)      echo "prisoners-choice-zh-cn-set" ;;
      un)      echo "prisoners-choice-zh-un-set" ;;
    esac
  else
    case "$cond" in
      unknown) echo "prisoners-choice-set" ;;
      us)      echo "prisoners-choice-us-set" ;;
      cn)      echo "prisoners-choice-cn-set" ;;
      un)      echo "prisoners-choice-un-set" ;;
    esac
  fi
}

slug() { echo "$1" | tr './' '--' | tr -cd 'a-zA-Z0-9-'; }

push_all() {
  echo ">> Pushing all tasks + task-sets to $ORG registry..."
  for t in tasks/gen1-dilemma/*/ tasks/gen2-choice/*/ \
           tasks/gen3-identity/prisoners-choice-*-q*/ \
           tasks/gen3b-language/prisoners-choice-*-q*/; do
    [ -f "$t/task.yaml" ] && dreadnode task push "$t" >/dev/null 2>&1 && echo "  task  $(basename "$t")"
  done
  for s in tasks/gen1-dilemma/prisoners-dilemma-set \
           tasks/gen2-choice/prisoners-choice-set \
           tasks/gen3-identity/prisoners-choice-*-set \
           tasks/gen3b-language/prisoners-choice-*-set; do
    [ -f "$s/task-set.yaml" ] && dreadnode task-set push "$s" >/dev/null 2>&1 && echo "  set   $(basename "$s")"
  done
  echo ">> Push complete."
}

# launch_one <eval-name> <task-set-name> <model> <logfile>
launch_one() {
  local name="$1" set="$2" model="$3" log="$4"
  echo ">> Launching $name  (task-set: $set, model: $model, conc: $CONCURRENCY)"
  local out
  out=$(dreadnode evaluation create \
    --name "$name" \
    --task-set "$ORG/$set" \
    --model "$model" \
    --concurrency "$CONCURRENCY" \
    --task-timeout-sec "$TIMEOUT" \
    --max-steps "$MAX_STEPS" 2>&1)
  local id
  id=$(echo "$out" | grep -oE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' | head -1)
  echo "$name -> $set -> ${id:-LAUNCH_FAILED}" | tee -a "$log"
  [ -z "$id" ] && { echo "!! launch failed:"; echo "$out"; return 1; }
  # Poll to terminal so evals run strictly one at a time (never overlap sandboxes).
  echo -n "   waiting for terminal state"
  while true; do
    sleep 30
    local st
    st=$(dreadnode evaluation get "$id" --json 2>/dev/null | python3 -c "import sys,json;print(json.load(sys.stdin).get('job_status',''))" 2>/dev/null || echo "")
    case "$st" in
      completed|partial|failed|cancelled) echo " -> $st"; break ;;
      *) echo -n "." ;;
    esac
  done
}

run_matrix() {  # <lang> <model> <rounds>
  local lang="$1" model="$2" rounds="$3"
  local prefix; prefix=$([ "$lang" = zh ] && echo "zhpd" || echo "idpd2")
  local mslug; mslug=$(slug "${model#dn/}")
  local log; log="$RUNS_DIR/${prefix}-${mslug}-$(date +%Y%m%d-%H%M%S).log"
  echo ">> Run matrix: lang=$lang model=$model rounds=$rounds -> $log"
  for r in $(seq 1 "$rounds"); do
    for cond in $COND_ORDER; do
      launch_one "${prefix}-${cond}-${mslug}-r${r}" "$(set_for "$lang" "$cond")" "$model" "$log"
    done
  done
  echo ">> Done. Eval IDs logged in $log"
  echo ">> Analyze with: python3 analysis/analyze.py $log"
}

status_all() {
  for log in "$RUNS_DIR"/*.log; do
    [ -f "$log" ] || continue
    echo "== $log =="
    grep -oE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' "$log" | while read -r id; do
      dreadnode evaluation get "$id" --json 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin); ic=d.get('item_counts') or {}
print(f\"  {d.get('name'):34s} {str(d.get('job_status')):10s} passed={ic.get('passed',0)} failed={ic.get('failed',0)} infra={ic.get('infra_error',0)}\")
" 2>/dev/null || echo "  $id (unreadable)"
    done
  done
}

cmd="${1:-help}"
case "$cmd" in
  push)      push_all ;;
  pilot)     run_matrix en "${2:?model required, e.g. dn/glm-5.3}" 1 ;;
  pilot-zh)  run_matrix zh "${2:?model required}" 1 ;;
  scale)     run_matrix en "${2:?model required}" "${3:?rounds required}" ;;
  scale-zh)  run_matrix zh "${2:?model required}" "${3:?rounds required}" ;;
  status)    status_all ;;
  *) sed -n '2,30p' "$0" ;;
esac
