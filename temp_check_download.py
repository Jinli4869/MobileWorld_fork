#!/usr/bin/env python3
import subprocess
import sys

mw_adb = "/home/jinli/Project/MobileWorld_fork/traj_logs/nanobot_skill_reuse_gui_only_all_rerun_5_calls/InvoiceReceiptCopyTask/.nanobot_runtime/InvoiceReceiptCopyTask-0/bin/mw_adb"

# Check Download folder
result = subprocess.run([mw_adb, "shell", "ls -la /sdcard/Download/"], capture_output=True, text=True)
print("=== Download folder ===")
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)

# Check Finance folder
result = subprocess.run([mw_adb, "shell", "ls -la /sdcard/Finance/"], capture_output=True, text=True)
print("\n=== Finance folder ===")
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)

# Check Finance/invoice folder
result = subprocess.run([mw_adb, "shell", "ls -la /sdcard/Finance/invoice/"], capture_output=True, text=True)
print("\n=== Finance/invoice folder ===")
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)
