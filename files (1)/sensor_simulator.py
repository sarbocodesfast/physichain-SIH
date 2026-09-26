"""
PhysiChain - Person A module
Simulates IMU/temperature/tamper readings for a device, trains an
Isolation Forest anomaly detector on the provided IoT security dataset,
and emits an attestation packet (JSON) per reading.

Run:
    python sensor_simulator.py                 # normal run, 20 readings
    python sensor_simulator.py --attack-at 10   # inject a tamper/anomaly at reading 10
"""

import argparse
import json
import time
import uuid
import hashlib
import random

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

DATASET_PATH = "iot_blockchain_security_dataset.csv"  # place next to this script


# ---------------------------------------------------------------------------
# 1. Train anomaly detector
#
# The IoT dataset's columns (Data Size, Processing Time, Energy...) live on
# a different scale than our simulated IMU/temp/current proxy features, so
# training directly on the raw CSV miscalibrates the detector (everything
# looks "anomalous"). Instead we bootstrap a training set in the SAME
# feature space the live readings will be scored in (self-consistent), and
# use the dataset only to sanity-check realistic severity/contamination
# levels -- good enough for a demo, and honest about what it is.
# ---------------------------------------------------------------------------
def train_anomaly_model(csv_path: str = DATASET_PATH, n_bootstrap: int = 400):
    df = pd.read_csv(csv_path)
    dataset_attack_rate = (df["Attack Severity (0-10)"] >= 5).mean()

    # Bootstrap "normal" readings (95%) + a few "attack" readings (5%) through
    # the exact same feature pipeline used at inference time.
    X = []
    n_attack = max(1, int(n_bootstrap * 0.05))
    for _ in range(n_bootstrap - n_attack):
        X.append(reading_to_feature_vector(generate_reading(0, attack=False)))
    for _ in range(n_attack):
        X.append(reading_to_feature_vector(generate_reading(0, attack=True)))
    X = np.array(X)

    model = IsolationForest(
        n_estimators=150,
        contamination=0.05,
        random_state=42,
    )
    model.fit(X)

    feature_cols = ["data_size_proxy", "processing_time_proxy",
                     "severity_proxy", "txn_time_proxy", "energy_proxy"]
    print(f"[Person A] Reference dataset attack rate (severity>=5): "
          f"{dataset_attack_rate:.1%} (used only as a sanity check)")
    return model, feature_cols, df


# ---------------------------------------------------------------------------
# 2. Fake sensor reading generator (stand-in for Wokwi/ESP32 stream)
# ---------------------------------------------------------------------------
def generate_reading(step: int, attack: bool = False):
    """Simulates one IMU + temperature + tamper + current sample."""
    if not attack:
        accel = [round(random.gauss(0, 0.05), 3) for _ in range(3)]   # g
        gyro = [round(random.gauss(0, 1.0), 3) for _ in range(3)]     # deg/s
        temp = round(random.gauss(30, 1.0), 2)                         # C
        current = round(random.gauss(45, 3), 2)                        # mA
        tamper_flag = False
    else:
        # exaggerated motion / heat / current spike = tamper or attack event
        accel = [round(random.gauss(0, 0.8), 3) for _ in range(3)]
        gyro = [round(random.gauss(0, 25), 3) for _ in range(3)]
        temp = round(random.gauss(55, 4), 2)
        current = round(random.gauss(120, 15), 2)
        tamper_flag = True

    return {
        "step": step,
        "accel_g": accel,
        "gyro_dps": gyro,
        "temperature_c": temp,
        "current_ma": current,
        "tamper_flag": tamper_flag,
    }


