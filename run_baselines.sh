#!/bin/bash
#SBATCH -J miplib_main
#SBATCH -p mit_normal
#SBATCH --exclude=node[1620-1625],node[2502-2513],node[2704-2705]
#SBATCH --array=0-4
#SBATCH -c 1
#SBATCH --mem=16G
#SBATCH -t 12:00:00
#SBATCH -o slurm_logs/%x_%a_%A.out

# One array task per baseline. Resubmitting continues unfinished baselines; finished runs are skipped.
STRATS=(backend none gmi cover gmi+cover)
S=${STRATS[$SLURM_ARRAY_TASK_ID]}
cd ~/15.c57-final-project
OUT=results/by_strategy/$S

PREV=$(ls -d $OUT/miplib_main/*/ 2>/dev/null | tail -1)
RESUME=""; [ -n "$PREV" ] && RESUME="--resume $PREV"

# Runs that ended in an error (for example a license failure) count as finished on resume; drop them so they rerun
if [ -n "$PREV" ] && grep -q '"status": "error"' $PREV/runs.jsonl 2>/dev/null; then
    cp $PREV/runs.jsonl $PREV/runs.jsonl.bak.$SLURM_JOB_ID
    grep -v '"status": "error"' $PREV/runs.jsonl.bak.$SLURM_JOB_ID > $PREV/runs.jsonl
fi

echo "strategy=$S node=$(hostname) cpu=$(lscpu | grep 'Model name' | sed 's/.*: *//') resume=$PREV"
.venv/bin/python -u run.py --results $OUT bench configs/miplib_main.toml --only "$S" $RESUME
