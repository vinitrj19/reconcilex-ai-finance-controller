# ReconcileX FastAPI + React Integration Report

## Inspection findings

| Item | Actual source | Finding |
|---|---|---|
| M6 final artifact | `backend/data/dev/m6_final.json` | `dict[str, record]`, 129 records; keys are payment IDs |
| M6 record | same | `payment_id`, `settlement_id`, `status`, `confidence`, `decision_source`, `reason` |
| DEV evaluation | `backend/evaluation/results_dev.json` | JSON object with `dataset`, `full_controller`, `baseline`, `determinism`, `idempotency`, `exceptions`, `regression_tests`, etc. |
| DEV confusion matrix | `backend/evaluation/confusion_matrix_dev.csv` | 8 non-zero expected/predicted rows |
| DEV exception artifact | `backend/evaluation/exceptions_dev.json` | 36 exception records |
| Audit | `backend/audit_log_m6.jsonl` | JSONL; 204 events; payment events keyed by `record_id`; chronological timestamps; stages include normalization, M1, M2, M3 and M6 |
| Pipeline entry point | `backend/scripts/run_m6.py` | Actual verified M1→M6 DEV runner; no `run_m9.py` exists |
| Frontend root | `reconcilex_frontend/` | React/Vite application; `frontend/` is empty |

## Frontend API contract

| Endpoint | Frontend caller | Expected response | Backend source / transformation |
|---|---|---|---|
| `GET /api/v1/health` | `api.getHealth` surface / health route | health object | API-local health response |
| `GET /api/v1/dashboard` | `realApi.getDashboard` | `DashboardResponse` | DEV CSV counts + stored M6/evaluation artifacts; status dict transformed to array |
| `GET /api/v1/reconciliation` | `realApi.getReconciliation` | `ReconciliationListResponse` | M6 dict → ordered list; joined with DEV payment/settlement records; search/status/pagination in adapter |
| `GET /api/v1/reconciliation/{payment_id}` | `realApi.getReconciliationDetail` | `ReconciliationDetailResponse` | DEV source rows + stored M6 decision + audit; candidate evidence generated via existing M3/M4 code for presentation only; no M5 call |
| `GET /api/v1/exceptions` | `realApi.getExceptions` | `ExceptionsResponse` | `evaluation/exceptions_dev.json` metadata + stored M6 decisions + DEV payment data |
| `GET /api/v1/exceptions/{case_id}` | `realApi.getExceptionDetail` | `ExceptionDetailResponse` | Exception item + reconciliation detail; prompts are UI investigation prompts, not fabricated resolutions |
| `GET /api/v1/audit/{payment_id}` | `realApi.getAudit` | `AuditResponse` | `audit_log_m6.jsonl`, filtered by payment `record_id`, sorted chronologically |
| `GET /api/v1/evaluation?dataset=dev` | `realApi.getEvaluation` | `EvaluationResponse` | Existing DEV evaluation and confusion-matrix artifacts |
| `POST /api/v1/runs` | `realApi.runReconciliation` | `RunResponse` | Invokes actual `scripts/run_m6.py`; reloads DEV artifacts; no fake pipeline |

## Money serialization

The reconciliation backend retains `Decimal` internally. The frontend's TypeScript contract requires numeric amounts, so the adapter converts `Decimal` to JSON numbers only at the HTTP boundary. No internal M1–M6 financial calculations were changed.

## Safety

- No M1–M6 protected module was modified.
- No holdout file is read by the API adapter.
- Holdout evaluation requests are rejected with HTTP 403.
- The final package excludes holdout data/artifacts.
- No API keys or credentials were found in the packaged source.
- `VITE_USE_MOCK_API=false` and `VITE_API_BASE_URL=http://localhost:8001/api/v1` are the integrated frontend settings.

## Verification

- Backend/API tests: **153 passed**.
  - 137 pre-existing non-API tests remain green.
  - 16 API integration tests pass.
- Real FastAPI server on port 8001: health, dashboard, reconciliation list, exceptions, evaluation, reconciliation detail, exception detail, audit, and `POST /runs` all returned successful HTTP responses.
- `POST /api/v1/runs` successfully invoked the actual `scripts/run_m6.py` entry point and reloaded the DEV artifacts.
- TypeScript project check: **passed** (`tsc -b`).
- `npm run build` / Vite dev could not be completed in this Linux sandbox because the supplied frontend `node_modules` contains a Darwin-only Rollup optional binary and the sandbox has no network/cache entry for the Linux Rollup package. This is an environment/dependency packaging limitation, not a TypeScript source error; a fresh `npm install` on the target Linux/macOS development machine is required before the final browser/UI verification.
