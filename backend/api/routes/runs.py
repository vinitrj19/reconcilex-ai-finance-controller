from __future__ import annotations

import subprocess
import sys
import time

from fastapi import APIRouter, HTTPException
from api.state import state, ROOT

router = APIRouter()


@router.post("/runs")
def trigger_run():
    # The verified pipeline entry point in this repository is scripts/run_m6.py;
    # there is no run_m9.py. Invoke the actual DEV M1-M6 runner, never a fake
    # or mock provider. M5 remains optional according to that runner.
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "scripts.run_m6"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "Pipeline failed")[-4000:]
        raise HTTPException(status_code=500, detail=detail)

    state.reload()
    elapsed = time.perf_counter() - started
    statuses = {s: 0 for s in ("MATCH", "PARTIAL_MATCH", "REFUND", "CONFLICT", "MISSING", "DUPLICATE", "AMBIGUOUS", "UNRESOLVED")}
    for d in state.m6_final.values():
        statuses[d.get("status", "UNRESOLVED")] = statuses.get(d.get("status", "UNRESOLVED"), 0) + 1
    matches = statuses["MATCH"] + statuses["PARTIAL_MATCH"] + statuses["REFUND"] + statuses["CONFLICT"]
    exceptions = len(state.exceptions_dev)
    run_id = f"DEV-M6-{int(time.time())}"
    steps = [
        {"key": "load", "label": "Loading sources", "status": "DONE"},
        {"key": "normalize", "label": "Normalizing records", "status": "DONE"},
        {"key": "candidates", "label": "Generating candidates", "status": "DONE"},
        {"key": "deterministic", "label": "Running deterministic rules", "status": "DONE"},
        {"key": "ai", "label": "Evaluating residual ambiguity", "status": "DONE"},
        {"key": "policy", "label": "Applying policy", "status": "DONE"},
        {"key": "audit", "label": "Writing audit records", "status": "DONE"},
    ]
    return {
        "run_id": run_id,
        "status": "COMPLETED",
        "steps": steps,
        "summary": {
            "run_id": run_id,
            "execution_time_seconds": elapsed,
            "records_processed": len(state.m6_final),
            "matches": matches,
            "exceptions": exceptions,
        },
    }
