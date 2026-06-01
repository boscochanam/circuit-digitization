#!/usr/bin/env python3
"""Check mapping experiment v2 status — for cron monitoring."""
import json
from pathlib import Path
from datetime import datetime

LOG_FILE = Path("/home/claw/circuit-digitization/output/mapping_experiment_v2/status.log")
RESULTS_FILE = Path("/home/claw/circuit-digitization/output/mapping_experiment_v2/mapping_v2_summary.json")

# Check if experiment is still running
import subprocess
result = subprocess.run(["pgrep", "-f", "mapping_experiment_v2"], capture_output=True, text=True)
running = result.returncode == 0
pids = result.stdout.strip()

lines = []

if LOG_FILE.exists():
    log_content = LOG_FILE.read_text()
    log_lines = [l.strip() for l in log_content.split("\n") if l.strip()]
    
    # Last 15 log lines
    recent = log_lines[-15:]
    lines.append("📋 RECENT LOG:")
    lines.extend(recent)
else:
    lines.append("⚠️ No log file found yet")

lines.append("")
lines.append(f"🔄 Process: {'RUNNING (PID: ' + pids + ')' if running else '❌ NOT RUNNING'}")

if RESULTS_FILE.exists():
    lines.append("")
    lines.append("📊 RESULTS AVAILABLE — check mapping_v2_summary.json")
    try:
        data = json.loads(RESULTS_FILE.read_text())
        best = data.get("best_method", "?")
        best_acc = data.get("best_endpoint_accuracy", 0)
        lines.append(f"🏆 Best method: {best} (EP accuracy: {best_acc:.4f})")
    except:
        pass

lines.append("")
lines.append(f"⏰ Check time: {datetime.now().strftime('%H:%M:%S')}")

print("\n".join(lines))