def reading_to_feature_vector(reading: dict):
    """Maps a raw sensor reading onto the same 5-D feature space the
    anomaly model was trained on, so the model can score live readings.
    This is a deliberately simple mapping for the demo -- swap in your
    own scaling once real Wokwi data is available."""
    accel_mag = float(np.linalg.norm(reading["accel_g"]))
    gyro_mag = float(np.linalg.norm(reading["gyro_dps"]))
    data_size_proxy = 200 + accel_mag * 400          # KB-ish
    processing_time_proxy = 10 + gyro_mag * 0.5       # ms-ish
    severity_proxy = min(10, gyro_mag / 3)            # 0-10-ish
    txn_time_proxy = 100 + reading["current_ma"] * 0.5
    energy_proxy = reading["current_ma"] * 0.02

    return [
        data_size_proxy,
        processing_time_proxy,
        severity_proxy,
        txn_time_proxy,
        energy_proxy,
    ]


# ---------------------------------------------------------------------------
# 3. PUF-style response simulator (very simplified, architecture-level only)
# ---------------------------------------------------------------------------
def simulate_puf_response(device_id: str, challenge: str, noise: float = 0.02):
    """Deterministic 'ideal' response from device_id+challenge, with a small
    amount of flipped bits to emulate real PUF noise. NOT a real SRAM PUF --
    for pipeline/architecture demo purposes only."""
    base = hashlib.sha256((device_id + challenge).encode()).hexdigest()
    bits = bin(int(base, 16))[2:].zfill(256)
    bits = list(bits)
    n_flips = int(len(bits) * noise)
    for idx in random.sample(range(len(bits)), n_flips):
        bits[idx] = "1" if bits[idx] == "0" else "0"
    return "".join(bits)


def hamming_distance(a: str, b: str) -> int:
    return sum(c1 != c2 for c1, c2 in zip(a, b))


# ---------------------------------------------------------------------------
# 4. Build attestation packet
# ---------------------------------------------------------------------------
def build_attestation_packet(device_id, reading, anomaly_score, is_anomaly,
                              puf_response, firmware_hash):
    return {
        "device_id": device_id,
        "timestamp": int(time.time()),
        "nonce": uuid.uuid4().hex,
        "puf_response": puf_response[:32] + "...",   # truncated for readability
        "sensor": {
            "temperature_c": reading["temperature_c"],
            "current_ma": reading["current_ma"],
            "tamper_flag": reading["tamper_flag"],
        },
        "anomaly_score": round(float(anomaly_score), 4),
        "is_anomaly": bool(is_anomaly),
        "firmware_hash": firmware_hash,
    }


# ---------------------------------------------------------------------------
# Main demo loop
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device-id", default="esp32-demo-01")
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--attack-at", type=int, default=-1,
                         help="step index to inject an attack/tamper reading")
    parser.add_argument("--out", default="attestation_log.jsonl")
    args = parser.parse_args()

    model, feature_cols, df = train_anomaly_model()
    print(f"[Person A] Anomaly model trained on {len(df)} rows, "
          f"features={feature_cols}")

    firmware_hash = hashlib.sha256(b"physichain-v1-firmware").hexdigest()[:16]
    challenge = uuid.uuid4().hex

    with open(args.out, "w") as f:
        for step in range(args.steps):
            attack = (step == args.attack_at)
            reading = generate_reading(step, attack=attack)
            feats = np.array([reading_to_feature_vector(reading)])

            score = -model.decision_function(feats)[0]  # higher = more anomalous
            is_anomaly = model.predict(feats)[0] == -1

            puf_resp = simulate_puf_response(args.device_id, challenge)

            packet = build_attestation_packet(
                args.device_id, reading, score, is_anomaly, puf_resp, firmware_hash
            )
            f.write(json.dumps(packet) + "\n")

            tag = "!! ANOMALY !!" if is_anomaly else "ok"
            print(f"step {step:02d} | temp={reading['temperature_c']:>6} "
                  f"current={reading['current_ma']:>7} "
                  f"tamper={reading['tamper_flag']!s:>5} "
                  f"score={score:.3f} -> {tag}")

    print(f"\n[Person A] Wrote {args.steps} attestation packets to {args.out}")
    print("Hand this file (or stream it live) to Person B's verifier/ledger.")


if __name__ == "__main__":
    main()
