#!/usr/bin/env bash
# Durable English-balancing orchestrator. Idempotent: skips (model,cond) cells whose
# eval already appears completed/partial in runs/en-balance.log. Launches remaining
# cells ONE AT A TIME at concurrency 1, waiting for each to reach terminal before the next.
# Safe to re-run if it dies — it resumes from the log.
set -uo pipefail
cd "$(dirname "$0")" || exit 1
LOG="runs/en-balance.log"; touch "$LOG"

setname() { case "$1" in
  unknown) echo prisoners-choice-set;; us) echo prisoners-choice-us-set;;
  cn) echo prisoners-choice-cn-set;; un) echo prisoners-choice-un-set;; esac; }

terminal() {  # returns 0 if eval id is in a terminal state
  local st; st=$(dreadnode evaluation get "$1" --json 2>/dev/null | \
    python3 -c "import sys,json;print(json.load(sys.stdin).get('job_status',''))" 2>/dev/null)
  case "$st" in completed|partial|failed|cancelled) return 0;; *) return 1;; esac
}

already_launched() { grep -q "^$1 " "$LOG"; }

for spec in "glm-5-3:dn/glm-5.3" "deepseek-v4-pro:dn/deepseek-v4-pro" "qwen3-8-max:dn/qwen3.8-max"; do
  mslug=${spec%%:*}; model=${spec##*:}
  for cond in unknown us cn un; do
    name="enpd-${cond}-${mslug}-r1"
    if already_launched "$name"; then
      # wait for the already-launched one to finish before proceeding
      id=$(grep "^$name " "$LOG" | awk -F' -> ' '{print $3}' | tail -1)
      if [ -n "$id" ]; then
        until terminal "$id"; do sleep 30; done
      fi
      continue
    fi
    out=$(dreadnode evaluation create --name "$name" --task-set "dreadnode/$(setname "$cond")" \
      --model "$model" --concurrency 1 --task-timeout-sec 600 --max-steps 30 2>&1)
    id=$(echo "$out" | grep -oE "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}" | head -1)
    echo "$name -> $(setname "$cond") -> ${id:-FAILED}" >> "$LOG"
    if [ -z "$id" ]; then echo "LAUNCH FAILED $name" >> /tmp/en_balance2.log; continue; fi
    echo "launched $name = $id" >> /tmp/en_balance2.log
    until terminal "$id"; do sleep 30; done
    echo "$name terminal" >> /tmp/en_balance2.log
  done
done
echo "EN BALANCE COMPLETE" >> /tmp/en_balance2.log
