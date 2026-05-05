#!/usr/bin/env python3
"""Complete setup for Mattermost Reading Group Task including ADB login."""

import sys
import os
import subprocess
import time

# Add the src directory to the path
sys.path.insert(0, '/home/jinli/Project/MobileWorld_fork/src')

from mobile_world.runtime.app_helpers import mattermost

ADB_CMD = "/home/jinli/Project/MobileWorld_fork/traj_logs/nanobot_skill_reuse_gui_only_all_rerun_5_calls/MattermostReadingGroupTask/.nanobot_runtime/MattermostReadingGroupTask-0/bin/mw_adb"

def run_adb(command: str) -> str:
    """Run an ADB command and return the output."""
    full_cmd = f"{ADB_CMD} {command}"
    result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
    return result.stdout + result.stderr

def setup_mattermost():
    """Set up Mattermost backend and create the reading channel with Sam's message."""
    
    print("=" * 60)
    print("Mattermost Reading Group Task Setup")
    print("=" * 60)
    
    print("\n[1/4] Starting Mattermost backend...")
    if not mattermost.start_mattermost_backend():
        print("✗ Failed to start Mattermost backend")
        return False
    
    print("✓ Mattermost backend started successfully")
    
    # Login as Sam
    print("\n[2/4] Logging in as Sam and creating reading channel...")
    cli = mattermost.MattermostCLI()
    if not cli.login(mattermost.SAM_ACCOUNT["username"], mattermost.SAM_ACCOUNT["password"]):
        print("✗ Failed to login as Sam")
        return False
    
    print("✓ Logged in as Sam")
    
    # Create the reading channel
    cli.create_channel(
        team=mattermost.TEAM_NAME,
        channel_name="reading",
        display_name="Reading Group",
        private=False,
        purpose="Reading group",
        header="Reading group",
    )
    print("✓ Created reading channel")
    
    # Add users to the channel
    cli.add_users_to_channel(
        team=mattermost.TEAM_NAME,
        channel="reading",
        users=["sam.oneill@neuralforge.ai", "harry.kong@neuralforge.ai"],
    )
    print("✓ Added users to channel")
    
    # Send Sam's message
    cli.send_message(
        team=mattermost.TEAM_NAME,
        channel="reading",
        message="Welcome to the reading group! For today's reading, please read the Qwen3-vl paper and share your thoughts @harry. Post here the arxiv link of the paper. Btw, what's their MMMU_Pro score for their best model?",
    )
    print("✓ Sent Sam's message")
    
    cli.logout()
    
    # Try to log in via ADB
    print("\n[3/4] Attempting to log in via ADB...")
    
    # Open Mattermost app
    run_adb("shell am start -n com.mattermost.rnbeta/.MainActivity")
    time.sleep(3)
    
    # Try to input credentials via ADB input commands
    print("Attempting to enter credentials via ADB...")
    
    # Clear and enter email
    run_adb("shell input text 'harry.kong@neuralforge.ai'")
    time.sleep(1)
    
    # Tab to password field (may not work reliably)
    run_adb("shell input keyevent 61")
    time.sleep(1)
    
    # Enter password
    run_adb("shell input text 'password'")
    time.sleep(1)
    
    # Press Enter to login
    run_adb("shell input keyevent 66")
    time.sleep(3)
    
    print("✓ ADB login attempt completed")
    
    print("\n[4/4] Setup complete!")
    print("\n" + "=" * 60)
    print("NEXT STEPS:")
    print("=" * 60)
    print("1. Check the Mattermost app on the emulator")
    print("2. If not logged in, manually enter:")
    print("   Email: harry.kong@neuralforge.ai")
    print("   Password: password")
    print("3. Once logged in, the agent can proceed with the task")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    success = setup_mattermost()
    if not success:
        sys.exit(1)
