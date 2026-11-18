from pathlib import Path
import random
import csv
import json

OUT = Path("B2_Adversarial_Workload")
(OUT / "results").mkdir(parents=True, exist_ok=True)
(OUT / "logs").mkdir(parents=True, exist_ok=True)

def make_workload(n=40, seed=1):
    rng = random.Random(seed)
    records = []
    for i in range(n):
        records.append({
            "id": i,
            "priority": 0 if rng.random() < 0.15 else rng.choice([1, 2]),
            "arrival": i // 4,
            "done": False,
            "cancelled": False
        })
    return records

def env_easy(tick):
    return {"battery": 70, "network": "good", "doze": False, "permission": True}

def env_adversarial(tick):
    feasible_window = tick % 8 < 3
    return {
        "battery": 70 if feasible_window else 15,
        "network": "good" if feasible_window else "poor",
        "doze": not feasible_window,
        "permission": True
    }

def feasible(record, env, tick):
    if not env["permission"]:
        return False
    critical = record["priority"] == 0
    if env["battery"] < (5 if critical else 20):
        return False
    if env["network"] == "none" or (env["network"] == "poor" and not critical):
        return False
    if env["doze"] and not critical and tick % 5 != 0:
        return False
    return True

def run_workload(records, environment_fn, max_workers=3, total_ticks=40, label=""):
    deferred = 0
    succeeded = 0
    logs = []
    for tick in range(total_ticks):
        env = environment_fn(tick)
        pending = [r for r in records if r["arrival"] <= tick and not r["done"] and not r["cancelled"]]
        ordered = sorted(pending, key=lambda r: (r["priority"], r["arrival"]))
        slots = max_workers
        running = 0
        deferred_now = 0

        for record in ordered:
            if slots == 0:
                break
            if feasible(record, env, tick):
                record["done"] = True
                succeeded += 1
                running += 1
                slots -= 1
            else:
                deferred += 1
                deferred_now += 1

        logs.append({
            "workload": label, "tick": tick, **env,
            "pending": len(pending), "running": running,
            "deferred_this_tick": deferred_now
        })

    backlog = sum(1 for r in records if not r["done"])
    return {
        "workload": label,
        "records": len(records),
        "processed_evaluations": sum(x["pending"] for x in logs),
        "deferrals": deferred,
        "successful_deliveries": succeeded,
        "backlog": backlog
    }, logs

def main():
    # Same generated records, count, arrival pattern and priority distribution.
    # Independent copies ensure one run cannot affect the other.
    base = make_workload(40, seed=1)
    easy, easy_log = run_workload([dict(r) for r in base], env_easy, label="A_easy")
    difficult, difficult_log = run_workload([dict(r) for r in base], env_adversarial, label="B_adversarial")

    rows = [easy, difficult]
    with open(OUT / "results" / "workload_comparison.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    with open(OUT / "logs" / "workload_decisions.json", "w") as f:
        json.dump(easy_log + difficult_log, f, indent=2)

    report = """B2 – ADVERSARIAL WORKLOAD INVESTIGATION

Prediction before execution:
Workload B is expected to require more scheduling evaluations because records arrive during
repeated poor-network, low-battery and Doze periods. The same pending records are rechecked
until a feasible window opens.

Workload A has good connectivity and 70% battery throughout, so few or no records should
be deferred.

Interpretation:
The input size is 40 records in both cases. Effort differs because the alignment between arrival
times and feasible execution windows differs. The difficult workload causes repeated constraint
checks and deferred scheduling attempts. Record count alone is therefore not a sufficient measure
of computational or energy cost.

These are simulated scheduler decisions, not physical radio or battery measurements.
"""
    (OUT / "reports.txt").write_text(report)
    print("B2 – WORKLOAD RESULTS")
    for row in rows:
        print(row)
    print("\n" + report)
    print("Saved results and decision log in", OUT)

if __name__ == "__main__":
    main()
