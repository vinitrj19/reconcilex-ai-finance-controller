# Multi-Source Payment Reconciliation Controller — Product Specification

## 1. Product Definition

An AI-assisted reconciliation controller that matches payment, settlement, and order records across sources, automatically resolves the matches it can prove, explains the ones it can't, and refuses to guess — with every decision traceable and every result measured against a held-out ground truth.

The system is designed for Razorpay Buildathon 2026, Track 04 — AI Finance Controller.

## 2. Primary User

Finance operations / accounts receivable staff at a merchant.

The workflow combines three overlapping sources:
- Payment gateway transactions
- Settlement / bank records
- Internal order records

The system should reduce manual spreadsheet reconciliation and surface only cases that genuinely require human investigation.

## 3. Core Pipeline

MULTI-SOURCE DATA → NORMALIZE → MATCH → VERIFY → EXPLAIN → RESOLVE/ESCALATE → AUDIT → MEASURE

The architecture is deterministic-first:
1. Normalize source records.
2. Apply exact identifier matching.
3. Apply deterministic amount/date/fee rules.
4. Generate candidates for residual cases.
5. Score and rank candidates.
6. Require an explicit confidence threshold and margin.
7. Refuse to guess when evidence is insufficient.
8. Use an LLM only for genuinely ambiguous residual cases in a later milestone.
9. Persist an audit trail.
10. Evaluate against held-out ground truth only after all thresholds are locked.

## 4. Status Taxonomy

| Status | Meaning |
|---|---|
| MATCH | Reliable exact or unambiguous match. |
| PARTIAL_MATCH | Match exists but settlement amount differs by a verified fee/tax deduction. |
| DUPLICATE | Same-source duplicate event with no evidence it is a separate financial event. |
| MISSING | No plausible corresponding record exists in the other source. |
| CONFLICT | Candidate exists but hard evidence disagrees beyond allowed tolerance. |
| AMBIGUOUS / REVIEW_REQUIRED | Multiple plausible candidates exist without a sufficiently clear winner. |
| UNRESOLVED | Evidence is insufficient to safely resolve the record. |
| REFUND | Refund evidence is corroborated by the relevant payment/settlement records. |

Every primary decision must be explainable by a deterministic rule or an explicit scored threshold. The system must never guess.

## 5. Dataset

The synthetic dataset is split into DEV and HOLDOUT.

DEV is used for debugging, rule development, threshold tuning, and evaluation during implementation.
HOLDOUT must remain untouched until the dedicated final evaluation milestone.

DEV contains:
- 120 logical events
- 129 payment rows
- 111 settlement rows
- 120 order rows

Expected DEV event distribution:
- MATCH: 51
- MISSING: 15
- PARTIAL_MATCH: 15
- DUPLICATE: 9
- CONFLICT: 9
- REFUND: 9
- UNRESOLVED: 6
- AMBIGUOUS: 6

The extra payment rows arise because duplicate events create additional source rows.

## 6. Financial Rules

Fee-adjusted settlement modeling:
- Fee rate: 1.5%–3.0% of gross payment.
- GST: 18% of the fee.
- Maximum effective deduction: 3.54% of gross.

Use Decimal for all monetary comparisons. Do not rely on floating-point equality.

A normal explainable deduction may be classified as PARTIAL_MATCH.
A discrepancy outside the defined fee/tax band should not be silently accepted.

## 7. M2 — Deterministic Reconciliation

M2 owns deterministic reconciliation rules.

Critical ordering:
1. Duplicate detection must happen before declaring MISSING.
2. Exact reliable identifiers should be preferred.
3. Fee/tax deductions must be explicitly verified.
4. Refunds require corroborating evidence.
5. Orphan/unresolved foreign keys must not crash the pipeline.
6. Ambiguous records must not be arbitrarily paired.

Every payment row must receive exactly one primary status.

## 8. M3 — Candidate Generation

M3 only generates plausible payment → settlement candidate pairs.

M3 must NOT:
- choose a winner
- assign final status
- apply acceptance thresholds
- call an LLM

Candidate generation can use:
- currency compatibility
- date windows
- amount/tolerance plausibility
- payment/order/invoice/reference signals
- fee-band plausibility
- stable deterministic ordering
- a top-K candidate limit

Candidate recall should be measured on DEV after implementation.

## 9. M4 — Candidate Scoring and Threshold Locking

M4 owns:
- deterministic candidate scoring
- candidate ranking
- acceptance threshold
- minimum score margin
- DEV-only threshold sweep
- locked versioned configuration

M4 must not silently reimplement M2.

If two candidates are too close, route to REVIEW_REQUIRED / AMBIGUOUS.
If the same settlement is proposed for multiple payments, the one-to-one assignment conflict must be handled explicitly by the reconciliation policy rather than hidden inside the scoring formula.

Thresholds must be tuned on DEV and locked before HOLDOUT evaluation.

## 10. M5 — AI Boundary

M5 will introduce LLM reasoning only for genuine ambiguous residual cases.

The LLM must receive structured evidence and return structured output.

The LLM must never:
- override deterministic hard conflicts
- invent transaction identifiers
- invent missing evidence
- execute irreversible financial actions

The policy layer remains the final authority.

## 11. Evaluation

Required metrics:
- Match rate
- Unresolved exception list
- Precision
- Recall
- False-positive rate
- Review / unresolved rate
- Deterministic-resolution rate
- AI invocation rate
- Throughput
- Comparison against a simple baseline

For ambiguous ground-truth cases, REVIEW_REQUIRED / AMBIGUOUS is considered the correct safe behavior when no unique pairing can be proven.

Threshold tuning must use DEV only.
HOLDOUT is loaded only once for final scoring after the pipeline and configuration are frozen.

## 12. Auditability

Every important decision should record:
- payment identifier
- settlement identifier when available
- stage
- rule / evidence used
- score when applicable
- threshold when applicable
- decision
- timestamp
- reason / explanation

Audit records should make it possible to answer why a transaction was matched, rejected, or escalated.

## 13. Architecture

Planned architecture:

React / simple web UI → FastAPI → normalization → deterministic reconciliation → candidate generation → scoring/policy → optional LLM reasoning → PostgreSQL/audit store → evaluation dashboard

The backend remains the authority for financial decisions.

## 14. Engineering Principles

- Deterministic first, AI second.
- Explainability over cleverness.
- Abstention is a valid outcome.
- Never optimize solely for match rate.
- Never use the HOLDOUT set to tune rules.
- Keep thresholds versioned.
- Keep financial calculations precise.
- Make every pipeline stage independently testable.
- Prefer reproducible batch evaluation over cherry-picked examples.
