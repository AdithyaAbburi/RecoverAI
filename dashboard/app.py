import os
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add root folder to sys.path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.db.models import Transaction, Customer, Invoice, AuditLog
from app.agent.erv_engine import calculate_ervs

# Set page config
st.set_page_config(
    page_title="RecoverAI Dashboard",
    layout="wide"
)

# Connect to database
@st.cache_resource
def get_db_engine():
    return create_engine(settings.DATABASE_URL)

engine = get_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def load_db_data():
    db = SessionLocal()
    try:
        txs = db.query(Transaction).all()
        tx_data = [{
            "transaction_id": t.transaction_id,
            "customer_id": t.customer_id,
            "amount": t.amount,
            "payment_method": t.payment_method,
            "status": t.status,
            "failure_code": t.failure_code,
            "retry_count": t.retry_count,
            "timestamp": t.timestamp
        } for t in txs]
        return pd.DataFrame(tx_data)
    finally:
        db.close()

# Load evaluation results if available
@st.cache_data
def load_evaluation_data():
    baseline_path = "data/evaluation/baseline_results.csv"
    rules_path = "data/evaluation/rules_only_results.csv"
    agent_path = "data/evaluation/agent_results.csv"
    
    baseline_df = None
    rules_df = None
    agent_df = None
    
    if os.path.exists(baseline_path):
        baseline_df = pd.read_csv(baseline_path)
    if os.path.exists(rules_path):
        rules_df = pd.read_csv(rules_path)
    if os.path.exists(agent_path):
        agent_df = pd.read_csv(agent_path)
        
    return baseline_df, rules_df, agent_df

# Title
st.title("RecoverAI: Revenue Recovery Operations Control Dashboard")
st.markdown("### Target: Razorpay AI Buildathon — Track 03: AI Revenue Recovery")

# Load data
db_df = load_db_data()
baseline_df, rules_df, agent_df = load_evaluation_data()

# -----------------
# KPI ROW
# -----------------
st.subheader("Key Performance Indicators (Evaluation Batch)")

if agent_df is not None and baseline_df is not None and rules_df is not None:
    # Aggregates
    rev_at_risk = agent_df["amount"].sum()
    agent_recovered = agent_df.loc[agent_df["status"] == "SUCCESS", "amount_recovered"].sum()
    rules_recovered = rules_df.loc[rules_df["status"] == "SUCCESS", "amount_recovered"].sum()
    baseline_recovered = baseline_df.loc[baseline_df["status"] == "SUCCESS", "amount_recovered"].sum()
    
    agent_recovery_rate = (agent_recovered / rev_at_risk * 100.0) if rev_at_risk > 0 else 0.0
    rules_recovery_rate = (rules_recovered / rev_at_risk * 100.0) if rev_at_risk > 0 else 0.0
    baseline_recovery_rate = (baseline_recovered / rev_at_risk * 100.0) if rev_at_risk > 0 else 0.0
    
    uplift_baseline = agent_recovered - baseline_recovered
    uplift_rules = agent_recovered - rules_recovered
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Revenue at Risk", f"₹{rev_at_risk:,.2f}")
    with col2:
        st.metric("Baseline (Retry-Once)", f"₹{baseline_recovered:,.2f}", f"{baseline_recovery_rate:.2f}% Rate")
    with col3:
        st.metric("Rules-Only (Multi-step)", f"₹{rules_recovered:,.2f}", f"{rules_recovery_rate:.2f}% Rate")
    with col4:
        st.metric("RecoverAI (AI-Optimized)", f"₹{agent_recovered:,.2f}", f"{agent_recovery_rate:.2f}% Rate")
    with col5:
        st.metric("AI Uplift (vs Rules)", f"₹{uplift_rules:,.2f}", f"+{agent_recovery_rate - rules_recovery_rate:.2f}% vs Rules")
else:
    st.info("No evaluation run data found. Run scripts/generate_data.py and scripts/run_batch.py first.")

st.markdown("---")

# -----------------
# COMPARISONS & CHARTS
# -----------------
if agent_df is not None and baseline_df is not None and rules_df is not None:
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.markdown("#### Financial Recovery Comparison (INR)")
        comparison_data = pd.DataFrame({
            "Workflow": ["Baseline (Retry-Once)", "Rules-Only (Multi-step)", "RecoverAI (AI-Optimized)"],
            "Recovered (₹)": [baseline_recovered, rules_recovered, agent_recovered]
        })
        st.bar_chart(comparison_data.set_index("Workflow"))
        
    with col_chart2:
        st.markdown("#### Recovery Agent Action Breakdown")
        action_counts = agent_df["final_action"].value_counts().reset_index()
        action_counts.columns = ["Action", "Count"]
        st.bar_chart(action_counts.set_index("Action"))

    col_chart3, col_chart4 = st.columns(2)
    with col_chart3:
        st.markdown("#### Failure Reason Distribution")
        fail_counts = agent_df["failure_code"].value_counts().reset_index()
        fail_counts.columns = ["Failure Code", "Count"]
        st.bar_chart(fail_counts.set_index("Failure Code"))
        
    with col_chart4:
        st.markdown("#### Deterministic Policy Interventions")
        policy_counts = agent_df["policy_result"].value_counts().reset_index()
        policy_counts.columns = ["Guardrail Decision", "Count"]
        st.bar_chart(policy_counts.set_index("Guardrail Decision"))

    st.markdown("---")

