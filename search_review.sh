#!/bin/bash
MW_ADB="/home/jinli/Project/MobileWorld_fork/traj_logs/nanobot_skill_reuse_gui_only_all_rerun_5_calls/ReviewPaperEmailTask/.nanobot_runtime/ReviewPaperEmailTask-0/bin/mw_adb"
$MW_ADB shell "find /sdcard/Documents -name 'review*.pdf' 2>/dev/null"
