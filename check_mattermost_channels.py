#!/usr/bin/env python3
"""Check Mattermost backend status and existing channels."""

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
    
    print("\nSearching for budget-related channels:")
    cursor.execute("SELECT name, display_name, purpose FROM channels WHERE name LIKE '%budget%' OR name LIKE '%approval%' OR display_name LIKE '%budget%' OR display_name LIKE '%approval%'")
    budget_channels = cursor.fetchall()
    if budget_channels:
        for channel in budget_channels:
            print(f"  - {channel[0]}: {channel[1]} (Purpose: {channel[2]})")
    else:
        print("  No budget-related channels found")
    
    cursor.close()
    connection.close()
else:
    print("Could not connect to database")
