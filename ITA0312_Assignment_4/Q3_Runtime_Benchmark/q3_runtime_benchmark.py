import os, time, gc, json, subprocess, platform, tracemalloc
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

OUT = Path("Q3_Runtime_Benchmark")
for folder in ["results", "graphs", "logs"]:
    (OUT / folder).mkdir(parents=True, exist_ok=True)

LEAK_BUCKET = []

def cpu_work(n=1_200_000):
    total = 0
    for i in range(1, n):
        total += (i * i) % 997
    return total

def allocation_work(count=250_000):
    return [{"id": i, "payload": "mobile-runtime-" + str(i)} for i in range(count)]

def list_work(count=100_000):
    data = [f"Patient record {i}" for i in range(count)]
    return [x for x in data if int(x.rsplit(" ", 1)[1]) % 3 == 0]

def timed(fn, *args):
    start = time.perf_counter()
    value = fn(*args)
    return time.perf_counter() - start, value

def adb(command):
    try:
        p = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=20)
        return {"command": command, "returncode": p.returncode,
                "stdout": p.stdout[:6000], "stderr": p.stderr[:2000]}
    except Exception as e:
        return {"command": command, "error": str(e)}

def main():
    print("Python runtime:", platform.python_version(), "| platform:", platform.platform())
    cold_start, _ = timed(lambda: cpu_work(100_000))
    warm_times = []
    for _ in range(5):
        elapsed, _ = timed(cpu_work)
        warm_times.append(elapsed)

    tracemalloc.start()
    gc_before = gc.get_count()
    alloc_time, objects = timed(allocation_work)
    current, peak = tracemalloc.get_traced_memory()
    del objects
    gc.collect()
    gc_after = gc.get_count()
    list_time, filtered = timed(list_work)
    del filtered
    current_after, peak_after = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Reachable memory-retention demonstration; bounded so it is safe in Colab.
    for i in range(8):
        LEAK_BUCKET.append(bytearray(1_000_000))
    leak_bytes = sum(len(x) for x in LEAK_BUCKET)
    LEAK_BUCKET.clear()
    gc.collect()

    rows = [
        {"workload": "CPU loop", "seconds": statistics_mean(warm_times), "detail": "5 warm iterations"},
        {"workload": "Object allocation", "seconds": alloc_time, "detail": "250,000 objects"},
        {"workload": "List filtering", "seconds": list_time, "detail": "100,000 rows"},
    ]
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "results" / "python_runtime_results.csv", index=False)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(df["workload"], df["seconds"])
    ax.set_ylabel("Seconds")
    ax.set_title("Python runtime workload benchmark (not ART)")
    fig.tight_layout()
    fig.savefig(OUT / "graphs" / "runtime_workloads.png", dpi=160)
    plt.show()

    report = {
        "runtime": platform.python_version(),
        "cold_start_proxy_seconds": cold_start,
        "warm_cpu_seconds": warm_times,
        "allocation_seconds": alloc_time,
        "list_rendering_proxy_seconds": list_time,
        "tracemalloc_current_bytes": current,
        "tracemalloc_peak_bytes": peak,
        "tracemalloc_after_cleanup_bytes": current_after,
        "gc_count_before": gc_before,
        "gc_count_after": gc_after,
        "bounded_retained_bytes_before_release": leak_bytes,
        "adb_evidence": [
            adb("adb shell cmd package compile -m verify -f YOUR.PACKAGE.NAME"),
            adb("adb shell cmd package compile -m speed-profile -f YOUR.PACKAGE.NAME"),
            adb("adb logcat -d -s art:D"),
            adb("adb shell dumpsys meminfo YOUR.PACKAGE.NAME"),
        ],
    }
    (OUT / "logs" / "runtime_report.json").write_text(json.dumps(report, indent=2))
    print("\nRESULTS")
    print(df.to_string(index=False))
    print(f"Cold-start proxy: {cold_start:.6f}s")
    print(f"Allocation peak traced memory: {peak / (1024*1024):.2f} MB")
    print(f"Bounded retained memory before release: {leak_bytes / (1024*1024):.2f} MB")
    print("\nIMPORTANT: These are Python/Colab results. They do not measure Android ART, ART compilation filters, Android GC pauses, or Android UI rendering.")
    print("Use the saved ADB commands on a connected Android device for those measurements.")

def statistics_mean(values):
    return sum(values) / len(values)

if __name__ == "__main__":
    main()
