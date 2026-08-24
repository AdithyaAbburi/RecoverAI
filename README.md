# RecoverAI: Bounded Autonomous Revenue Recovery Agent

> **Razorpay AI Buildathon (Track 03: AI Revenue Recovery)**  
> An autonomous agent that detects payment failures, diagnoses root causes, economically optimizes recovery paths (ERV), and executes actions under strict deterministic policy guardrails.

---

## 📈 E2E Evaluation & Business Impact
RecoverAI was evaluated on a reproducible batch of **1,000 synthetic transaction failures** (under identical simulator seeds to ensure scientific comparison):

| Metric | Naive Baseline (Retry-Once) | Rules-Only (Static Mapping) | RecoverAI Agent (AI-Optimized) |
| :--- | :--- | :--- | :--- |
| **Transactions Recovered** | 321 (32.1%) | 515 (51.5%) | **660 (66.0%)** |
| **Total Revenue Recovered** | INR 4,292,057.07 | INR 6,815,233.05 | **INR 8,647,258.31** |
| **Recovery Rate (%)** | 29.30% | 46.53% | **59.00%** |
| **Financial Uplift vs. Baseline** | — | +17.22% | **+29.70% (₹43.55 Lakhs Saved)** |
| **Financial Uplift vs. Rules-Only**| — | — | **+12.48% (₹18.32 Lakhs Saved)** |
| **Policy Violation Rate** | 0.0% | 0.0% | **0.0% (100% Compliant)** |
| **Stopping Rule Compliance** | 100.0% | 100.0% | **100.0% (MAX_ATTEMPTS=2 Enforced)** |

---

## 🏗️ System Architecture

RecoverAI is built on a defensive, multi-stage engineering pipeline designed for high-stakes financial operations. Rather than letting the LLM directly execute actions, the LLM is restricted to context diagnosis, while a mathematical optimizer ranks actions, and a deterministic engine enforces safety policies.

```
                  [ Transaction Failure Ingestion ]
                                  ↓
                  [ 1. Deterministic Risk Engine ]
                      (Scores severity: 0-100)
                                  ↓
                  [ 2. LLM Root-Cause Diagnosis ]
                 (Local DeepSeek-Coder:6.7b on CPU)
                                  ↓
                    [ 3. ERV Ranking Optimizer ]
                   (Calculates Expected Net Value)
                                  ↓
                  [ 4. Deterministic Policy Engine ]
                  (Safety constraints & limits check)
                                  ↓
                       Approved   |   Rejected / Escalated
                    +-------------+-------------+
                    |                           |
                    v                           v
         [ 5. Bounded Tool Exec ]       [ Human Ops Queue ]
             (Seeded Simulator)
                    |
                    v
         [ 6. Immutable Audit Trail ]
              (SQLite DB Logs)
```

1. **Revenue Risk Engine**: Generates a risk score (0-100) based on transaction value, historical failure frequency, and active customer invoices.
2. **LLM Diagnosis Module**: Analyzes customer metadata, lifetime value (LTV), overdue invoices, and transaction logs to diagnose the real root cause (e.g., resolving ambiguity between temporary bank timeouts and liquidity issues).
3. **Expected Recovery Value (ERV) Optimizer**: Selects the candidate action that mathematically maximizes net recovery:  
   $$\text{Expected Net Recovery} = (\text{Success Probability} \times \text{Amount}) - \text{Operational Cost}$$
4. **Policy Guardrail Engine**: The final gatekeeper. Validates the action against strict safety policies (e.g., capping retries to `MAX_ATTEMPTS = 2`, blocking contact actions for opted-out users, and routing transactions $\ge$ ₹25,000 immediately to manual review).
5. **Bounded Tool Execution**: Executes the action in a seeded payment simulator.
6. **Immutable Audit Trail**: Records a step-by-step trace of every decision stage to SQLite for compliance.

---

## 📂 Codebase Structure
```
RecoverAI/
├── app/
│   ├── main.py                 # FastAPI Web API
│   ├── config.py               # Env Configuration
│   ├── agent/                  # Agent orchestrator, tools, and prompts
│   ├── risk/                   # Transaction Risk Scoring Engine
│   ├── diagnosis/              # LLM root-cause analyzer (Ollama)
│   ├── policy/                 # Hardcoded business policy guardrails
│   ├── simulator/              # Seeded repeatable payment simulator
│   ├── services/               # DB interaction services
│   └── db/                     # DB schemas and database session setup
├── dashboard/                  # streamlit Operations Control Room (app.py)
├── scripts/                    # CLI tools (generate_data.py, run_batch.py, evaluate.py)
├── tests/                      # Pytest automation suite
└── docs/                       # Architectural & evaluation details
```

---

## 🚀 Getting Started & Reproducing the Metrics

### 1. Prerequisites
- **Python**: 3.13+ installed.
- **Ollama**: Installed and running locally. Pull the model before starting:
  ```bash
  ollama pull deepseek-coder:6.7b
  ```

### 2. Installation
Clone the repository, install python dependencies, and set up your environment variables:
```bash
pip install -r requirements.txt
cp .env.example .env
```

### 3. Run Automated Tests
Verify code integrity and safety guardrail assertions:
```bash
python -m pytest tests/
```

### 4. Replicate the Ablation Study (1,000 Transactions)
Initialize the database and execute the comparative evaluation runs:
```bash
# 1. Generate clean synthetic transaction dataset
python scripts/generate_data.py --count 1000

# 2. Run baseline, rules-only, and AI recovery workflows
python scripts/run_batch.py --limit 1000 --llm-limit 2

# 3. Print the final metrics summary
python scripts/evaluate.py
```

### 5. Launch the Streamlit Dashboard Control Room
Inspect interactive charts, recovery metric breakdowns, and detailed audit timelines:
```bash
streamlit run dashboard/app.py
```

---

## 🔬 Core Engineering Rationales (For Judges/Interviewers)

* **Defensive Guardrails**: LLMs are creative and prone to hallucination. RecoverAI addresses this by using the LLM strictly as a *context diagnostic tool* to label the failure. The actual recovery action is chosen by a mathematical optimization function and validated against a compiled python rules engine.
* **Local Inference Efficiency**: To scale to thousands of transactions on standard hardware, the agent supports a `--llm-limit` parameter. Only initial transactions run LLM inference to demonstrate capability, while the rest fall back to the ERV optimizer, completing large batches in seconds.
* **Write-Ahead Logging (WAL) Mode**: Integrated database connection event listeners to set SQLite pragmas (`PRAGMA journal_mode = WAL` and `PRAGMA synchronous = NORMAL`). This resolves lock timeouts and allows Streamlit to perform concurrent reads during batch evaluation writes.
