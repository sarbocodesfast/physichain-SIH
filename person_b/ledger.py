"""
PhysiChain - Person B module (FALLBACK / GUARANTEED-WORKING PATH)

A tamper-evident hash-chain "ledger" that mimics what the blockchain layer
does (append-only, each record cryptographically linked to the previous
one) without needing Solidity/Anvil/Hardhat installed. Use this if the
real blockchain setup (blockchain_contract/) isn't ready in time -- it
still demonstrates the core "immutable attestation log" concept live.

Run:
    python ledger.py --watch attestation_log.jsonl
(point it at Person A's output file; it will ingest new lines as they
appear and print the running trust state + chain)
"""

import argparse
import hashlib
import json
import os
import time
from dataclasses import dataclass, asdict, field


GENESIS_HASH = "0" * 64


@dataclass
class LedgerBlock:
    index: int
    timestamp: float
    device_id: str
    attestation: dict
    trust_state: str
    prev_hash: str
    block_hash: str = field(default="")

    def compute_hash(self) -> str:
        payload = {
            "index": self.index,
            "timestamp": self.timestamp,
            "device_id": self.device_id,
            "attestation": self.attestation,
            "trust_state": self.trust_state,
            "prev_hash": self.prev_hash,
        }
        blob = json.dumps(payload, sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()


class Ledger:
    def __init__(self):
        self.chain: list[LedgerBlock] = []

    def determine_trust_state(self, packet: dict) -> str:
        """TRUSTED / STRICT / ISOLATED decision logic."""
        if packet["sensor"]["tamper_flag"]:
            return "ISOLATED"
        if packet["is_anomaly"]:
            return "STRICT"
        return "TRUSTED"

    def add_attestation(self, packet: dict) -> LedgerBlock:
        prev_hash = self.chain[-1].block_hash if self.chain else GENESIS_HASH
        trust_state = self.determine_trust_state(packet)

        block = LedgerBlock(
            index=len(self.chain),
            timestamp=time.time(),
            device_id=packet["device_id"],
            attestation=packet,
            trust_state=trust_state,
            prev_hash=prev_hash,
        )
        block.block_hash = block.compute_hash()
        self.chain.append(block)
        return block

    def verify_chain(self) -> bool:
        for i, block in enumerate(self.chain):
            expected_prev = self.chain[i - 1].block_hash if i > 0 else GENESIS_HASH
            if block.prev_hash != expected_prev:
                return False
            recomputed = block.compute_hash()
            if recomputed != block.block_hash:
                return False
        return True

    def to_json(self, path="ledger_state.json"):
        with open(path, "w") as f:
            json.dump([asdict(b) for b in self.chain], f, indent=2)


def watch_file(path: str, poll_interval: float = 1.0):
    ledger = Ledger()
    seen_lines = 0
    print(f"[Person B] Watching {path} for new attestation packets... "
          f"(Ctrl+C to stop)\n")

    try:
        while True:
            if os.path.exists(path):
                with open(path) as f:
                    lines = f.readlines()
                new_lines = lines[seen_lines:]
                for line in new_lines:
                    line = line.strip()
                    if not line:
                        continue
                    packet = json.loads(line)
                    block = ledger.add_attestation(packet)
                    print(f"block #{block.index:03d} | device={block.device_id} "
                          f"| trust_state={block.trust_state:<9} "
                          f"| hash={block.block_hash[:12]}... "
                          f"| valid_chain={ledger.verify_chain()}")
                seen_lines = len(lines)
                ledger.to_json()
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print(f"\n[Person B] Stopped. {len(ledger.chain)} blocks recorded, "
              f"chain valid={ledger.verify_chain()}. Wrote ledger_state.json")


def replay_file(path: str):
    """Non-watching mode: ingest a complete file once and exit (useful for
    demo runs where Person A's script has already finished)."""
    ledger = Ledger()
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            packet = json.loads(line)
            block = ledger.add_attestation(packet)
            print(f"block #{block.index:03d} | device={block.device_id} "
                  f"| trust_state={block.trust_state:<9} "
                  f"| hash={block.block_hash[:12]}...")
    print(f"\n[Person B] Ingested {len(ledger.chain)} blocks. "
          f"Chain valid={ledger.verify_chain()}")
    ledger.to_json()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="attestation_log.jsonl")
    parser.add_argument("--watch", action="store_true",
                         help="poll the file continuously instead of running once")
    args = parser.parse_args()

    if args.watch:
        watch_file(args.file)
    else:
        replay_file(args.file)
