"""
send_waf_logs.py
────────────────
Push WAF logs from azure_waf.csv (AzureDiagnostics format)
to Microsoft Sentinel CustomTable_CL via
Azure Monitor Logs Ingestion API.

Automatically map AzureDiagnostics columns (clientIp_s, ruleSetType_s, ...)
to CustomTable_CL schema (ClientIp, RuleSetType, ...).

No AMA required, no Logstash required.
Prerequisites: DCE + DCR + App Registration (Service Principal).

Usage:
    python send_waf_logs.py          # Test the first 3 rows
    python send_waf_logs.py --all    # Send all logs
"""

import pandas as pd
import requests
import json
import time
import sys
import os
from datetime import datetime, timezone

# ╔══════════════════════════════════════════════════════════╗
# ║                   CONFIGURATION                          ║
# ╚══════════════════════════════════════════════════════════╝

# --- Azure AD / Entra ID ---
TENANT_ID     = ""
CLIENT_ID     = ""
CLIENT_SECRET = ""

# --- Data Collection Endpoint (DCE) ---
DCE_ENDPOINT = ""

# --- Data Collection Rule (DCR) ---
DCR_IMMUTABLE_ID = ""
STREAM_NAME      = ""

# --- Input Data ---
CSV_FILE = "azure_waf.csv"

# --- Batch config ---
MAX_PAYLOAD_BYTES = 1_040_000  # Keep under 1MB (1,048,576), leave buffer
BATCH_SIZE        = 50        # Smaller batch to avoid exceeding 1MB
DELAY_BETWEEN_BATCHES = 0.5   # Seconds between each batch

# --- Debug log ---
DEBUG_LOG_FILE = "debug_log.txt"


# ╔══════════════════════════════════════════════════════════╗
# ║                   LOGGER                                 ║
# ╚══════════════════════════════════════════════════════════╝

_log_file = None

def init_log():
    """Initialize debug log file."""
    global _log_file
    _log_file = open(DEBUG_LOG_FILE, "w", encoding="utf-8")
    log(f"=== Debug Log Started: {datetime.now().isoformat()} ===")
    log(f"DCE: {DCE_ENDPOINT}")
    log(f"DCR: {DCR_IMMUTABLE_ID}")
    log(f"Stream: {STREAM_NAME}")
    log(f"CSV: {CSV_FILE}")
    log("")

def log(msg):
    """Write to console + debug log."""
    print(msg)
    if _log_file:
        _log_file.write(msg + "\n")
        _log_file.flush()

def close_log():
    global _log_file
    if _log_file:
        log(f"\n=== Debug Log Ended: {datetime.now().isoformat()} ===")
        _log_file.close()
        _log_file = None


# ╔══════════════════════════════════════════════════════════╗
# ║            GET ACCESS TOKEN (OAuth2)                     ║
# ╚══════════════════════════════════════════════════════════╝

def get_access_token():
    """Get Bearer token from Microsoft Entra ID."""
    token_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"

    payload = {
        "grant_type":    "client_credentials",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope":         "https://monitor.azure.com/.default"
    }

    log("[*] Getting access token from Entra ID...")
    log(f"    Token URL: {token_url}")

    resp = requests.post(token_url, data=payload, timeout=30)

    log(f"    HTTP {resp.status_code}")

    if resp.status_code != 200:
        log(f"[✗] Error getting token!")
        log(f"    Response: {resp.text}")
        sys.exit(1)

    token_data = resp.json()
    token = token_data.get("access_token")
    expires_in = token_data.get("expires_in", "?")
    log(f"[✓] Token retrieved successfully. Expires in {expires_in}s.")
    log(f"    Token (start): {token[:30]}...")
    return token


# ╔══════════════════════════════════════════════════════════╗
# ║           SEND BATCH LOG TO INGESTION API                ║
# ╚══════════════════════════════════════════════════════════╝

