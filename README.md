# PhysiChain — SIH Software Simulation

Working starter code for the software-simulation slice of PhysiChain:
sensor simulation → anomaly detection → attestation packet → tamper-evident
ledger → live dashboard. The blockchain smart contract is included as a
stretch goal, but the core demo does NOT require it to work.

## Folder layout
```
physichain/
├── simulation/
│   ├── sensor_simulator.py      # simulated IMU/temp/current + anomaly detector
│   ├── iot_blockchain_security_dataset.csv
│   └── requirements.txt
├── blockchain/
│   ├── ledger.py                 # tamper-evident hash-chain (GUARANTEED path)
│   ├── contracts/AttestationRegistry.sol   # real Solidity (stretch goal)
│   ├── deploy_and_bridge.py      # deploys + writes to real chain (stretch goal)
│   └── requirements.txt
└── shared/
    └── dashboard.py               # Streamlit live demo screen
```

## Quickstart (the guaranteed-working path)

```bash
# 1. Install deps
cd simulation && pip install -r requirements.txt && cd ..
cd blockchain && pip install -r requirements.txt && cd ..

# 2. Run a normal demo cycle
cd simulation
python sensor_simulator.py --steps 15 --attack-at -1   # no attack, all TRUSTED
python sensor_simulator.py --steps 15 --attack-at 8    # attack injected at step 8

# 3. Feed it into the ledger
cd ../blockchain
python ledger.py --file ../simulation/attestation_log.jsonl

# 4. Live dashboard (do this one for the actual demo in front of judges)
cd ..
streamlit run shared/dashboard.py
```

In the dashboard: set "Inject attack/tamper at step" to a real step number,
hit **Run simulation**, and watch the status flip from TRUSTED (green) to
ISOLATED (red) live, with the hash chain updating below it.

## What's already verified working
- `sensor_simulator.py`: anomaly detector correctly separates normal vs.
  injected attack readings (tested — 14/15 normal readings scored "ok",
  the 1 injected attack at step 8 was the only one flagged).
- `ledger.py`: correctly ingests the simulation's output, flips trust state
  to ISOLATED on the tamper reading, and the hash chain validates
  (`chain valid=True`).
- `dashboard.py`: syntax-checked; wires both scripts together via
  subprocess calls so one button press runs the whole pipeline.

## What's NOT tested (stretch goal only)
`deploy_and_bridge.py` + `AttestationRegistry.sol` need Foundry/Anvil and
`web3`/`py-solc-x` installed locally — untested in this environment.
**Do not attempt this until the ledger.py path above is working and
demo-ready.** If it works, it strictly upgrades the ledger to a real EVM
chain; if it doesn't work in time, the hash-chain ledger is a legitimate
fallback that still demonstrates the same tamper-evident concept.

## Talking points for judges
- The attestation packet format (device_id, PUF response, sensor state,
  anomaly score, firmware hash, nonce, signature) is the same shape
  whether it's logged to the fallback ledger or a real smart contract —
  swapping the backend doesn't change the architecture.
- Be upfront that PUF simulation here is architecture-level (deterministic
  hash + injected noise), not a real SRAM PUF — real PUF stability needs
  physical silicon measurement across power/temp/voltage, which is future
  hardware work, not something software simulation can claim to prove.
