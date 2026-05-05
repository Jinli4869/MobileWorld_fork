#!/usr/bin/env python3
"""Set up Mattermost backend and users for the reading group task."""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, '/home/jinli/Project/MobileWorld_fork/src')

from mobile_world.runtime.app_helpers import mattermost

def setup_mattermost():
    """Set up Mattermost backend and create the reading channel with Sam's message."""
    
    print("Starting Mattermost backend...")
    if not mattermost.start_mattermost_backend():
        print("Failed to start Mattermost backend")
        return False
    
    print("Mattermost backend started successfully")
    
    # Login as Sam
    cli = mattermost.MattermostCLI()
    if not cli.login(mattermost.SAM_ACCOUNT["username"], mattermost.SAM_ACCOUNT["password"]):
        print("Failed to login as Sam")
        return False
    
    print("Logged in as Sam")
    
    # Create the reading channel
    cli.create_channel(
        team=mattermost.TEAM_NAME,
        channel_name="reading",
        display_name="Reading Group",
        private=False,
        purpose="Reading group",
        header="Reading group",
    )
    print("Created reading channel")
    
    # Add users to the channel
    cli.add_users_to_channel(
        team=mattermost.TEAM_NAME,
        channel="reading",
        users=["sam.oneill@neuralforge.ai", "harry.kong@neuralforge.ai"],
    )
    print("Added users to channel")
    
    # Send Sam's message
    cli.send_message(
        team=mattermost.TEAM_NAME,
        channel="reading",
        message="Welcome to the reading group! For today's reading, please read the Qwen3-vl paper and share your thoughts @harry. Post here the arxiv link of the paper. Btw, what's their MMMU_Pro score for their best model?",
    )
    print("Sent Sam's message")
    
    cli.logout()
    
    print("Mattermost setup complete!")
    return True

if __name__ == "__main__":
    success = setup_mattermost()
    if not success:
        sys.exit(1)
