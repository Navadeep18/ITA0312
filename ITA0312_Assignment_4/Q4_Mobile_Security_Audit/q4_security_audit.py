import json
from pathlib import Path
import pandas as pd

OUT = Path("Q4_Mobile_Security_Audit")
(OUT / "results").mkdir(parents=True, exist_ok=True)
(OUT / "reports").mkdir(parents=True, exist_ok=True)

CONFIG = {
    "permissions": ["CAMERA", "ACCESS_FINE_LOCATION"],
    "data_stores": {
        "auth_token": "EncryptedSharedPreferences + Android Keystore",
        "patient_database": "Encrypted SQLite",
        "temporary_exports": "Private app files directory",
        "key_material": "Android Keystore"
    },
    "network_endpoints": [
        {"url": "https://api.example.org/patients", "protocol": "HTTPS/TLS"},
        {"url": "http://legacy.example.org/telemetry", "protocol": "HTTP"}
    ],
    "components": [
        {"name": "PatientHomeActivity", "exported": False},
        {"name": "PatientDetailActivity", "exported": True}
    ],
    "signing": "Release APK signed with a protected release key",
    "backup": "Sensitive database excluded from cloud backup"
}

THREATS = [
    ("Spoofing", "Stolen authentication token", "Encrypted token storage; short-lived access token; server-side revocation", "Token may be exposed on a rooted or unlocked device", "Auth token"),
    ("Tampering", "Modified application package", "APK signing and signature verification; verified boot supports platform integrity", "Compromised signing key or rooted OS", "Application package"),
    ("Repudiation", "User denies changing a patient record", "Server-side audit trail with timestamp and authenticated user identity", "A compromised server or stolen account can undermine attribution", "Audit log"),
    ("Information Disclosure", "Local database copied from device", "App sandbox, encrypted database and Keystore-protected key", "Data visible while app is unlocked or OS is compromised", "Patient database"),
    ("Denial of Service", "Repeated requests exhaust API resources", "Rate limiting, request quotas and bounded client retries", "Distributed abuse can still affect availability", "REST API"),
    ("Elevation of Privilege", "Malicious app launches an exported internal activity", "Set internal activity exported=false; validate caller and deep-link inputs", "Publicly intended components still require input validation", "Activity"),
    ("Information Disclosure", "Network observer reads traffic", "TLS certificate validation; reject cleartext traffic", "Compromised endpoint or device trust store", "API traffic"),
    ("Spoofing", "Fake camera/location permission use", "Request runtime permission only when feature is used; explain purpose", "User can grant permission without understanding downstream use", "Camera/location")
]

def audit(config):
    rows = []
    for category, threat, mitigation, residual, asset in THREATS:
        result = "Blocked"
        reason = "Configured control is present in the design model."
        if asset == "API traffic" and any(x["protocol"] == "HTTP" for x in config["network_endpoints"]):
            result = "Exposed"
            reason = "At least one endpoint uses cleartext HTTP."
        if asset == "Activity":
            exported = any(c["name"] == "PatientDetailActivity" and c["exported"] for c in config["components"])
            if exported:
                result = "Partially Blocked"
                reason = "Component is exported; external invocation may be possible. Add authorization and intent validation."
        if asset == "Patient database" and "Encrypted" not in config["data_stores"]["patient_database"]:
            result = "Exposed"
            reason = "Database encryption is not specified."
        if asset == "Auth token" and "Keystore" not in config["data_stores"]["auth_token"]:
            result = "Exposed"
            reason = "Token storage is not protected by Keystore-backed encryption."
        rows.append({
            "STRIDE": category, "Threat": threat, "Asset": asset,
            "Attack vector": threat, "Mechanism applied": mitigation,
            "Decision": result, "Residual risk": residual, "Reason": reason
        })
    return pd.DataFrame(rows)

def main():
    df = audit(CONFIG)
    df.to_csv(OUT / "results" / "security_decisions.csv", index=False)

    # Deliberately weaken one control: enable cleartext endpoint and exported activity.
    weakened = json.loads(json.dumps(CONFIG))
    weakened["data_stores"]["auth_token"] = "Plain SharedPreferences"
    weakened["network_endpoints"].append({"url": "http://attacker.example.org/collect", "protocol": "HTTP"})
    weakened["components"][1]["exported"] = True
    weakened_df = audit(weakened)
    weakened_df.to_csv(OUT / "results" / "weakened_control_decisions.csv", index=False)

    verdict = "PASS" if not (df["Decision"] == "Exposed").any() and not (df["Decision"] == "Partially Blocked").any() else "NEEDS REMEDIATION"
    report = [
        "MOBILE APPLICATION SECURITY AUDIT",
        "=" * 55,
        f"Initial verdict: {verdict}",
        "\nInitial decisions:",
        df[["Asset", "Threat", "Mechanism applied", "Decision", "Reason"]].to_string(index=False),
        "\nWeakened-control experiment:",
        weakened_df[["Asset", "Decision", "Reason"]].to_string(index=False),
        "\nIncident challenge:",
        "A third-party SDK sending a device identifier over HTTP exposes the identifier to observers on the network.",
        "Sandboxing limits access to local app data but does not prevent the app itself from transmitting data.",
        "Detect using static endpoint inspection, proxy/network capture in an authorised test, and runtime network logs.",
        "Remediation: remove the HTTP endpoint, require TLS certificate validation, minimise identifiers and audit SDK traffic.",
        "\nEngineering extension:",
        "Biometric login should bind key use to user authentication where supported. BYOD/work-profile mode requires separate managed data, policy enforcement, key attestation where available, and remote wipe of managed data."
    ]
    (OUT / "reports" / "security_audit_report.txt").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))
    print(f"\nSaved: {OUT}/results and {OUT}/reports")

if __name__ == "__main__":
    main()
