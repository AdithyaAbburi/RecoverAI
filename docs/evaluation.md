# RecoverAI: Evaluation & Benchmark Methodology

This document outlines the evaluation framework, metrics definition, and experimental setup for comparing **RecoverAI** against baseline and static rules recovery mechanisms.

---

## 1. Objectives

The primary goal of RecoverAI is to maximize the net revenue recovered from failed payment transactions while maintaining strict compliance with safety policies, attempt limits, and customer communication preferences.

---

## 2. Experimental Setup

### A. Dataset
Evaluation is conducted on a canonical batch of **1,000 synthetic transaction records** representing real-world payment failure distributions:
- **High-Value Transactions**: 5% of records have amount $\ge$ INR 25,000.
- **Customer Diversity**: 700 distinct customer profiles with varied lifetime values (LTV), historical payment success rates (40%-98%), and contact preferences (`email`, `sms`, `none`).
- **Failure Code Categories**: `BANK_TIMEOUT` (20%), `TEMPORARY_BANK_ERROR` (20%), `INSUFFICIENT_FUNDS` (30%), `CARD_EXPIRED` (15%), `LIMIT_EXCEEDED` (10%), `CUSTOMER_DECLINED` (5%).

### B. Seed-Based Repeatability
All workflows run on the exact same transaction dataset under **identical simulator seeds** per transaction (`seed = 42 + transaction_index`). This guarantees mathematical reproducibility across all three strategies.

---

## 3. Comparative Strategies

### A. Naive Baseline (Retry-Once)
- Executes a single immediate retry (`retry_payment`) for failed transactions below INR 25,000.
- Stops if amount $\ge$ INR 25,000 or contact preference is `none`.
- No root-cause diagnosis or multi-step interventions.

### B. Rules-Only (Static Multi-Step Mapping)
- Applies static failure-code-to-action mappings (e.g. `BANK_TIMEOUT` $\rightarrow$ `retry_payment`).
- Allows up to `MAX_ATTEMPTS = 2`.
- Enforces basic policy guardrails (high-value escalation, opt-out checks).

### C. RecoverAI Agent (AI + ERV Optimization)
- Uses LLM root-cause diagnosis to parse rich transaction and customer context.
- Calculates Expected Recovery Value (ERV) to mathematically select the intervention maximizing Expected Net Recovery:
  $$\text{Expected Net Recovery} = (\text{Success Probability} \times \text{Recoverable Amount}) - \text{Operational Cost}$$
- Validates selected interventions against compiled Python policy guardrails.
- Enforces `MAX_ATTEMPTS = 2` stopping rules.

---

## 4. Canonical Benchmark Results (1,000 Cases, Seed=42)

Source of Truth: `data/evaluation/evaluation_results.json`

| Metric | Naive Baseline (Retry-Once) | Rules-Only (Static) | RecoverAI Agent (AI-Optimized) |
| :--- | :--- | :--- | :--- |
| **Transactions Evaluated** | 1,000 | 1,000 | 1,000 |
| **Transactions Successfully Recovered** | 321 / 1,000 | 515 / 1,000 | **661 / 1,000** |
| **Transaction Recovery Rate** | 32.1% | 51.5% | **66.1%** |
| **Revenue at Risk** | INR 14,648,500.39 | INR 14,648,500.39 | INR 14,648,500.39 |
| **Gross Revenue Recovered** | INR 4,292,057.07 | INR 6,815,233.05 | **INR 8,647,258.31** |
| **Revenue Recovery Rate** | 29.30% | 46.53% | **59.03%** |
| **Recovery Operational Cost** | INR 839.00 | INR 30,072.00 | INR 34,795.00 |
| **Net Revenue Recovered** | INR 4,291,218.07 | INR 6,785,161.05 | **INR 8,612,463.31** |
| **Financial Net Uplift (vs Baseline)** | — | +17.22% | **+29.73% (+INR 4,355,201.24)** |
| **Financial Net Uplift (vs Rules-Only)**| — | — | **+12.51% (+INR 1,832,025.26)** |
| **Average Attempts per Transaction** | 0.84 | 1.40 | 1.53 |
| **Escalated Cases (Human Queue)** | 0 | 295 (29.5%) | 339 (33.9%) |
| **Policy Violation Rate** | 0.0% | 0.0% | **0.0% (100% Compliant)** |
| **Stopping Rule Compliance** | 100.0% | 100.0% | **100.0% (MAX_ATTEMPTS=2 Enforced)** |

---

## 5. Local LLM Evaluation Optimization (`--llm-limit`)

Local LLM CPU inference on standard hardware takes ~30-45 seconds per transaction. Processing 1,000 transactions entirely via CPU LLM would take >10 hours.

To allow instant verification during judging:
- Running `python scripts/run_evaluation.py --count 1000 --llm-limit 2` processes the first 2 cases via Ollama to verify live prompt construction, structured output parsing, and reasoning logs.
- The remaining 998 cases execute via the deterministic ERV solver fallback, completing the 1,000-case evaluation in seconds.
- On GPU hardware, evaluators can scale `--llm-limit` (e.g. `--llm-limit 100` or `--llm-limit 1000`).
