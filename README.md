# ReconcileX — AI Finance Controller

> AI-assisted payment reconciliation with deterministic-first matching, bounded Gemini reasoning, policy-controlled decisions, and an auditable exception path.

**Razorpay AI Buildathon 2026 · Track 04 — AI Finance Controller**

## 1. Problem

Payment reconciliation becomes difficult when the same financial event appears differently across systems.

A payment gateway records the payment, an order system records the order, and a settlement system records what reaches the business. Amounts can differ because of fees; dates can shift; references can change; records can be duplicated or missing.

The core question is:

> **Do these records actually describe the same financial event?**

ReconcileX answers that question across a batch while avoiding unsafe forced matches.

## 2. What ReconcileX Does

ReconcileX takes three sources:

- Payments
- Settlements
- Orders

The controller:

1. Normalizes records into a common internal representation.
2. Performs deterministic reconciliation first.
3. Generates bounded candidates for unresolved cases.
4. Scores candidates using amount, date, and reference evidence.
5. Sends only residual ambiguity to Gemini AI.
6. Validates AI recommendations through M6 Policy Control.
7. Resolves safe cases or escalates uncertain cases to review.
8. Records decisions and evidence in an audit trail.
9. Evaluates the controller on development and held-out synthetic data.

### Core principle

> **AI proposes. Deterministic policy decides.**

The LLM is never treated as the final financial authority.

## 3. Architecture

```text
                 ┌───────────────────┐
                 │ Payments          │
                 │ Settlements       │
                 │ Orders            │
                 └─────────┬─────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │   Normalization   │
                 └─────────┬─────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │ Deterministic     │
                 │ Matching Engine   │
                 └─────────┬─────────┘
                           │
                     unresolved cases
                           │
                           ▼
                 ┌───────────────────┐
                 │ Candidate + Score │
                 └─────────┬─────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │ Gemini AI         │
                 │ Reasoning         │
                 └─────────┬─────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │ M6 Policy Control │
                 └──────┬─────┬──────┘
                        │     │
                 RESOLVE│     │REVIEW
                        ▼     ▼
                 ┌───────────────────┐
                 │   Audit Trail     │
                 └───────────────────┘
```

## 4. Why Deterministic-First?

Known financial patterns can be handled more cheaply, consistently, and explainably with rules:

- Exact identifier matches
- Date shifts
- Fee-adjusted settlements
- Refunds
- Partial settlements
- Duplicate records
- Missing payment / settlement records

Only genuinely ambiguous residual cases reach AI.

## 5. AI and Financial Safety

Gemini receives structured evidence and returns a recommendation such as:

```json
{
  "decision": "MATCH",
  "selected_candidate_id": "STL_00091",
  "confidence": 0.91,
  "reasoning": "The payment and candidate settlement agree on the available evidence.",
  "missing_evidence": [],
  "recommended_action": "ACCEPT"
}
```

M6 then validates the recommendation before acceptance.

Safety controls include:

- One settlement can have at most one owner.
- Duplicate payments cannot claim a settlement.
- Deterministic decisions are protected from unsafe AI overrides.
- AI MATCH decisions must reference an existing candidate.
- Low-confidence or invalid AI responses fail safely.
- Candidate collisions are resolved deterministically.
- Ambiguous cases can remain in review.
- AI recommendations are not the final authority.
- Decisions are auditable.
- Re-running the pipeline is designed to be idempotent.

> **If evidence is insufficient, review is safer than a forced financial match.**

## 6. Evaluation Dataset

The build uses synthetic reconciliation data.

| Split | Events | Purpose |
|---|---:|---|
| Development | 120 | Tuning, development and debugging |
| Held-out | 80 | Final evaluation snapshot |
| **Total** | **200** | |

Scenarios include:

- Exact match
- Date shift
- Fee-adjusted settlement
- Duplicate
- Missing settlement
- Missing payment
- Refund
- Partial settlement
- Ambiguous cases
- Unrelated records

The held-out set is kept separate from development tuning.

## 7. Evaluation Snapshot

| Metric | Result |
|---|---:|
| Held-out event-level correctness | **96.25%** |
| Financial false positives | **0** |
| Development safe automation | **86.0%** |

These are results for the current synthetic-data prototype, not production financial accuracy.

> **The goal is not maximum automation. It is maximum safe automation.**

## 8. Engineering Journey

ReconcileX evolved through failure.

### Exact matching
Good for clean records, but too brittle for messy reconciliation patterns.

### Deterministic rules
Added handling for dates, fees, refunds, duplicates, partial settlements and missing records.

### Candidate generation and scoring
Created bounded candidate sets and scored them using financial evidence.

