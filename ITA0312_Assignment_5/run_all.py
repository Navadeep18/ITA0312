import subprocess
import sys

programs = [
    "B1_Background_Scheduler/b1_background_scheduler.py",
    "B2_Adversarial_Workload/b2_adversarial_workload.py",
    "B3_Exact_vs_Approximate_UI/b3_feed_optimization.py",
    "B4_Multimedia_Decision/b4_multimedia_decision.py"
]

for program in programs:
    print("\n" + "=" * 75)
    print("RUNNING:", program)
    print("=" * 75)
    result = subprocess.run([sys.executable, program])
    if result.returncode != 0:
        raise SystemExit(f"Program failed: {program}")