# -----------------
# INTERACTIVE CASE VIEWER
# -----------------
st.subheader("Transaction Case and Audit Viewer")
st.markdown("Filter transactions to inspect the agent's diagnosis, policy decisions, and tool executions.")

if not db_df.empty:
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        status_filter = st.selectbox("Status", ["All", "FAILED", "SUCCESS"])
    with col_f2:
        failure_filter = st.selectbox("Failure Code", ["All"] + list(db_df["failure_code"].dropna().unique()))
    with col_f3:
        search_tx = st.text_input("Search Transaction ID (e.g. TX00001)")
        
    # Apply filters
    filtered_df = db_df.copy()
    if status_filter != "All":
        filtered_df = filtered_df[filtered_df["status"] == status_filter]
    if failure_filter != "All":
        filtered_df = filtered_df[filtered_df["failure_code"] == failure_filter]
    if search_tx:
        filtered_df = filtered_df[filtered_df["transaction_id"].str.contains(search_tx, case=False)]
        
    st.dataframe(filtered_df.head(100), use_container_width=True)
    
    # Selection details
    st.markdown("### Detailed Audit Trail for Selected Transaction")
    selected_tx_id = st.text_input("Enter Transaction ID to view audit logs:", value=filtered_df.iloc[0]["transaction_id"] if not filtered_df.empty else "")
    
    if selected_tx_id:
        db = SessionLocal()
        tx = db.query(Transaction).filter(Transaction.transaction_id == selected_tx_id).first()
        if tx:
            customer = db.query(Customer).filter(Customer.customer_id == tx.customer_id).first()
            invoice = db.query(Invoice).filter(Invoice.customer_id == tx.customer_id).first()
            audits = db.query(AuditLog).filter(AuditLog.transaction_id == selected_tx_id).order_by(AuditLog.id.asc()).all()
            
            c_details1, c_details2, c_details3 = st.columns(3)
            with c_details1:
                st.markdown(f"**Transaction ID**: `{tx.transaction_id}`  \n**Amount**: ₹{tx.amount:,.2f}  \n**Status**: `{tx.status}`  \n**Failure Code**: `{tx.failure_code}`")
            with c_details2:
                if customer:
                    st.markdown(f"**Customer ID**: `{customer.customer_id}`  \n**Type**: `{customer.customer_type}`  \n**Success Rate**: `{customer.previous_payment_success_rate:.2f}`  \n**Preference**: `{customer.contact_preference}`  \n**Risk Flag**: `{customer.risk_flag}`")
                else:
                    st.markdown("*No customer profile found*")
            with c_details3:
                if invoice:
                    st.markdown(f"**Invoice ID**: `{invoice.invoice_id}`  \n**Amount Due**: ₹{invoice.amount_due:,.2f}  \n**Days Overdue**: `{invoice.days_overdue}`  \n**Promise to Pay**: `{invoice.promise_to_pay}`")
                else:
                    st.markdown("*No outstanding invoices*")
            
            st.markdown("---")
            # Show ERV comparisons
            ervs = calculate_ervs(tx.amount, tx.failure_code)
            erv_rows = []
            for action, metrics in ervs.items():
                erv_rows.append({
                    "Intervention Action": action,
                    "Success Probability": f"{metrics['probability']*100:.0f}%",
                    "Operational Cost": f"₹{metrics['cost']:.1f}",
                    "Expected Net Recovery": f"₹{metrics['expected_net']:,.2f}"
                })
            st.markdown("#### Expected Net Recovery Value (ERV) Decision Matrix")
            st.table(pd.DataFrame(erv_rows))
            # Show AI Selection Explanation
            rc_audit = db.query(AuditLog).filter(
                AuditLog.transaction_id == selected_tx_id,
                AuditLog.stage == "root_cause_analysis"
            ).order_by(AuditLog.id.desc()).first()

            if rc_audit:
                st.markdown("#### AI Selected Intervention & Reasoning")
                st.info(f"**Selected Action**: `{rc_audit.agent_action}`  \n\n**Reasoning**: {rc_audit.reason}")
                st.markdown("---")

            st.markdown("#### Audit Trail Timeline")
            if audits:
                audit_records = []
                for a in audits:
                    audit_records.append({
                        "Time": a.timestamp,
                        "Stage": a.stage,
                        "Action Recommended": a.agent_action or "None",
                        "Policy Status": a.policy_result or "None",
                        "Tool Status": a.tool_result or "None",
                        "Recovered (₹)": a.amount_recovered,
                        "Logs & Details": a.reason
                    })
                st.table(pd.DataFrame(audit_records))
            else:
                st.info("No audit logs recorded for this transaction yet.")
        else:
            st.warning("Transaction not found. Enter a valid transaction ID.")
        db.close()
else:
    st.info("No records loaded from database. Verify SQLite database file is populated.")
