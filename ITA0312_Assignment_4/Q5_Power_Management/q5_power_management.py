from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

OUT = Path("Q5_Power_Management")
(OUT / "results").mkdir(parents=True, exist_ok=True)
(OUT / "graphs").mkdir(parents=True, exist_ok=True)
(OUT / "logs").mkdir(parents=True, exist_ok=True)

HOURS = 8
BASE_CPU_MAH_PER_HOUR = 110
RADIO_WAKE_COST_MAH = 0.018

def simulate(mode):
    rows = []
    battery_used = 0.0
    wakeups = 0
    for hour in range(HOURS):
        if mode == "baseline":
            cpu_factor, wakeups_hour, responsiveness = 1.0, 60, "High"
        elif mode == "dvfs":
            cpu_factor, wakeups_hour, responsiveness = 0.72, 60, "Moderate"
        elif mode == "doze":
            cpu_factor, wakeups_hour, responsiveness = 0.45, 8, "Delayed background work"
        elif mode == "batching":
            cpu_factor, wakeups_hour, responsiveness = 0.62, 6, "Uploads delayed to batch window"
        elif mode == "wakelock_conflict":
            cpu_factor, wakeups_hour, responsiveness = 0.92, 60, "Responsive but inefficient"
        else:
            raise ValueError(mode)
        cpu = BASE_CPU_MAH_PER_HOUR * cpu_factor
        radio = wakeups_hour * RADIO_WAKE_COST_MAH
        total = cpu + radio
        battery_used += total
        wakeups += wakeups_hour
        rows.append({
            "hour": hour + 1, "technique": mode, "cpu_estimated_mAh": cpu,
            "radio_estimated_mAh": radio, "total_estimated_mAh": total,
            "wakeups": wakeups_hour, "cumulative_mAh": battery_used,
            "responsiveness": responsiveness
        })
    return rows

def main():
    modes = ["baseline", "dvfs", "doze", "batching", "wakelock_conflict"]
    all_rows = []
    for mode in modes:
        all_rows.extend(simulate(mode))
    df = pd.DataFrame(all_rows)
    df.to_csv(OUT / "results" / "power_simulation.csv", index=False)

    summary = df.groupby("technique").agg(
        total_estimated_mAh=("total_estimated_mAh", "sum"),
        total_wakeups=("wakeups", "sum")
    ).reset_index()
    summary.to_csv(OUT / "results" / "power_summary.csv", index=False)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(summary["technique"], summary["total_estimated_mAh"])
    ax.set_ylabel("Estimated energy (mAh)")
    ax.set_title("Eight-hour power model comparison (simulated)")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    fig.savefig(OUT / "graphs" / "energy_comparison.png", dpi=160)
    plt.show()

    conflict = summary[summary["technique"] == "wakelock_conflict"]["total_estimated_mAh"].iloc[0]
    doze = summary[summary["technique"] == "doze"]["total_estimated_mAh"].iloc[0]
    report = f"""POWER MANAGEMENT EXPERIMENT
Model duration: {HOURS} hours
DVFS: reduces the assumed CPU energy factor while preserving frequent work.
Doze: reduces background wakeups and defers non-urgent work.
Batching: coalesces network activity into fewer radio wakeups.
Stress case: wakelock_conflict keeps the device awake and removes much of the Doze benefit.

Doze estimated energy: {doze:.2f} mAh
Wakelock-conflict estimated energy: {conflict:.2f} mAh

These are model estimates, not physical battery measurements. Actual DVFS frequency, voltage,
Doze state, wakelock duration and radio-active time require Android device instrumentation.
"""
    (OUT / "logs" / "power_interpretation.txt").write_text(report, encoding="utf-8")
    print(summary.to_string(index=False))
    print("\n" + report)
    print("Industry interpretation:")
    print("- Always-on tracking: foreground location service where justified, sensor batching and carefully bounded wake locks.")
    print("- Gaming/media: DVFS and frame pacing matter; background batching has less impact during sustained foreground load.")
    print("- Managed fleet: prefer OS-supported schedulers and policies that work across supported OS versions.")

if __name__ == "__main__":
    main()