def send_logs(token, logs_batch, batch_label=""):
    """
    POST a batch (list of dicts) to Logs Ingestion API.
    Returns (success: bool, status_code: int, response_text: str)
    """
    url = (
        f"{DCE_ENDPOINT}"
        f"/dataCollectionRules/{DCR_IMMUTABLE_ID}"
        f"/streams/{STREAM_NAME}"
        f"?api-version=2023-01-01"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }

    # Calculate payload size
    body = json.dumps(logs_batch, ensure_ascii=False)
    body_bytes = len(body.encode("utf-8"))

    log(f"    URL: {url}")
    log(f"    Payload size: {body_bytes:,} bytes ({body_bytes/1024:.1f} KB)")
    log(f"    Records: {len(logs_batch)}")

    if body_bytes > MAX_PAYLOAD_BYTES:
        log(f"    [⚠] Payload ({body_bytes:,}) exceeds limit ({MAX_PAYLOAD_BYTES:,}). Will be divided into smaller batches.")
        return False, 413, "Payload too large - need smaller batch"

    resp = requests.post(url, headers=headers, data=body.encode("utf-8"), timeout=60)

    log(f"    HTTP {resp.status_code} | Response: {resp.text[:500] if resp.text else '(empty)'}")

    if resp.status_code in (200, 204):
        return True, resp.status_code, ""
    else:
        return False, resp.status_code, resp.text[:500]


# ╔══════════════════════════════════════════════════════════╗
# ║              PREPARE DATA FROM CSV                       ║
# ╚══════════════════════════════════════════════════════════╝

