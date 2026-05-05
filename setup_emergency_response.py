#!/usr/bin/env python3
"""Set up Mattermost emergency-response channel for the visual instruction task."""

import sys
import os
import time

# Add the src directory to the path
sys.path.insert(0, '/home/jinli/Project/MobileWorld_fork/src')

from mobile_world.runtime.app_helpers import mattermost
from mobile_world.runtime.app_helpers.mattermost import DEFAULT_PASSWORD, USERS
from urllib.parse import quote

CHANNEL_NAME = "emergency-response"

# Data to be embedded in images
CONTACTS_DATA = [
    {"name": "Dr. Smith", "phone": "555-1010"},
    {"name": "Safety Officer", "phone": "555-2020"},
]

ALARMS_DATA = [
    {"label": "Morning Shift", "time_str": "08:00 AM", "hour": 8, "minute": 0},
    {"label": "Evening Shift", "time_str": "08:00 PM", "hour": 20, "minute": 0},
]

def _generate_image_url(title: str, lines: list[str]) -> str:
    """Generate a placehold.co URL containing the text."""
    full_text = f"{title}\n" + "\n".join(lines)
    encoded_text = quote(full_text)
    return f"https://placehold.co/600x400/EEE/31343C/png?text={encoded_text}"

def setup_emergency_response():
    """Set up Mattermost emergency-response channel."""
    
    print("Starting Mattermost backend...")
    if not mattermost.start_mattermost_backend():
        print("Failed to start Mattermost backend")
        return False
    
    print("Mattermost backend started successfully")
    time.sleep(5)
    
    # Login as alex
    cli = mattermost.MattermostCLI()
    if not cli.login(USERS["alex"], DEFAULT_PASSWORD):
        print("Failed to login as alex")
        return False
    
    print("Logged in as alex")
    
    # Create the emergency-response channel
    cli.create_channel(
        team=mattermost.TEAM_NAME,
        channel_name=CHANNEL_NAME,
        display_name="Emergency Response",
        private=False,
        purpose="Coordination for emergency protocols",
    )
    print("Created emergency-response channel")
    
    cli.add_users_to_channel(
        team=mattermost.TEAM_NAME,
        channel=CHANNEL_NAME,
        users=["harry.kong@neuralforge.ai", USERS["sofia"]],
    )
    print("Added users to channel")
    
    # Post text context
    cli.send_message(
        team=mattermost.TEAM_NAME,
        channel=CHANNEL_NAME,
        message=(
            "**URGENT UPDATE**\n\n"
            "The central server is down, so I'm posting the manual override details here. "
            "Please update your local devices immediately."
        ),
    )
    print("Posted urgent update message")
    
    # Post Contacts Image
    contact_lines = [f"{c['name']}: {c['phone']}" for c in CONTACTS_DATA]
    contacts_url = _generate_image_url("EMERGENCY CONTACTS", contact_lines)
    
    cli.send_message(
        team=mattermost.TEAM_NAME,
        channel=CHANNEL_NAME,
        message=(
            f"Here is the updated contact list for the response team:\n\n"
            f"![Emergency Contacts]({contacts_url})"
        ),
    )
    print("Posted Emergency Contacts image")
    
    # Post Alarms Image
    alarm_lines = [f"{a['label']}: {a['time_str']}" for a in ALARMS_DATA]
    alarms_url = _generate_image_url("SHIFT SCHEDULE", alarm_lines)
    
    cli.send_message(
        team=mattermost.TEAM_NAME,
        channel=CHANNEL_NAME,
        message=(
            f"And here are the mandatory check-in times for the manual shifts:\n\n"
            f"![Shift Schedule]({alarms_url})"
        ),
    )
    print("Posted Shift Schedule image")
    
    # Add some noise/conversation
    cli.logout()
    cli.login(USERS["sofia"], DEFAULT_PASSWORD)
    cli.send_message(
        team=mattermost.TEAM_NAME,
        channel=CHANNEL_NAME,
        message="Got it. Is the Safety Officer number reachable 24/7?",
    )
    print("Posted Sofia's message")
    
    cli.logout()
    cli.login(USERS["alex"], DEFAULT_PASSWORD)
    cli.send_message(
        team=mattermost.TEAM_NAME,
        channel=CHANNEL_NAME,
        message="Yes, use that number for all critical incidents.",
    )
    print("Posted Alex's response")
    
    cli.logout()
    
    print("Mattermost emergency-response setup complete!")
    return True

if __name__ == "__main__":
    success = setup_emergency_response()
    if not success:
        sys.exit(1)
