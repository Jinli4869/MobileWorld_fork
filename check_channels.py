#!/usr/bin/env python3
"""Check Mattermost channels including customer-feedback."""

import sys
sys.path.insert(0, '/home/jinli/Project/MobileWorld_fork/src')

from mobile_world.runtime.app_helpers import mattermost

# Check backend status
status = mattermost.get_mattermost_backend_status()
print(f'Mattermost backend status: {status}')

# Connect to database and list all channels
connection, cursor = mattermost.connect_to_postgres()
if cursor:
    print("\nAll channels:")
    cursor.execute("SELECT name, display_name, purpose FROM channels ORDER BY name")
    channels = cursor.fetchall()
    for channel in channels:
        print(f"  - {channel[0]}: {channel[1]} (Purpose: {channel[2]})")
    
    print("\nSearching for customer-feedback channel:")
    cursor.execute("SELECT name, display_name, purpose FROM channels WHERE name LIKE '%customer%' OR name LIKE '%feedback%'")
    feedback_channels = cursor.fetchall()
    if feedback_channels:
        for channel in feedback_channels:
            print(f"  - {channel[0]}: {channel[1]} (Purpose: {channel[2]})")
    else:
        print("  No customer-feedback channel found")
    
    # Get posts from any feedback channel
    if feedback_channels:
        for channel in feedback_channels:
            channel_id = channel[0]
            print(f"\nPosts in {channel[0]}:")
            cursor.execute("SELECT message, createat FROM posts WHERE channelid = '{}' ORDER BY createat DESC LIMIT 20".format(channel_id))
            posts = cursor.fetchall()
            for post in posts:
                print(f"  [{post[1]}] {post[0][:100]}...")
    
    cursor.close()
    connection.close()
else:
    print("Could not connect to database")
