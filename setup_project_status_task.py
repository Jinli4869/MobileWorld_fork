#!/usr/bin/env python3
"""Set up Mattermost backend and data for the project status report task."""

import sys
import os
import time

# Add the src directory to the path
sys.path.insert(0, '/home/jinli/Project/MobileWorld_fork/src')

from mobile_world.runtime.app_helpers import mattermost
from mobile_world.runtime.app_helpers.fossify_calendar import insert_calendar_event
from mobile_world.runtime.app_helpers.system import time_sync_to_now
from datetime import datetime, timedelta

def _compute_dates() -> dict:
    """Compute dynamic dates for the status report task."""
    today = datetime.now().date()
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    base_date = today + timedelta(days=days_until_monday)

    return {
        "sprint_start": base_date.strftime("%Y-%m-%d"),
        "sprint_end": (base_date + timedelta(days=13)).strftime("%Y-%m-%d"),
        "milestone_1": (base_date + timedelta(days=4)).strftime("%Y-%m-%d"),  # On track
        "milestone_2": (base_date + timedelta(days=7)).strftime("%Y-%m-%d"),  # At risk
        "milestone_3": (base_date + timedelta(days=11)).strftime("%Y-%m-%d"),  # Blocked
        "review_date": (base_date + timedelta(days=6)).strftime("%Y-%m-%d"),
    }

def setup_mattermost():
    """Set up Mattermost backend and create channels with status updates."""
    
    print("=" * 60)
    print("Mattermost Project Status Report Task Setup")
    print("=" * 60)
    
    print("\n[1/5] Starting Mattermost backend...")
    if not mattermost.start_mattermost_backend():
        print("✗ Failed to start Mattermost backend")
        return False
    
    print("✓ Mattermost backend started successfully")
    
    # Login as Sam
    print("\n[2/5] Logging in as Sam and creating channels...")
    cli = mattermost.MattermostCLI()
    if not cli.login(mattermost.SAM_ACCOUNT["username"], mattermost.SAM_ACCOUNT["password"]):
        print("✗ Failed to login as Sam")
        return False
    
    print("✓ Logged in as Sam")
    
    # Create team channels
    channels = [
        ("backend-team", "Backend Team"),
        ("frontend-team", "Frontend Team"),
        ("qa-team", "QA Team"),
        ("project-sync", "Project Sync"),
    ]
    
    dates = _compute_dates()
    print(f"\nUsing dates:")
    print(f"  milestone_1 (on-track): {dates['milestone_1']}")
    print(f"  milestone_2 (at-risk): {dates['milestone_2']}")
    print(f"  milestone_3 (blocked): {dates['milestone_3']}")
    
    for channel_name, display_name in channels:
        cli.create_channel(
            team=mattermost.TEAM_NAME,
            channel_name=channel_name,
            display_name=display_name,
            private=False,
        )
        print(f"✓ Created channel: {channel_name}")
        
        cli.add_users_to_channel(
            team=mattermost.TEAM_NAME,
            channel=channel_name,
            users=["sam.oneill@neuralforge.ai", "harry.kong@neuralforge.ai"],
        )
        print(f"✓ Added users to {channel_name}")
    
    # Backend team updates - mix of statuses
    print("\n[3/5] Posting status updates to channels...")
    cli.send_message(
        team=mattermost.TEAM_NAME,
        channel="backend-team",
        message=(
            f"Status Update - Authentication Module: on-track\n"
            f"Expected completion: {dates['milestone_1']}\n"
            "All unit tests passing, ready for integration."
        ),
    )
    print("✓ Posted Authentication Module status (on-track)")
    
    cli.send_message(
        team=mattermost.TEAM_NAME,
        channel="backend-team",
        message=(
            "Status Update - Payment Integration: blocked\n"
            "Waiting on third-party API credentials from vendor.\n"
            "Cannot proceed until this is resolved."
        ),
    )
    print("✓ Posted Payment Integration status (blocked)")
    
    # Frontend team updates
    cli.send_message(
        team=mattermost.TEAM_NAME,
        channel="frontend-team",
        message=(
            f"Status Update - Dashboard UI: at-risk\n"
            f"Original target: {dates['milestone_2']}\n"
            "Design changes requested, may need 2 extra days."
        ),
    )
    print("✓ Posted Dashboard UI status (at-risk)")
    
    cli.send_message(
        team=mattermost.TEAM_NAME,
        channel="frontend-team",
        message=(
            f"Status Update - API Gateway Setup: on-track\n"
            f"Completion target: {dates['milestone_1']}\n"
            "Routing configured, testing in progress."
        ),
    )
    print("✓ Posted API Gateway Setup status (on-track)")
    
    # QA team updates
    cli.send_message(
        team=mattermost.TEAM_NAME,
        channel="qa-team",
        message=(
            "Status Update - Performance Testing: at-risk\n"
            "Load testing environment not yet provisioned.\n"
            "No calendar milestone assigned yet."
        ),
    )
    print("✓ Posted Performance Testing status (at-risk)")
    
    cli.send_message(
        team=mattermost.TEAM_NAME,
        channel="qa-team",
        message=(
            "Status Update - Security Audit: blocked\n"
            "Dependency on Payment Integration completion.\n"
            "Cannot start until payment module is ready."
        ),
    )
    print("✓ Posted Security Audit status (blocked)")
    
    # Create calendar milestones for on-track items only
    print("\n[4/5] Creating calendar milestones...")
    insert_calendar_event(
        title="Authentication Module Complete",
        start_time=f"{dates['milestone_1']} 09:00:00",
        end_time=f"{dates['milestone_1']} 10:00:00",
        description="Backend authentication milestone",
    )
    print("✓ Created calendar event: Authentication Module Complete")
    
    insert_calendar_event(
        title="API Gateway Launch",
        start_time=f"{dates['milestone_1']} 14:00:00",
        end_time=f"{dates['milestone_1']} 15:00:00",
        description="Gateway setup completion",
    )
    print("✓ Created calendar event: API Gateway Launch")
    
    cli.logout()
    
    # Sync time
    print("\n[5/5] Syncing time...")
    if not time_sync_to_now():
        print("✗ Failed to sync time")
        return False
    print("✓ Time synced")
    
    print("\n" + "=" * 60)
    print("Setup complete!")
    print("=" * 60)
    print("\nExpected items:")
    print("  ON_TRACK: Authentication Module, API Gateway Setup")
    print("  AT_RISK: Dashboard UI, Performance Testing")
    print("  BLOCKED: Payment Integration, Security Audit")
    print("\nLogin credentials for Mattermost app:")
    print("  Email: harry.kong@neuralforge.ai")
    print("  Password: password")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    success = setup_mattermost()
    if not success:
        sys.exit(1)
