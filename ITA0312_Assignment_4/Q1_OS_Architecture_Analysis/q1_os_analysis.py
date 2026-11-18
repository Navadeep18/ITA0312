import os, subprocess, platform, json, time
from pathlib import Path

OUT = Path("Q1_OS_Architecture_Analysis/results")
OUT.mkdir(parents=True, exist_ok=True)

ANDROID_COMMANDS = [
    ("Kernel", "adb shell uname -a"),
    ("Process list", "adb shell ps -A"),
    ("Zygote processes", "adb shell ps -A | grep zygote"),
    ("Memory summary", "adb shell dumpsys meminfo"),
    ("Activity processes", "adb shell dumpsys activity processes"),
    ("Binder devices", "adb shell ls -l /dev/binder /dev/vndbinder"),
    ("App package compile state", "adb shell cmd package compile -m speed-profile -f YOUR.PACKAGE.NAME"),
]

ARCHITECTURE = {
    "Android": [
        ("Applications", "Activities, services, receivers and providers"),
        ("Application framework", "ActivityManager, PackageManager, WindowManager, PowerManager; Binder APIs"),
        ("ART", "DEX execution, JIT/AOT compilation, garbage collection and JNI"),
        ("Native libraries", "Bionic, SQLite, graphics, media and cryptography libraries"),
        ("HAL", "Stable interfaces between framework services and vendor hardware"),
        ("Linux kernel", "Scheduler, virtual memory, Binder driver, networking, security and device drivers"),
        ("Hardware", "CPU, memory, display, modem, sensors and storage"),
    ],
    "iOS": [
        ("Cocoa Touch", "UIKit, application lifecycle and user interaction"),
        ("Media", "Core Graphics, Core Animation, AVFoundation and Metal"),
        ("Core Services", "Foundation, Core Data, networking and other system services"),
        ("Core OS", "Darwin/XNU, security, file system, networking and low-level services"),
        ("Hardware", "Apple SoC, memory, display, radios and sensors"),
    ],
}

def run_command(label, command):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=20)
        return {
            "label": label, "command": command, "returncode": result.returncode,
            "stdout": result.stdout[:12000], "stderr": result.stderr[:3000]
        }
    except Exception as exc:
        return {"label": label, "command": command, "error": str(exc)}

def main():
    report = []
    report.append("MOBILE OS ARCHITECTURE ANALYSIS")
    report.append("=" * 60)
    report.append(f"Host OS: {platform.platform()}")
    report.append("Colab host is not an Android device; host information is not Android evidence.")
    report.append("\nLAYER MODEL")
    for os_name, layers in ARCHITECTURE.items():
        report.append(f"\n{os_name}")
        for layer, role in layers:
            report.append(f"- {layer}: {role}")

    report.append("\nANDROID LIVE EVIDENCE")
    adb_check = run_command("ADB availability", "adb version")
    report.append(json.dumps(adb_check, indent=2))
    if adb_check.get("returncode") == 0:
        for label, command in ANDROID_COMMANDS:
            item = run_command(label, command)
            report.append("\n" + json.dumps(item, indent=2))
    else:
        report.append("ADB is unavailable or no Android device is attached.")
        report.append("Run the listed commands on a computer with Android Platform Tools and USB debugging.")

    report.append("""
PROCESS / IPC INTERPRETATION
- Android app processes are commonly created by zygote; the Linux kernel schedules and isolates them.
- Binder is the principal Android framework IPC mechanism; /dev/binder is useful supporting evidence.
- iOS applications are launched under launchd and commonly use XPC/Mach messaging for system IPC.
- Android lifecycle evidence should be captured from Activity/Service callbacks in a test application.
- iOS lifecycle evidence requires an iOS device/simulator and Xcode tooling; Colab cannot collect it.

BOUNDARY TEST
Rotate the device while a form contains unsaved input, then background and restore the app.
Expected check: state is restored from saved instance state or persistent storage; transient UI state
must not be assumed to survive process death.
""")
    path = OUT / "q1_os_analysis_report.txt"
    path.write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report[:28]))
    print(f"\nFull report saved to: {path}")

if __name__ == "__main__":
    main()
