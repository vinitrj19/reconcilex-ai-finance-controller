<div align="center">

# ⚡ ReconcileX

### AI Finance Controller for Safe, Explainable Payment Reconciliation

**Deterministic where possible. AI where necessary. Policy-controlled always.**

<br>

![Python](https://img.shields.io/badge/Python-Backend-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-Frontend-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-Frontend-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini-AI_Reasoning-4285F4?style=for-the-badge&logo=google&logoColor=white)
![Status](https://img.shields.io/badge/Status-Demo_Ready-success?style=for-the-badge)

<br>

**Razorpay AI Buildathon 2026 • Track 04 — AI Finance Controller**

[🎥 Watch Demo](https://youtu.be/Yxvd2zoMIug) • [🏗️ Architecture](#️-architecture) • [🛡️ Safety](#️-safety-first-design) • [🚀 Run Locally](#-running-locally)

</div>

---

## 💡 The Problem

Payment reconciliation sounds simple:

> **Payment received → order identified → settlement confirmed.**

In reality, the same transaction may appear differently across payment, order and settlement systems.

Teams encounter:

- missing references
- delayed settlements
- duplicate payments
- refunds
- amount differences
- conflicting ownership
- incomplete records
- ambiguous matches

A naïve automated system can create something worse than an unresolved transaction:

> **a confident but incorrect financial match.**

ReconcileX is designed around that risk.

---

## ✨ What is ReconcileX?

**ReconcileX is a multi-source payment reconciliation controller that combines deterministic matching, bounded AI reasoning and a final financial policy layer.**

Instead of asking an LLM to reconcile everything, ReconcileX follows a safer principle:

```text
Rules first → AI only for residual ambiguity → Policy makes the final decision
```

Gemini can **recommend**.

Gemini cannot independently authorize a financial match.

---

## 🔄 How It Works

```text
                    ┌─────────────────────────┐
                    │ Payments • Settlements │
                    │        • Orders        │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │      Normalization      │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ Deterministic Matching  │
                    │         Engine          │
                    └────────────┬────────────┘
                                 │
                         unresolved cases
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │   Candidate + Scoring   │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │   Gemini AI Reasoning   │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │    M6 Policy Control    │
                    └─────────┬───────┬───────┘
                              │       │
                       RESOLVE│       │REVIEW
                              ▼       ▼
                    ┌─────────────────────────┐
                    │       Audit Trail       │
                    └─────────────────────────┘
```

---

## 🧠 Deterministic First. AI Second.

ReconcileX intentionally keeps AI downstream.

### 1️⃣ Normalize

Payments, settlements and orders are converted into comparable representations.

### 2️⃣ Deterministic Resolution

Strong matches are handled through explainable rules rather than sending every transaction to an LLM.

### 3️⃣ Candidate Generation & Scoring

Residual cases receive candidate settlements and evidence scores using signals such as:

| Signal | Purpose |
|---|---|
| 💰 Amount | Compare transaction values |
| 📅 Date | Evaluate temporal compatibility |
| 🔗 Reference | Detect shared identifiers |
| 🧾 Candidate evidence | Preserve explainability |

### 4️⃣ Gemini Reasoning

Only residual ambiguous cases can reach the AI reasoning layer.

Gemini receives bounded evidence and returns a structured recommendation such as:

```json
{
  "decision": "MATCH",
  "selected_candidate_id": "STL_TEST",
  "confidence": 1.0,
  "reasoning": "Payment evidence matches the supplied candidate.",
  "missing_evidence": [],
  "recommended_action": "ACCEPT"
}
```

### 5️⃣ M6 Policy Control

The AI recommendation is **not automatically a financial decision**.

M6 checks safety invariants before a recommendation can become a final result.

---

## 🛡️ Safety-First Design

<div align="center">

### AI PROPOSES. DETERMINISTIC POLICY DECIDES.

</div>

ReconcileX protects against unsafe automation through:

- 🔒 one-settlement-one-owner enforcement
- ♻️ duplicate protection
- ⚔️ collision and conflict checks
- 🎯 confidence requirements
- 🧾 candidate validation
- 🚨 review instead of forced matching
- 📜 auditable decision history
- 🚫 no direct AI-triggered financial action

When evidence is insufficient:

```text
UNKNOWN ≠ MATCH
```

The system escalates the case rather than inventing certainty.

---

## 🖥️ Product Experience

The ReconcileX control center provides:

### 📊 Overview
Operational reconciliation metrics and pipeline status.

### 🔗 Reconciliation
Payment-to-order-to-settlement decisions with evidence.

### ⚠️ Exceptions
Cases requiring investigation or review.

### 📈 Evaluation
Quality and safety-oriented evaluation metrics.

### 📜 Audit
Traceable reconciliation decisions and reasoning history.

For an individual transaction, reviewers can inspect:

```text
Payment
   ↓
Order
   ↓
Settlement
   ↓
Candidate evidence
   ↓
Deterministic score
   ↓
AI reasoning
   ↓
Policy decision
```

This makes the system not merely automated, but **inspectable**.

---

## 📊 Development Demo Snapshot

During the demonstrated development run:

| Metric | Result |
|---|---:|
| 💳 Payments processed | **129** |
| 🏦 Settlements | **111** |
| 🧾 Orders | **120** |
| 🤖 Residual cases reaching AI review | **12** |
| 🛡️ Financial false positives shown by evaluation | **0** |

> These figures describe the included development/demo evaluation and should not be interpreted as production performance guarantees.

---

## 🧩 Example: Why ReconcileX Matters

Suppose a payment of **₹2,776.55** exists.

A settlement candidate also contains:

```text
Amount match     → 100%
Date match       → 100%
Reference match  → 0%
Score            → 0.65
Threshold        → 0.75
```

A simplistic system may decide:

> "The amount and date match, so accept it."

ReconcileX instead asks:

- Is another payment competing for this settlement?
- Is there reference evidence?
- Is the confidence sufficient?
- Would accepting it violate settlement ownership?
- Can the decision be safely justified?

If the evidence cannot arbitrate the conflict:

```text
⚠️ REVIEW REQUIRED
No automatic financial action taken.
```

That behavior is a feature—not a failure.

---

## 🏗️ Architecture

```text
ReconcileX/
│
├── backend/
│   ├── api/
│   ├── src/
│   ├── scripts/
│   ├── tests/
│   ├── config/
│   ├── data/
│   └── evaluation/
│
├── reconcilex_frontend/
│   ├── src/
│   └── ...
│
├── INTEGRATION_REPORT.md
└── README.md
```

### Technology Stack

| Layer | Technology |
|---|---|
| 🎨 Frontend | React + TypeScript |
| ⚙️ Backend | Python |
| 🚀 API | FastAPI |
| 🧠 AI | Google Gemini |
| 🧪 Testing | Pytest |
| 📦 Demo data | File-based development dataset |
| 🛡️ Decision authority | Deterministic M6 policy |

---

## 🤖 Why Gemini?

The AI layer exists for a specific reason:

**deterministic rules are excellent when evidence is explicit, but residual ambiguity sometimes requires contextual reasoning.**

Gemini is therefore used as a bounded reasoning component—not as an autonomous finance controller.

This separation keeps the architecture:

- cheaper
- easier to audit
- easier to test
- safer
- more explainable

---

## 🚀 Running Locally

### Backend

```bash
cd backend

export AI_PROVIDER=gemini
export AI_MODEL=<supported-gemini-model>
export AI_API_KEY=<your-api-key>

uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload
```

Health check:

```bash
curl http://localhost:8001/api/v1/health
```

Expected:

```json
{
  "status": "ok",
  "service": "reconcilex-api",
  "version": "1.0.0"
}
```

### Frontend

Open another terminal:

```bash
cd reconcilex_frontend
npm install
npm run dev
```

Then open the local URL shown by the development server.

> 🔐 Never commit Gemini API keys or other credentials to the repository.

---

## 🧪 Engineering Journey

ReconcileX was not built by simply connecting an LLM to financial records.

The project evolved through several engineering problems:

**Deterministic reconciliation → candidate generation → scoring → AI integration → policy enforcement → evaluation → API integration → dashboard.**

During development, several important failure modes appeared:

- AI provider configuration problems
- model/API compatibility changes
- mocked-provider versus real-provider behavior
- ambiguous settlement ownership
- protected-status policy behavior
- test assumptions changing after provider migration
- frontend/backend integration issues

Those failures influenced the final architecture.

The biggest design lesson was:

> **In financial automation, knowing when not to automate is as important as knowing when to automate.**

---

## 🧪 Testing & Evaluation

The repository contains automated tests covering important reconciliation components and provider behavior.

The evaluation strategy emphasizes more than raw matching accuracy.

Particular attention is given to:

```text
✓ Financial false positives
✓ Settlement ownership
✓ Duplicate protection
✓ Ambiguity preservation
✓ Deterministic behavior
✓ AI schema validation
✓ Failure-safe behavior
```

This reflects the central project objective:

> **maximize useful automation without sacrificing financial safety.**

---

## ⚠️ Current Limitations

ReconcileX is a buildathon prototype, not a production banking platform.

Current limitations include:

- file-based demonstration data
- no live payment processor integration
- no production database
- no enterprise authentication/RBAC
- no real fund movement
- Gemini availability depends on provider/API configuration
- further large-scale evaluation would be required before production use

These boundaries are intentional and clearly separated from the project's demonstrated capabilities.

---

## 🗺️ Roadmap

Future versions could introduce:

- 🔌 live payment/settlement connectors
- 🗄️ production database persistence
- 👥 role-based reviewer workflows
- 📬 exception queues and notifications
- 📊 reconciliation analytics
- 🔁 configurable reconciliation policies
- 🧠 provider abstraction across multiple reasoning models
- 📡 event-driven ingestion
- 🏢 multi-merchant support
- 🔐 enterprise security controls

---

## 🎥 Demo

<div align="center">

### See ReconcileX in action

[![Demo](https://img.shields.io/badge/▶_WATCH_DEMO-ReconcileX-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](YOUR_YOUTUBE_LINK)

</div>

The demo walks through:

**Problem → Architecture → Dashboard → Deterministic matching → Ambiguous case → Gemini reasoning → M6 policy → Auditability**

---

## 🏆 Built For

<div align="center">

### Razorpay AI Buildathon 2026

**Track 04 — AI Finance Controller**

<br>

> Building an AI-assisted finance controller that automates confidently when evidence is strong and escalates safely when it isn't.

</div>

---

## 👨‍💻 Author

<div align="center">

### Vinit Raj

Built with a focus on **financial safety, explainability and practical AI orchestration.**

⭐ If you find ReconcileX interesting, consider starring the repository.

</div>