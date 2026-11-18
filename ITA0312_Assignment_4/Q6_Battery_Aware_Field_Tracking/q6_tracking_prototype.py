import os, json, time, uuid, hashlib
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

OUT = Path("Q6_Battery_Aware_Field_Tracking")
for folder in ["results", "graphs", "reports"]:
    (OUT / folder).mkdir(parents=True, exist_ok=True)

KEY = AESGCM.generate_key(bit_length=256)
CIPHER = AESGCM(KEY)

SCENARIOS = [
    {"name":"Charging WiFi moving","battery":85,"charging":True,"network":"WIFI","motion":"MOVING","temp":33,"queue":20},
    {"name":"High battery LTE moving","battery":80,"charging":False,"network":"CELLULAR","motion":"MOVING","temp":34,"queue":5},
    {"name":"Low battery stationary LTE","battery":18,"charging":False,"network":"CELLULAR","motion":"STILL","temp":35,"queue":120},
    {"name":"Low power no network","battery":14,"charging":False,"network":"NONE","motion":"STILL","temp":36,"queue":80},
    {"name":"Hot device WiFi","battery":55,"charging":False,"network":"WIFI","motion":"MOVING","temp":44,"queue":35},
    {"name":"Normal battery no network","battery":60,"charging":False,"network":"NONE","motion":"MOVING","temp":32,"queue":45},
    {"name":"Charging cellular stationary","battery":25,"charging":True,"network":"CELLULAR","motion":"STILL","temp":31,"queue":200},
]

def choose_policy(s):
    if s["temp"] >= 42:
        interval, upload, state = 180, "DEFER_COOL_DOWN", "HOT"
    elif s["charging"]:
        interval = 30 if s["motion"] == "MOVING" else 90
        upload = "UPLOAD_NOW" if s["network"] != "NONE" else "QUEUE"
        state = "CHARGING"
    elif s["battery"] <= 15:
        interval, upload, state = 300, "QUEUE_CRITICAL_BATTERY", "CRITICAL"
    elif s["battery"] <= 20:
        interval = 180 if s["motion"] == "STILL" else 120
        upload = "DEFER_UNTIL_WIFI_OR_CHARGING" if s["network"] == "CELLULAR" else "QUEUE"
        state = "LOW"
    elif s["network"] == "NONE":
        interval, upload, state = (60 if s["motion"] == "MOVING" else 180), "QUEUE_OFFLINE", "NORMAL"
    elif s["network"] == "WIFI":
        interval, upload, state = (30 if s["motion"] == "MOVING" else 90), "UPLOAD_BATCH", "NORMAL"
    else:
        interval, upload, state = (60 if s["motion"] == "MOVING" else 120), "UPLOAD_BATCH_IF_QUEUE_HIGH", "NORMAL"
    return interval, upload, state

def encrypt_record(record):
    nonce = os.urandom(12)
    raw = json.dumps(record, sort_keys=True).encode()
    encrypted = CIPHER.encrypt(nonce, raw, None)
    return nonce + encrypted

def main():
    rows = []
    encrypted_samples = []
    for s in SCENARIOS:
        interval, upload, state = choose_policy(s)
        record = {"record_id": str(uuid.uuid4()), "scenario": s["name"], "battery": s["battery"],
                  "motion": s["motion"], "timestamp": time.time()}
        blob = encrypt_record(record)
        encrypted_samples.append(blob)
        # Transparent illustrative energy model; not a physical measurement.
        sample_cost = 0.002
        radio_cost = 0.018 if upload in ["UPLOAD_NOW", "UPLOAD_BATCH"] else 0.002
        estimated_energy = sample_cost + radio_cost + (0.001 * max(1, s["queue"] // 50))
        rows.append({
            **s, "policy_state": state, "sampling_interval_seconds": interval,
            "upload_action": upload, "estimated_energy_mAh_per_cycle": round(estimated_energy, 5),
            "encrypted_before_queue": True, "authenticated_TLS_required": True,
            "encrypted_record_bytes": len(blob)
        })

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "results" / "scenario_policy_results.csv", index=False)

    # Small validation against an always-on baseline.
    validation = []
    for s in SCENARIOS[:3]:
        interval, upload, state = choose_policy(s)
        policy_samples_per_hour = 3600 / interval
        baseline_samples_per_hour = 3600 / 10
        validation.append({
            "scenario": s["name"], "policy_interval_s": interval,
            "policy_samples_per_hour": round(policy_samples_per_hour, 2),
            "baseline_interval_s": 10, "baseline_samples_per_hour": baseline_samples_per_hour,
            "policy_upload": upload, "policy_state": state
        })
    pd.DataFrame(validation).to_csv(OUT / "results" / "validation.csv", index=False)

    # Scalability experiment: count policy evaluations and queued events.
    scale_rows = []
    for n in [100, 1000, 10000]:
        start = time.perf_counter()
        evaluations = 0
        queued = 0
        for i in range(n):
            s = SCENARIOS[i % len(SCENARIOS)]
            _, action, _ = choose_policy(s)
            evaluations += 1
            if "QUEUE" in action or "DEFER" in action:
                queued += 1
        elapsed = time.perf_counter() - start
        scale_rows.append({"records": n, "policy_evaluations": evaluations,
                           "queued_records": queued, "processing_seconds": elapsed})
    scale_df = pd.DataFrame(scale_rows)
    scale_df.to_csv(OUT / "results" / "scalability.csv", index=False)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(df["name"], df["sampling_interval_seconds"])
    ax.set_ylabel("Sampling interval (seconds)")
    ax.set_title("Adaptive sampling policy by operating condition")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(OUT / "graphs" / "sampling_policy.png", dpi=160)
    plt.show()

    report = """BATTERY-AWARE SECURE FIELD TRACKING
Inputs: battery level, charging state, network, motion, temperature and queued-record count.
Output: sampling interval and upload action.
Objective: deliver useful tracking records per unit of energy while protecting data.

Security:
- Each record is encrypted with AES-GCM before it is queued.
- The demo key is generated in memory for this run. It is NOT Android Keystore persistence.
- Upload is marked as requiring authenticated TLS; no real server transfer is performed.

Validation compares adaptive sampling with an illustrative always-on 10-second baseline.
Scalability counts policy evaluations and queued records at increasing input sizes.
Energy figures are transparent estimates, not measured phone mAh.

Trade-off: emergency real-time mode should override battery-saving intervals, use a justified
foreground tracking mode and accept higher energy use, heat and privacy exposure.
"""
    (OUT / "reports" / "tracking_report.txt").write_text(report, encoding="utf-8")
    print("SCENARIO POLICY RESULTS")
    print(df[["name","policy_state","sampling_interval_seconds","upload_action",
              "estimated_energy_mAh_per_cycle","encrypted_before_queue"]].to_string(index=False))
    print("\nVALIDATION")
    print(pd.DataFrame(validation).to_string(index=False))
    print("\nSCALABILITY")
    print(scale_df.to_string(index=False))
    print("\n" + report)

if __name__ == "__main__":
    main()
