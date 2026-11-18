from pathlib import Path
import csv
import itertools
import json

OUT = Path("B4_Multimedia_Decision")
(OUT / "results").mkdir(parents=True, exist_ok=True)
(OUT / "reports").mkdir(parents=True, exist_ok=True)

# Assignment appendix model: (quality level, encode energy J, encode time s)
RESOLUTIONS = {
    480: (1, 4, 2),
    720: (2, 9, 4),
    1080: (3, 20, 9)
}
BITRATE_LEVEL = {1: 0, 2.5: 1, 5: 2}

DEVICES = [
    {"id": "D1", "label": "flagship Wi-Fi", "cpu": 1.0, "bandwidth": 10.0,
     "network": "wifi", "battery": 80, "capacity_j": 41580},
    {"id": "D2", "label": "mid-range LTE", "cpu": 0.8, "bandwidth": 6.0,
     "network": "cellular", "battery": 55, "capacity_j": 41580},
    {"id": "D3", "label": "low-end slow uplink", "cpu": 0.7, "bandwidth": 1.5,
     "network": "cellular", "battery": 60, "capacity_j": 41580},
    {"id": "D4", "label": "low battery Wi-Fi", "cpu": 1.0, "bandwidth": 10.0,
     "network": "wifi", "battery": 12, "capacity_j": 41580},
    {"id": "D5", "label": "flagship slow uplink", "cpu": 1.0, "bandwidth": 2.0,
     "network": "cellular", "battery": 65, "capacity_j": 41580}
]

def evaluate(resolution, bitrate, device):
    quality_level, encode_j, encode_s = RESOLUTIONS[resolution]
    cpu = device["cpu"]
    encode_energy = encode_j * (1 + 0.1 * bitrate) / cpu
    encode_time = encode_s / cpu
    clip_size_mb = bitrate * 10 / 8
    upload_time = clip_size_mb * 8 / device["bandwidth"]
    radio_power_factor = 1.0 if device["network"] == "wifi" else 2.5
    total_energy = encode_energy + upload_time * radio_power_factor
    total_time = encode_time + upload_time
    quality_score = quality_level + 0.5 * BITRATE_LEVEL[bitrate]
    battery_impact = total_energy / device["capacity_j"] * 100
    return total_energy, total_time, quality_score, battery_impact

def heuristic(device):
    if device["battery"] < 20:
        return 480, 1, "defer to Wi-Fi/charging"
    feasible_resolutions = [
        res for res in RESOLUTIONS
        if RESOLUTIONS[res][2] / device["cpu"] <= 6
    ]
    resolution = max(feasible_resolutions) if feasible_resolutions else 480
    feasible_bitrates = [b for b in BITRATE_LEVEL if b <= 0.6 * device["bandwidth"]]
    bitrate = max(feasible_bitrates) if feasible_bitrates else 1
    upload = "now" if device["bandwidth"] >= 2 and device["battery"] >= 20 else "defer to Wi-Fi"
    return resolution, bitrate, upload

def objective(resolution, bitrate, device):
    energy, duration, quality, battery_impact = evaluate(resolution, bitrate, device)
    return energy + 0.5 * duration + 8 * (4 - quality)

def exhaustive(device):
    candidates = []
    for resolution, bitrate in itertools.product(RESOLUTIONS, BITRATE_LEVEL):
        candidates.append((objective(resolution, bitrate, device), resolution, bitrate))
    return min(candidates)

def main():
    rows = []
    for device in DEVICES:
        resolution, bitrate, upload = heuristic(device)
        energy, duration, quality, impact = evaluate(resolution, bitrate, device)
        h_cost = objective(resolution, bitrate, device)
        best_cost, best_resolution, best_bitrate = exhaustive(device)
        rows.append({
            "device": device["id"], "profile": device["label"],
            "battery_percent": device["battery"], "bandwidth_mbps": device["bandwidth"],
            "heuristic_resolution": resolution, "heuristic_bitrate_mbps": bitrate,
            "estimated_energy_j": round(energy, 2), "estimated_time_s": round(duration, 2),
            "battery_impact_percent": round(impact, 3), "upload_timing": upload,
            "heuristic_cost": round(h_cost, 2),
            "exhaustive_best_resolution": best_resolution,
            "exhaustive_best_bitrate_mbps": best_bitrate,
            "exhaustive_best_cost": round(best_cost, 2),
            "matches_exhaustive": abs(h_cost - best_cost) < 1e-9
        })

    with open(OUT / "results" / "device_decisions.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    report = """B4 – MULTIMEDIA FRAMEWORK ENGINEERING DECISION NOTE

Selection rule:
1. If battery is below 20%, select 480p/1 Mbps and defer upload.
2. Otherwise select the highest resolution whose estimated encode time is <= 6 seconds.
3. Select the largest bitrate in {1, 2.5, 5} Mbps not exceeding 60% of measured bandwidth.
4. Upload now only if bandwidth >= 2 Mbps and battery >= 20%; otherwise defer.

Why not exhaustive at production scale:
Resolution x bitrate x codec x profile x upload timing creates a large search space. Evaluating
every option for thousands of changing device/network profiles consumes compute and makes
the decision stale.

Guarantee:
The heuristic is not globally optimal. It applies simple safety rules, but the device comparisons
show that independent thresholds can miss interactions between energy, quality, CPU and network.

Advantage:
A few comparisons produce a fast decision, avoiding a full search for every clip.

When exact/cloud-assisted methods are appropriate:
Premium or long clips, periodic offline tuning from fleet telemetry, or server-side transcoding for
devices with weak encoding capability.

Monitor before production:
Upload success rate, p95 encode/upload time, battery drain per clip by device class, thermal
throttling, quality complaints, deferred-upload share, and A/B results against a fixed-quality baseline.

All energy and time values in this experiment are outputs of the assignment's simplified model,
not physical phone measurements.
"""
    (OUT / "reports" / "engineering_decision_note.txt").write_text(report)
    print("B4 – MULTIMEDIA DEVICE DECISIONS")
    for row in rows:
        print(row)
    print("\n" + report)
    print("Saved CSV and decision note in", OUT)

if __name__ == "__main__":
    main()
