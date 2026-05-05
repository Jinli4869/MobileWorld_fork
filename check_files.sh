#!/bin/bash
MW_ADB="/home/jinli/Project/MobileWorld_fork/traj_logs/nanobot_skill_reuse_gui_only_all_rerun_5_calls/ReviewPaperEmailTask/.nanobot_runtime/ReviewPaperEmailTask-0/bin/mw_adb"

echo "=== Searching for review*.pdf in Documents ==="
$MW_ADB shell "find /sdcard/Documents -name 'review*.pdf' 2>/dev/null"

echo ""
echo "=== Listing Documents directory ==="
$MW_ADB shell "ls -la /sdcard/Documents/"

echo ""
echo "=== Checking if paper folder exists ==="
$MW_ADB shell "ls -la /sdcard/Documents/paper/ 2>/dev/null || echo 'paper folder does not exist'"
