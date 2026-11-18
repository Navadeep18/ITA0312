from pathlib import Path
import random
import csv
import matplotlib.pyplot as plt

OUT = Path("B3_Exact_vs_Approximate_UI")
(OUT / "results").mkdir(parents=True, exist_ok=True)
(OUT / "graphs").mkdir(parents=True, exist_ok=True)
(OUT / "reports").mkdir(parents=True, exist_ok=True)

def make_instance(seed, count, levels, cache_sizes, lam):
    rng = random.Random(seed)
    workload = [rng.choice([2, 3, 4, 6, 8]) for _ in range(count)]
    return workload, levels, cache_sizes, lam

def cost(quality, cache, workload, lam):
    frame_drops = 0.0
    energy = 0.0
    n = len(workload)
    for i, weight in enumerate(workload):
        hit_rate = min(1.0, cache / (1 + (i * 7) % 6))
        frame_time = weight * quality * (1.6 - 0.6 * hit_rate)
        if frame_time > 16:
            frame_drops += (frame_time - 16) / 4
        energy += quality * quality * (1 - 0.5 * hit_rate) + 0.15 * cache * cache
    return frame_drops + lam * energy + n * 0.6 / quality

def exact_search(workload, levels, cache_sizes, lam):
    best = None
    configurations_evaluated = 0
    item_evaluations = 0
    for quality in range(1, levels + 1):
        for cache in range(1, cache_sizes + 1):
            configurations_evaluated += 1
            item_evaluations += len(workload)
            value = cost(quality, cache, workload, lam)
            candidate = (value, quality, cache)
            if best is None or candidate < best:
                best = candidate
    return best, configurations_evaluated, item_evaluations

def greedy_search(workload, levels, cache_sizes, lam, start=None):
    quality, cache = start or (min(2, levels), min(2, cache_sizes))
    current = cost(quality, cache, workload, lam)
    evaluations = 1
    item_evaluations = len(workload)
    quality_changes = 0
    cache_evictions = 0
    path = [(quality, cache, round(current, 4))]

    while True:
        neighbours = [
            (quality + dq, cache + dc)
            for dq, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]
            if 1 <= quality + dq <= levels and 1 <= cache + dc <= cache_sizes
        ]
        scored = []
        for q, c in neighbours:
            scored.append((cost(q, c, workload, lam), q, c))
            evaluations += 1
            item_evaluations += len(workload)

        value, new_quality, new_cache = min(scored)
        if value < current - 1e-9:
            if new_quality != quality:
                quality_changes += 1
            if new_cache < cache:
                cache_evictions += cache - new_cache
            quality, cache, current = new_quality, new_cache, value
            path.append((quality, cache, round(current, 4)))
        else:
            break

    return (current, quality, cache), evaluations, item_evaluations, quality_changes, cache_evictions, path

def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

def main():
    small_rows = []
    for seed, lam in [(1, 0.3), (2, 1.0), (3, 0.05)]:
        workload, levels, cache_sizes, lam = make_instance(seed, 10, 4, 4, lam)
        exact, exact_evals, exact_items = exact_search(workload, levels, cache_sizes, lam)
        approx, approx_evals, approx_items, q_changes, evictions, path = greedy_search(
            workload, levels, cache_sizes, lam
        )
        small_rows.append({
            "seed": seed, "lambda": lam, "exact_cost": round(exact[0], 4),
            "exact_quality": exact[1], "exact_cache": exact[2],
            "approx_cost": round(approx[0], 4), "approx_quality": approx[1],
            "approx_cache": approx[2], "match": abs(exact[0] - approx[0]) < 1e-9,
            "exact_configurations": exact_evals, "approx_evaluations": approx_evals,
            "quality_changes": q_changes, "cache_evictions": evictions
        })

    # Deliberate counterexample required by B3.2: seed 2, lambda 0.1.
    workload, levels, cache_sizes, lam = make_instance(2, 10, 4, 4, 0.1)
    exact, exact_evals, exact_items = exact_search(workload, levels, cache_sizes, lam)
    approx, approx_evals, approx_items, q_changes, evictions, path = greedy_search(
        workload, levels, cache_sizes, lam
    )
    counterexample = {
        "seed": 2, "lambda": 0.1,
        "exact_cost": round(exact[0], 4), "exact_quality": exact[1], "exact_cache": exact[2],
        "approx_cost": round(approx[0], 4), "approx_quality": approx[1], "approx_cache": approx[2],
        "path": str(path), "evaluations": approx_evals
    }

    scaling_rows = []
    for count, levels, cache_sizes in [(50, 4, 4), (200, 8, 8), (1000, 16, 16)]:
        workload, levels, cache_sizes, lam = make_instance(7, count, levels, cache_sizes, 0.3)
        exact, exact_evals, exact_items = exact_search(workload, levels, cache_sizes, lam)
        approx, approx_evals, approx_items, q_changes, evictions, path = greedy_search(
            workload, levels, cache_sizes, lam
        )
        scaling_rows.append({
            "items": count, "quality_levels": levels, "cache_sizes": cache_sizes,
            "exact_configurations_evaluated": exact_evals,
            "exact_item_evaluations": exact_items,
            "adaptive_configurations_evaluated": approx_evals,
            "adaptive_item_evaluations": approx_items,
            "quality_changes": q_changes, "cache_evictions": evictions,
            "adaptive_to_exact_cost_ratio": round(approx[0] / exact[0], 4)
        })

    write_csv(OUT / "results" / "small_instance_comparison.csv", small_rows)
    write_csv(OUT / "results" / "scalability.csv", scaling_rows)
    write_csv(OUT / "results" / "counterexample.csv", [counterexample])

    fig, ax = plt.subplots(figsize=(8, 4))
    x = [str(row["items"]) for row in scaling_rows]
    ax.plot(x, [row["exact_item_evaluations"] for row in scaling_rows], marker="o", label="Exact")
    ax.plot(x, [row["adaptive_item_evaluations"] for row in scaling_rows], marker="o", label="Adaptive")
    ax.set_xlabel("Number of feed items")
    ax.set_ylabel("Item-cost evaluations")
    ax.set_title("Exact vs adaptive evaluation work")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "graphs" / "evaluation_scalability.png", dpi=160)
    plt.show()

    report = [
        "B3 – EXACT VS APPROXIMATE FEED OPTIMISATION",
        "",
        "Small-instance comparison:",
        str(small_rows),
        "",
        "Counterexample:",
        str(counterexample),
        "",
        "Adaptive path:",
        "The greedy search changes one coordinate at a time and stops when no orthogonal neighbour improves cost.",
        "For seed 2 and lambda 0.1 it moves from (2,2) to (2,3), then stops at a local minimum.",
        "The exact optimum is (1,1), which requires a diagonal combination of changes.",
        "",
        "Scaling:",
        str(scaling_rows),
        "",
        "Trade-off:",
        "Exact search guarantees the best configuration within the enumerated finite search space, but evaluates every configuration.",
        "Greedy search evaluates fewer configurations and can react quickly, but has no global optimality guarantee.",
        "A live scrolling feed can accept a near-optimal adaptive configuration to protect frame responsiveness."
    ]
    (OUT / "reports" / "feed_optimization_report.txt").write_text("\n".join(report))
    print("\nB3 – SMALL INSTANCES")
    for row in small_rows:
        print(row)
    print("\nCOUNTEREXAMPLE")
    print(counterexample)
    print("\nSCALABILITY")
    for row in scaling_rows:
        print(row)
    print("\nSaved CSVs, graph and report in", OUT)

if __name__ == "__main__":
    main()
