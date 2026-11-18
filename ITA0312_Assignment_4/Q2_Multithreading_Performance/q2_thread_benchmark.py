import os, time, math, statistics, json
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import psutil

OUT = Path("Q2_Multithreading_Performance")
(OUT / "results").mkdir(parents=True, exist_ok=True)
(OUT / "graphs").mkdir(parents=True, exist_ok=True)

def cpu_chunk(bounds):
    start, end = bounds
    total = 0
    for n in range(start, end):
        total += int(math.sqrt(n) * math.sin(n % 100))
    return total

def run_single(total_n, chunks):
    step = total_n // chunks
    bounds = [(i * step, (i + 1) * step if i < chunks - 1 else total_n) for i in range(chunks)]
    t0 = time.perf_counter()
    result = sum(cpu_chunk(b) for b in bounds)
    return time.perf_counter() - t0, result

def run_parallel(total_n, chunks, workers, executor_type):
    step = total_n // chunks
    bounds = [(i * step, (i + 1) * step if i < chunks - 1 else total_n) for i in range(chunks)]
    t0 = time.perf_counter()
    with executor_type(max_workers=workers) as pool:
        result = sum(pool.map(cpu_chunk, bounds))
    return time.perf_counter() - t0, result

def small_task(_=None):
    return sum(i * i for i in range(1000))

def main():
    workers = max(2, min(os.cpu_count() or 2, 4))
    print(f"Runtime CPUs reported: {os.cpu_count()} | workers tested: {workers}")
    rows = []
    process = psutil.Process()
    before_mem = process.memory_info().rss / (1024 * 1024)

    for n in [1_000_000, 3_000_000]:
        single_t, single_result = run_single(n, workers)
        thread_t, thread_result = run_parallel(n, workers * 2, workers, ThreadPoolExecutor)
        process_t, process_result = run_parallel(n, workers * 2, workers, ProcessPoolExecutor)
        rows.extend([
            {"case": f"large_{n}", "mode": "single_process", "seconds": single_t,
             "result": single_result, "workers": 1},
            {"case": f"large_{n}", "mode": "multi_thread", "seconds": thread_t,
             "result": thread_result, "workers": workers},
            {"case": f"large_{n}", "mode": "multi_process", "seconds": process_t,
             "result": process_result, "workers": workers},
        ])

    small_n = 40
    t0 = time.perf_counter()
    s = sum(small_task() for _ in range(small_n))
    single_small = time.perf_counter() - t0
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        p = sum(pool.map(small_task, range(small_n)))
    parallel_small = time.perf_counter() - t0
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        t = sum(pool.map(small_task, range(small_n)))
    thread_small = time.perf_counter() - t0
    rows.extend([
        {"case": "small_overhead", "mode": "single_process", "seconds": single_small,
         "result": s, "workers": 1},
        {"case": "small_overhead", "mode": "multi_thread", "seconds": thread_small,
         "result": t, "workers": workers},
        {"case": "small_overhead", "mode": "multi_process", "seconds": parallel_small,
         "result": p, "workers": workers},
    ])

    after_mem = process.memory_info().rss / (1024 * 1024)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "results" / "benchmark_results.csv", index=False)

    fig, ax = plt.subplots(figsize=(10, 5))
    for mode, group in df.groupby("mode"):
        ax.bar(group["case"] + " " + mode, group["seconds"], label=mode)
    ax.set_ylabel("Elapsed time (seconds)")
    ax.set_title("Single-process vs multi-process workload timing")
    ax.tick_params(axis="x", rotation=25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "graphs" / "execution_time.png", dpi=160)
    plt.show()

    print("\nBENCHMARK RESULTS")
    print(df.to_string(index=False))
    print(f"\nParent process RSS before/after: {before_mem:.2f} MB / {after_mem:.2f} MB")
    print(f"Parent process RSS change: {after_mem-before_mem:.2f} MB")
    print("\nInterpretation:")
    print("- Large CPU-bound work may benefit from multiple processes because processes can use separate CPU cores.")
    print("- Small tasks can become slower when process startup, serialization and coordination dominate.")
    print("- Python process timing is not a direct measurement of Android thread scheduling or big.LITTLE placement.")
    print("- For Android core placement, collect Perfetto or CPU Profiler traces on the device.")

if __name__ == "__main__":
    main()