### AI reasoning
Gemini was introduced only for residual ambiguity.

### Policy control
Real provider integration exposed failures that mocks could hide. This led to structured outputs, safe provider failure, confidence thresholds, ownership checks, collision handling and a hard boundary between AI recommendation and financial decision.

**The failures became part of the architecture.**

## 9. Tech Stack

### Backend
- Python
- FastAPI
- Pandas
- Pydantic
- RapidFuzz / similarity scoring
- Decimal-based financial calculations

### AI
- Google Gemini
- Structured model output
- Provider abstraction
- Mock and failing providers

### Frontend
- React
- TypeScript
- Tailwind CSS
- shadcn/ui
- Lucide icons
- Recharts

### Production direction
- PostgreSQL persistence
- Real provider connectors
- Asynchronous processing

## 10. Product Interface

### Overview
Reconciliation metrics, pipeline stages and status distribution.

### Reconciliation
Transaction-level decisions, candidates, scores and decision source.

### Exceptions
Cases requiring human review instead of unsafe automatic resolution.

### Evaluation
Development and held-out evaluation metrics.

### Audit
Decision provenance and audit information.

## 11. Decision States

The controller represents outcomes including:

`MATCH` · `PARTIAL_MATCH` · `REFUND` · `DUPLICATE` · `MISSING` · `CONFLICT` · `AMBIGUOUS` · `UNRESOLVED`

The system does not force every payment into MATCH.

## 12. Repository Structure

```text
ReconcileX/
├── backend/
│   ├── api/
│   ├── scripts/
│   ├── src/
│   │   ├── normalization/
│   │   ├── matching/
│   │   ├── m5_provider.py
│   │   └── policy.py
│   ├── tests/
│   └── synthetic_data/
├── reconcilex_frontend/
│   ├── src/
│   └── ...
├── README.md
└── ...
```

## 13. Run Locally

### Backend

```bash
cd backend

export AI_PROVIDER=gemini
export AI_MODEL=gemini-3.6-flash
export AI_API_KEY="YOUR_GEMINI_API_KEY"

python3 -m uvicorn api.main:app --reload --port 8001
```

### Frontend

```bash
cd reconcilex_frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

The frontend uses:

```text
http://localhost:8001/api/v1
```

**Never commit an API key.** Keep secrets in environment variables or a local `.env` excluded by `.gitignore`.

## 14. Demo Video

Upload the final video to **YouTube as Unlisted** (recommended) or Google Drive with viewer access.

Then replace this line:

```text
[Watch the ReconcileX Demo](https://youtu.be/Yxvd2zoMIug)
```

with the actual video link.

For the Razorpay submission portal, paste the same video URL into the **video/demo submission field** if the portal asks for a link.

## 15. What Makes ReconcileX Different?

1. **Deterministic-first architecture** — AI is not used where explicit financial rules are sufficient.
2. **Bounded AI** — Gemini receives residual ambiguous cases with bounded candidates.
3. **Policy-controlled AI** — the LLM recommends; deterministic policy decides.
4. **Explicit uncertainty** — unresolved cases remain visible.
5. **Financial safety invariants** — ownership, duplicate protection, collisions and confidence thresholds are enforced outside the model.
6. **Evaluation discipline** — development tuning is separated from held-out evaluation.
7. **Auditability** — decisions can be traced to source, evidence and reasoning.

## 16. Current Limitations

This is a buildathon prototype, not a production finance platform.

- Synthetic rather than live production data
- Prototype-level payment and settlement connectors
- Human review is not yet a full operational queue
- AI introduces latency and cost
- Production authentication, observability and deployment hardening remain
- Evaluation results should not be interpreted as production accuracy

## 17. Roadmap

1. Integrate real payment and settlement providers.
2. Add durable PostgreSQL persistence.
3. Add asynchronous reconciliation jobs.
4. Cache and batch AI requests where appropriate.
5. Build a complete finance-team review workflow.
6. Add production authentication and observability.
7. Learn from resolved exceptions while preserving deterministic financial controls.

The long-term goal is not to replace finance teams with AI.

It is to give them a controller that:

> **automates what can be proven, reasons about what is ambiguous, and makes uncertainty visible.**

## 18. Buildathon Context

**Event:** Razorpay AI Buildathon 2026  
**Track:** Track 04 — AI Finance Controller  
**Project:** ReconcileX  
**Focus:** Multi-source payment reconciliation with deterministic-first resolution and policy-controlled AI reasoning.

## 19. Final Takeaway

> **Use rules for what can be proven. Use AI for what requires judgment. Use policy to control the financial decision.**

ReconcileX is designed around that separation to make reconciliation safer, more explainable and more auditable.