def parse_time_generated(raw_time):
    """
    Convert TimeGenerated from CSV format to ISO 8601 UTC.
    CSV format: "4/3/2026, 10:03:48.000 AM"
    Output:     "2026-04-03T10:03:48Z"
    """
    if pd.isna(raw_time) or not raw_time:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    raw = str(raw_time).strip()

    # Try common formats
    formats = [
        "%m/%d/%Y, %I:%M:%S.%f %p",   # 4/3/2026, 10:03:48.000 AM
        "%m/%d/%Y, %H:%M:%S.%f",       # 4/3/2026, 10:03:48.000
        "%m/%d/%Y, %I:%M:%S %p",       # 4/3/2026, 10:03:48 AM
        "%Y-%m-%dT%H:%M:%SZ",          # ISO 8601 (already correct)
        "%Y-%m-%dT%H:%M:%S.%fZ",       # ISO 8601 with milliseconds
        "%Y-%m-%d %H:%M:%S",           # 2026-04-03 10:03:48
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue

    # If unable to parse, return original
    return raw


def safe_str(value, max_len=None):
    """Convert value to string, remove NaN."""
    if pd.isna(value) or value is None:
        return ""
    s = str(value)
    if s == "nan":
        return ""
    if max_len:
        s = s[:max_len]
    return s


def prepare_log_entry(row):
    """
    Convert 1 CSV row (query_data.csv format) into JSON object
    matching CustomTable_CL schema.
    """
    original_time = parse_time_generated(row.get("TimeGenerated [UTC]"))
    entry = {
        "TimeGenerated":              original_time,
        "EventTime":                  original_time,
        "ClientIp":                   safe_str(row.get("ClientIp")),
        "Hostname":                   safe_str(row.get("Hostname")),
        "RequestUri":                 safe_str(row.get("RequestUri"), max_len=500),
        "Uri":                        safe_str(row.get("Uri"), max_len=500),
        "Message":                    safe_str(row.get("Message")),
        "DetailedMessage":            safe_str(row.get("DetailedMessage")),
        "RuleId":                     safe_str(row.get("RuleId")),
        "RuleSetType":                safe_str(row.get("RuleSetType")),
        "RuleSetVersion":             safe_str(row.get("RuleSetVersion")),
        "Action":                     safe_str(row.get("Action")),
        "OperationName":              safe_str(row.get("OperationName")),
        "InstanceId":                 safe_str(row.get("InstanceId")),
        "TransactionId":              safe_str(row.get("TransactionId")),
        "PolicyId":                   safe_str(row.get("PolicyId")),
        "PolicyScope":                safe_str(row.get("PolicyScope")),
        "OriginalRequestUriWithArgs": safe_str(row.get("OriginalRequestUriWithArgs"), max_len=500),
        "FileDetails":                safe_str(row.get("FileDetails")),
        "LineDetails":                safe_str(row.get("LineDetails")),
        "DetailedData":               safe_str(row.get("DetailedData")),
    }

    # Remove empty fields
    return {k: v for k, v in entry.items() if v}


def prepare_azure_waf_entry(row):
    """
    Convert 1 CSV row from azure_waf.csv (AzureDiagnostics format)
    to JSON object matching CustomTable_CL schema.

    Mapping AzureDiagnostics → CustomTable_CL:
      timeStamp_t [UTC]             → TimeGenerated, EventTime
      clientIp_s                    → ClientIp
      hostname_s                    → Hostname
      requestUri_s                  → RequestUri
      hostname_s + requestUri_s     → Uri
      Message                       → Message
      details_message_s             → DetailedMessage
      ruleId_s                      → RuleId
      ruleSetType_s                 → RuleSetType
      ruleSetVersion_s              → RuleSetVersion
      action_s                      → Action
      OperationName                 → OperationName
      instanceId_s                  → InstanceId
      transactionId_g               → TransactionId
      policyId_s                    → PolicyId
      policyScope_s                 → PolicyScope
      originalRequestUriWithArgs_s  → OriginalRequestUriWithArgs
      details_file_s                → FileDetails
      details_line_s                → LineDetails
      details_data_s                → DetailedData
    """
    # Get timestamp from timeStamp_t [UTC] (actual WAF event time)
    # Fallback to TimeGenerated [UTC] if timeStamp_t is missing
    event_time_raw = row.get("timeStamp_t [UTC]")
    if pd.isna(event_time_raw) or not event_time_raw:
        event_time_raw = row.get("TimeGenerated [UTC]")
    original_time = parse_time_generated(event_time_raw)

    # Create Uri = hostname + requestUri (same as query_data.csv)
    hostname = safe_str(row.get("hostname_s"))
    request_uri = safe_str(row.get("requestUri_s"), max_len=500)
    uri = f"{hostname}{request_uri}" if hostname and request_uri else request_uri

    entry = {
        "TimeGenerated":              original_time,
        "EventTime":                  original_time,
        "ClientIp":                   safe_str(row.get("clientIp_s")),
        "Hostname":                   hostname,
        "RequestUri":                 request_uri,
        "Uri":                        safe_str(uri, max_len=500),
        "Message":                    safe_str(row.get("Message")),
        "DetailedMessage":            safe_str(row.get("details_message_s")),
        "RuleId":                     safe_str(row.get("ruleId_s")),
        "RuleSetType":                safe_str(row.get("ruleSetType_s")),
        "RuleSetVersion":             safe_str(row.get("ruleSetVersion_s")),
        "Action":                     safe_str(row.get("action_s")),
        "OperationName":              safe_str(row.get("OperationName")),
        "InstanceId":                 safe_str(row.get("instanceId_s")),
        "TransactionId":              safe_str(row.get("transactionId_g")),
        "PolicyId":                   safe_str(row.get("policyId_s")),
        "PolicyScope":                safe_str(row.get("policyScope_s")),
        "OriginalRequestUriWithArgs": safe_str(row.get("originalRequestUriWithArgs_s"), max_len=500),
        "FileDetails":                safe_str(row.get("details_file_s")),
        "LineDetails":                safe_str(row.get("details_line_s")),
        "DetailedData":               safe_str(row.get("details_data_s")),
    }

    # Remove empty fields
    return {k: v for k, v in entry.items() if v}


def smart_batch(all_logs):
    """
    Divide logs into batches ensuring each batch is < 1MB.
    If 1 batch exceeds, automatically reduce size.
    """
    batches = []
    current_batch = []
    current_size = 2  # for [ ] brackets

    for entry in all_logs:
        entry_json = json.dumps(entry, ensure_ascii=False)
        entry_size = len(entry_json.encode("utf-8")) + 1  # +1 for comma

        if current_size + entry_size > MAX_PAYLOAD_BYTES and current_batch:
            batches.append(current_batch)
            current_batch = []
            current_size = 2

        current_batch.append(entry)
        current_size += entry_size

    if current_batch:
        batches.append(current_batch)

    return batches


# ╔══════════════════════════════════════════════════════════╗
# ║              AUTO-DETECT CSV FORMAT                      ║
# ╚══════════════════════════════════════════════════════════╝

def detect_csv_format(df):
    """
    Automatically detect if CSV is AzureDiagnostics (azure_waf.csv)
    or query_data.csv format based on column names.
    Returns: 'azure_diag' or 'query_data'
    """
    cols = set(df.columns)
    # Signs of AzureDiagnostics: has columns with suffix _s, _g, _t
    azure_diag_markers = {"clientIp_s", "ruleSetType_s", "details_message_s", "action_s"}
    if azure_diag_markers.issubset(cols):
        return "azure_diag"
    return "query_data"


def prepare_entry_auto(row, csv_format):
    """Choose appropriate prepare function based on CSV format."""
    if csv_format == "azure_diag":
        return prepare_azure_waf_entry(row)
    else:
        return prepare_log_entry(row)


# ╔══════════════════════════════════════════════════════════╗
# ║              TEST FIRST 3 ROWS                           ║
# ╚══════════════════════════════════════════════════════════╝

def test_send():
    """Send first 3 rows to test connection + schema."""
    init_log()
    log("=" * 60)
    log("   🧪 TEST MODE: Send first 3 rows")
    log("=" * 60)

    # 1. Token
    token = get_access_token()

    # 2. Read CSV
    log(f"\n[*] Reading data from {CSV_FILE}...")
    df = pd.read_csv(CSV_FILE)
    csv_format = detect_csv_format(df)
    log(f"[*] Detected CSV format: {csv_format}")

    # Only take first 3 rows
    df = df.head(3)

    log(f"[*] Taken {len(df)} rows for test.")
    log(f"[*] Columns: {list(df.columns)}")

    # 3. Prepare data
    test_logs = []
    for i, (_, row) in enumerate(df.iterrows()):
        entry = prepare_entry_auto(row, csv_format)
        test_logs.append(entry)
        log(f"\n--- Record {i+1} ---")
        log(json.dumps(entry, indent=2, ensure_ascii=False))

    if not test_logs:
        log("\n[⚠️] No data in CSV to test!")
        close_log()
        return

    # 4. Send
    log(f"\n[*] Sending {len(test_logs)} records...")
    ok, status, resp_text = send_logs(token, test_logs, batch_label="TEST")

    if ok:
        log(f"\n[🎉] TEST SUCCESSFUL! HTTP {status}")
        log("    → Data has been pushed to Sentinel CustomTable_CL.")
    else:
        log(f"\n[✗] TEST FAILED! HTTP {status}")
        log(f"    Response: {resp_text}")

    log(f"\n[*] Debug log saved at: {os.path.abspath(DEBUG_LOG_FILE)}")
    close_log()


# ╔══════════════════════════════════════════════════════════╗
# ║                  SEND ALL                                ║
# ╚══════════════════════════════════════════════════════════╝

def send_all():
    """Send all logs from CSV to CustomTable_CL."""
    init_log()
    log("=" * 60)
    log(f"   {CSV_FILE} → Microsoft Sentinel CustomTable_CL")
    log("=" * 60)

    # 1. Token
    token = get_access_token()

    # 2. Read CSV
    log(f"\n[*] Reading {CSV_FILE}...")
    df = pd.read_csv(CSV_FILE)
    total_raw = len(df)
    csv_format = detect_csv_format(df)
    log(f"[*] Detected CSV format: {csv_format}")
    log(f"[*] Total {total_raw:,} log rows.\n")

    if total_raw == 0:
        log("\n[⚠️] CSV empty! Terminating.")
        close_log()
        return

    # 3. Prepare data
    all_logs = []
    for _, row in df.iterrows():
        entry = prepare_entry_auto(row, csv_format)
        if entry:
            all_logs.append(entry)

    log(f"[*] Prepared {len(all_logs):,} valid records.")

    # 4. Smart batching (each batch < 1MB)
    batches = smart_batch(all_logs)
    log(f"[*] Divided into {len(batches)} batches (auto-sized under 1MB).\n")

    # 5. Send
    success_count = 0
    fail_count = 0

    for i, batch in enumerate(batches):
        batch_num = i + 1
        log(f"  → Batch {batch_num}/{len(batches)} ({len(batch)} records)...")

        ok, status, resp_text = send_logs(token, batch, batch_label=f"Batch-{batch_num}")

        if ok:
            success_count += len(batch)
            log(f"    ✓ OK")
        else:
            fail_count += len(batch)
            log(f"    ✗ FAILED")

        # Delay between batches
        if batch_num < len(batches):
            time.sleep(DELAY_BETWEEN_BATCHES)

    # 6. Results
    log("\n" + "=" * 60)
    log(f"  ✓ Success: {success_count:,} records")
    log(f"  ✗ Failed:   {fail_count:,} records")
    log("=" * 60)

    if fail_count == 0:
        log(f"\n[🎉] All logs from {CSV_FILE} have been pushed to Sentinel CustomTable_CL successfully!")
    else:
        log("\n[⚠️] An error occurred. Check debug_log.txt for details.")

    log(f"\n[*] Debug log saved at: {os.path.abspath(DEBUG_LOG_FILE)}")
    close_log()


# ╔══════════════════════════════════════════════════════════╗
# ║                       MAIN                               ║
# ╚══════════════════════════════════════════════════════════╝

if __name__ == "__main__":
    if "--all" in sys.argv:
        send_all()
    else:
        test_send()