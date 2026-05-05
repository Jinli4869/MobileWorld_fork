#!/usr/bin/env python3
"""Set up Mattermost backend and customer-feedback channel for the analysis task."""

import sys
sys.path.insert(0, '/home/jinli/Project/MobileWorld_fork/src')

from mobile_world.runtime.app_helpers import mattermost

def setup_customer_feedback():
    """Set up Mattermost backend and create the customer-feedback channel with messages."""
    
    print("=" * 60)
    print("Mattermost Customer Feedback Task Setup")
    print("=" * 60)
    
    print("\n[1/3] Starting Mattermost backend...")
    if not mattermost.start_mattermost_backend():
        print("✗ Failed to start Mattermost backend")
        return False
    
    print("✓ Mattermost backend started successfully")
    
    # Login as admin
    print("\n[2/3] Logging in as admin and creating customer-feedback channel...")
    cli = mattermost.MattermostCLI()
    if not cli.login(mattermost.ADMIN_ACCOUNT["username"], mattermost.ADMIN_ACCOUNT["password"]):
        print("✗ Failed to login as admin")
        return False
    
    print("✓ Logged in as admin")
    
    # Create the customer-feedback channel
    cli.create_channel(
        team=mattermost.TEAM_NAME,
        channel_name="customer-feedback",
        display_name="Customer Feedback",
        private=False,
        purpose="Customer feedback and bug reports",
        header="Customer Feedback Channel",
    )
    print("✓ Created customer-feedback channel")
    
    # Add users to the channel
    cli.add_users_to_channel(
        team=mattermost.TEAM_NAME,
        channel="customer-feedback",
        users=["sam.oneill@neuralforge.ai", "harry.kong@neuralforge.ai", "admin@test.com"],
    )
    print("✓ Added users to channel")
    
    # Send sample customer feedback messages (mix of positive and negative)
    print("\n[3/3] Adding sample customer feedback messages...")
    
    feedback_messages = [
        "Great update! The new UI is much cleaner and easier to navigate. Love it!",
        "BUG: App crashes every time I try to upload a photo. This has been happening for 3 days now. Very frustrating!",
        "The customer support team was very helpful. Issue resolved quickly.",
        "ISSUE: Login keeps failing even with correct password. Had to reset 5 times today.",
        "Feature request: Would love to see dark mode added in the next release.",
        "COMPLAINT: The app is extremely slow on my device. Takes forever to load messages.",
        "Thanks for the quick response on my previous ticket!",
        "BUG REPORT: Notifications are not working at all. Missing important messages.",
        "The new search feature is amazing! Found what I needed instantly.",
        "ISSUE: Cannot attach files larger than 5MB. This is a major limitation for our team.",
        "Very disappointed with the recent update. Many features are broken.",
        "COMPLAINT: The app drains my battery very quickly. Please optimize!",
    ]
    
    for msg in feedback_messages:
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel="customer-feedback",
            message=msg,
        )
    
    print("✓ Added sample feedback messages")
    
    cli.logout()
    
    print("\n" + "=" * 60)
    print("Setup complete!")
    print("\nLogin credentials for Mattermost app:")
    print("  Email: harry.kong@neuralforge.ai")
    print("  Password: password")
    print("\nThe customer-feedback channel now contains sample messages.")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    success = setup_customer_feedback()
    if not success:
        sys.exit(1)
