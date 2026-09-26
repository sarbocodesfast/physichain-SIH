"""
PhysiChain - Live demo dashboard

Reads ledger_state.json (written by blockchain/ledger.py) and shows:
  - big current trust-state indicator
  - recent attestation blocks / mini hash chain
  - a button that runs a fresh simulation with an injected attack, so you
    can trigger the "flip to ISOLATED" moment live in front of judges

Run (from the physichain/ folder, after the simulation + blockchain scripts exist):
    streamlit run shared/dashboard.py
"""

import json
import subprocess
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
LEDGER_STATE = ROOT / "blockchain" / "ledger_state.json"
SIMULATION_DIR = ROOT / "simulation"
BLOCKCHAIN_DIR = ROOT / "blockchain"

st.set_page_config(page_title="PhysiChain - Live Demo", layout="wide")

st.title("🔒 PhysiChain — Device Attestation Dashboard")
st.caption("Hardware root-of-trust attestation, backed by a tamper-evident ledger")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Run a demo cycle")
    steps = st.slider("Number of readings", 5, 30, 15)
    attack_step = st.slider("Inject attack/tamper at step", -1, 29, 10,
                             help="-1 = no attack, normal run only")
    if st.button("▶ Run simulation", type="primary"):
        with st.spinner("Simulating sensor readings + anomaly scoring..."):
            subprocess.run(
                [sys.executable, "sensor_simulator.py",
                 "--steps", str(steps), "--attack-at", str(attack_step)],
                cwd=SIMULATION_DIR, check=True,
            )
        with st.spinner("Writing attestations to tamper-evident ledger..."):
            subprocess.run(
                [sys.executable, "ledger.py",
                 "--file", str(SIMULATION_DIR / "attestation_log.jsonl")],
                cwd=BLOCKCHAIN_DIR, check=True,
            )
        st.success("Demo cycle complete.")
        st.rerun()

with col2:
    if LEDGER_STATE.exists():
        chain = json.loads(LEDGER_STATE.read_text())
        if chain:
            latest = chain[-1]
            state = latest["trust_state"]
            color = {"TRUSTED": "green", "STRICT": "orange",
                     "ISOLATED": "red"}.get(state, "gray")
            st.markdown(
                f"<h1 style='text-align:center;color:{color};'>{state}</h1>"
                f"<p style='text-align:center;'>Device: {latest['device_id']} "
                f"| Block #{latest['index']} | Chain valid: "
                f"{'✅' if chain else '—'}</p>",
                unsafe_allow_html=True,
            )
        else:
            st.info("No attestations yet — click 'Run simulation'.")
    else:
        st.info("No ledger yet — click 'Run simulation' to generate one.")

st.divider()
st.subheader("Attestation chain (most recent first)")

if LEDGER_STATE.exists():
    chain = json.loads(LEDGER_STATE.read_text())
    for block in reversed(chain[-20:]):
        att = block["attestation"]
        icon = {"TRUSTED": "🟢", "STRICT": "🟠", "ISOLATED": "🔴"}.get(
            block["trust_state"], "⚪")
        with st.expander(
            f"{icon} Block #{block['index']} — {block['trust_state']} "
            f"— {block['device_id']} — hash {block['block_hash'][:10]}..."
        ):
            c1, c2 = st.columns(2)
            c1.metric("Temperature (C)", att["sensor"]["temperature_c"])
            c1.metric("Current (mA)", att["sensor"]["current_ma"])
            c2.metric("Anomaly score", att["anomaly_score"])
            c2.metric("Tamper flag", str(att["sensor"]["tamper_flag"]))
            st.code(json.dumps(block, indent=2), language="json")
else:
    st.write("Run a simulation cycle to populate the chain.")
