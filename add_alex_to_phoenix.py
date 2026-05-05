#!/usr/bin/env python3
"""Add Alex to the Phoenix channel on Mattermost."""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, '/home/jinli/Project/MobileWorld_fork/src')

from mobile_world.runtime.app_helpers import mattermost

def add_alex_to_phoenix():
    """Add Alex to the Phoenix channel."""
    
    print("Starting Mattermost backend...")
    if not mattermost.start_mattermost_backend():
        print("Failed to start Mattermost backend")
        return False
    
    print("Mattermost backend started successfully")
    
    # Login as Sam (admin user)
    cli = mattermost.MattermostCLI()
    if not cli.login(mattermost.SAM_ACCOUNT["username"], mattermost.SAM_ACCOUNT["password"]):
        print("Failed to login as Sam")
        return False
    
    print("Logged in as Sam")
    
    # Add Alex to the Phoenix channel
    success = cli.add_users_to_channel(
        team=mattermost.TEAM_NAME,
        channel="phoenix",
        users=["alex.rivera@neuralforge.ai"],
    )
    
    if success:
        print("Successfully added Alex to the Phoenix channel")
    else:
        print("Failed to add Alex to the Phoenix channel")
    
    cli.logout()
    
    return success

if __name__ == "__main__":
    success = add_alex_to_phoenix()
    if not success:
        sys.exit(1)
