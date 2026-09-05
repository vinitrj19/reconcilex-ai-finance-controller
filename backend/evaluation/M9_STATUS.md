# M9 Status (interim - work preserved mid-task, not complete)

This snapshot was packaged early, on explicit instruction, to preserve work
before credits ran out. It is NOT a completed M9. Do not read this zip as
containing final holdout results.

## Done and verified at packaging time
- Root cause of the M8 M5 defect diagnosed and documented (see the
  docstring at the top of src/m5_provider.py and src/m5_reasoning.py):
  `try_load_m5_engine()` hardcoded `MockProvider()` with no response,
  which made `AIDecision(**None)` raise on every call, always ESCALATE.
- Fix implemented: src/m5_provider.py (ReasoningProvider ABC,
  RealLLMProvider, MockProvider with a loud failure instead of a silent
  one, FailingProvider, build_provider() env-based DI factory) and
  src/m5_reasoning.py (same external contract, richer leak-free evidence
  payload). Minimal, documented change to scripts/run_m6.py::
  try_load_m5_engine() to call build_provider() instead of hardcoding.
- M1-M4/M6 core files confirmed byte-identical before/after the fix:
  see evaluation/m9_pre_change_freeze_hashes.json (hashes taken
  immediately before any M9 code change) - re-hash the same 17 files
  listed there against the current src//config/ to reproduce this check.
- DEV pipeline re-run after the fix: data/dev/m6_final.json is
  byte-identical to the original M8-shipped copy (verified by diff during
  the session; not re-verified again after this point per the "no further
  runs" instruction).
- Test suite: 137 passed, 0 failed at packaging time (102 pre-existing
  M8 tests + 35 new: tests/test_m5_provider.py, tests/test_m5_integration.py).
  Run `python3 -m pytest tests/ -q` from the project root to reproduce.
  Note: this environment has real `pydantic` and `pytest` installed (both
  fetched from PyPI, which this sandbox can reach) - the M8-era comments
  claiming "not installed, no network access" are stale for this
  environment; they are left in place where they document historical
  context and only edited where they were factually load-bearing.

## Explicitly NOT done - remaining M9 work
- scripts/run_m9.py (holdout evaluation runner) was NOT created before
  this stop instruction. It does not exist in this package.
- HOLDOUT was NOT run under M9. No new holdout predictions, no
  evaluation/results_m9.json, confusion_matrix_m9.csv, exceptions_m9.json,
  report_m9.md, m8_vs_m9.json/.md were generated.
- No live LLM call was ever made (no AI_API_KEY is configured in this
  sandbox; build_provider() returns None, exactly as designed - see
  src/m5_provider.py).
- M9_CHANGELOG.md, section 18's missing-settlement investigation, and the
  final formatted M9 report were not produced.
- evaluation/m8_integrity_manifest.json (from M8) is included for
  reference/comparison only - it was not regenerated or extended for M9.

## To resume
1. Re-verify the freeze (hash the 17 files in
   evaluation/m9_pre_change_freeze_hashes.json again) before doing
   anything else.
2. Re-run `python3 -m pytest tests/ -q` and `python3 scripts/run_m6.py`
   to reconfirm the dev regression (`data/dev/m6_final.json` byte-identical
   to the M8 copy) before touching holdout.
3. Write scripts/run_m9.py following the same freeze-then-predict-then-
   score protocol scripts/run_m8.py already uses (predictions frozen to
   evaluation/predictions_holdout.json-equivalent BEFORE
   ground_truth/holdout/ground_truth_holdout.json is opened).
4. Only then run the one-time HOLDOUT evaluation.
