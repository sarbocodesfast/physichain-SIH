"""
PhysiChain - Real blockchain bridge (stretch goal)

ONLY attempt this after the fallback ledger.py demo is working end-to-end.
This deploys AttestationRegistry.sol to a local Anvil node and forwards
attestation packets from the simulation module's log into it.

Prereqs (install ahead of time, not during the hackathon crunch):
    1. Foundry:  curl -L https://foundry.paradigm.xyz | bash && foundryup
    2. Start a local node in a separate terminal:  anvil
    3. pip install web3 py-solc-x --break-system-packages
    4. python -c "import solcx; solcx.install_solc('0.8.20')"

Run:
    python deploy_and_bridge.py --file ../simulation/attestation_log.jsonl
"""

import argparse
import hashlib
import json
import time

from web3 import Web3
from solcx import compile_source, install_solc

ANVIL_URL = "http://127.0.0.1:8545"
SOLC_VERSION = "0.8.20"

CONTRACT_SOURCE = open(
    "contracts/AttestationRegistry.sol"
).read() if __name__ == "__main__" else ""

TRUST_STATE_MAP = {"TRUSTED": 0, "STRICT": 1, "ISOLATED": 2}


def determine_trust_state(packet: dict) -> str:
    if packet["sensor"]["tamper_flag"]:
        return "ISOLATED"
    if packet["is_anomaly"]:
        return "STRICT"
    return "TRUSTED"


def compile_contract():
    install_solc(SOLC_VERSION)
    compiled = compile_source(
        CONTRACT_SOURCE, output_values=["abi", "bin"], solc_version=SOLC_VERSION
    )
    _, contract_interface = compiled.popitem()
    return contract_interface["abi"], contract_interface["bin"]


def deploy(w3: Web3, abi, bytecode, account):
    Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    tx_hash = Contract.constructor().transact({"from": account})
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"[Ledger] Contract deployed at {receipt.contractAddress}")
    return w3.eth.contract(address=receipt.contractAddress, abi=abi)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="../simulation/attestation_log.jsonl")
    args = parser.parse_args()

    w3 = Web3(Web3.HTTPProvider(ANVIL_URL))
    assert w3.is_connected(), "Could not connect to Anvil at " + ANVIL_URL
    account = w3.eth.accounts[0]

    abi, bytecode = compile_contract()
    contract = deploy(w3, abi, bytecode, account)

    registered = set()
    with open(args.file) as f:
        for line in f:
            packet = json.loads(line.strip())
            device_id = packet["device_id"]

            if device_id not in registered:
                tx = contract.functions.registerDevice(device_id).transact(
                    {"from": account}
                )
                w3.eth.wait_for_transaction_receipt(tx)
                registered.add(device_id)

            state = determine_trust_state(packet)
            packet_hash = Web3.keccak(
                text=json.dumps(packet, sort_keys=True)
            )

            tx = contract.functions.logAttestation(
                device_id, packet_hash, TRUST_STATE_MAP[state]
            ).transact({"from": account})
            receipt = w3.eth.wait_for_transaction_receipt(tx)

            print(f"On-chain: device={device_id} state={state} "
                  f"tx={receipt.transactionHash.hex()[:12]}...")
            time.sleep(0.1)

    total = contract.functions.totalAttestations().call()
    print(f"\n[Ledger] {total} attestations logged on-chain at "
          f"{contract.address}")


if __name__ == "__main__":
    main()
