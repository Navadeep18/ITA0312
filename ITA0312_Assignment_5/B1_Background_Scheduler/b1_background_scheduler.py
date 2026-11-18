from pathlib import Path
import copy
import csv
import json

OUT = Path("B1_Background_Scheduler")
(OUT / "results").mkdir(parents=True, exist_ok=True)
(OUT / "logs").mkdir(parents=True, exist_ok=True)

def make_items(n=12):
    return [
        {
            "id": i,
            "priority": 0 if i in (2, 6, 9) else (1 if i % 2 else 2),
            "arrival": i // 2,
            "done": False,
            "cancelled": False,
            "done_at": None
        }
        for i in range(n)
    ]

def environment(scenario, tick):
    if scenario == "good":
        return {"battery": 80, "network": "good", "doze": False, "permission": True}
    if scenario == "lowdoze":
        return {
            "battery": max(8, 60 - 4 * tick),
            "network": "poor" if tick % 3 else "good",
            "doze": tick >= 5,
            "permission": True
        }
    if scenario == "permission":
        return {"battery": 70, "network": "good", "doze": False, "permission": tick < 4}
    raise ValueError("Unknown scenario: " + scenario)

def feasible(item, env, tick):
    if not env["permission"]:
        return False
    critical = item["priority"] == 0
    if env["battery"] < (5 if critical else 20):
        return False
    if env["network"] == "none" or (env["network"] == "poor" and not critical):
        return False
    if env["doze"] and not critical and tick % 5 != 0:
        return False
    return True

def run_scheduler(scenario, policy, max_workers=3, total_ticks=20):
    items = make_items()
    deferred = 0
    succeeded = 0
    cancelled = 0
    peak_workers = 0
    decision_log = []

    for tick in range(total_ticks):
        env = environment(scenario, tick)
        pending = [
            item for item in items
            if item["arrival"] <= tick and not item["done"] and not item["cancelled"]
        ]

        if not env["permission"]:
            cancelled_now = 0
            for item in pending:
                item["cancelled"] = True
                cancelled += 1
                cancelled_now += 1
            decision_log.append({
                "tick": tick, **env, "policy": policy,
                "running": 0, "event": "permission_revoked_cancel_pending",
                "cancelled_this_tick": cancelled_now
            })
            continue

        if policy == "FIFO":
            ordered = pending
        elif policy == "PRIORITY":
            ordered = sorted(pending, key=lambda item: (item["priority"], item["arrival"]))
        else:
            raise ValueError("policy must be FIFO or PRIORITY")

        slots = max_workers
        running_now = 0
        deferred_now = 0

        for item in ordered:
            if slots == 0:
                break
            if feasible(item, env, tick):
                item["done"] = True
                item["done_at"] = tick
                succeeded += 1
                running_now += 1
                slots -= 1
            else:
                deferred += 1
                deferred_now += 1
                if policy == "FIFO":
                    slots -= 1

        peak_workers = max(peak_workers, running_now)
        decision_log.append({
            "tick": tick, **env, "policy": policy,
            "running": running_now, "deferred_this_tick": deferred_now,
            "event": "scheduled"
        })

    critical_latencies = []
    for item in items:
        if item["priority"] == 0:
            if item["done"]:
                critical_latencies.append(item["done_at"] - item["arrival"])
            else:
                critical_latencies.append(None)

    backlog = sum(1 for item in items if not item["done"] and not item["cancelled"])
    metrics = {
        "scenario": scenario,
        "policy": policy,
        "enqueued": len(items),
        "deferred_evaluations": deferred,
        "cancelled": cancelled,
        "successful_executions": succeeded,
        "peak_concurrent_workers": peak_workers,
        "final_backlog": backlog,
        "critical_item_latencies": json.dumps(critical_latencies)
    }
    return metrics, decision_log, items

def main():
    results = []
    all_logs = []
    validation = []

    for scenario in ["good", "lowdoze", "permission"]:
        for policy in ["FIFO", "PRIORITY"]:
            metrics, logs, items = run_scheduler(scenario, policy)
            results.append(metrics)
            for row in logs:
                all_logs.append({"scenario": scenario, **row})
            if policy == "PRIORITY":
                validation.append(metrics)

    with open(OUT / "results" / "scheduler_comparison.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    with open(OUT / "logs" / "decision_log.json", "w") as f:
        json.dump(all_logs, f, indent=2)

    with open(OUT / "results" / "validation_scenarios.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(validation[0].keys()))
        writer.writeheader()
        writer.writerows(validation)

    print("B1 – BACKGROUND SCHEDULER")
    for row in results:
        print(row)

    print("\nInterpretation:")
    print("- Good conditions should deliver all 12 records without deferral.")
    print("- Low battery/Doze may leave a safe encrypted backlog; deferral is not data loss.")
    print("- Permission revocation cancels pending work, including critical records.")
    print("- Priority scheduling aims to reduce critical-item latency; it need not maximise total throughput.")
    print("\nSaved CSV results and per-tick decision log in", OUT)

if __name__ == "__main__":
    main()
