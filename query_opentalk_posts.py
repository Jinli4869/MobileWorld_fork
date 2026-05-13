#!/usr/bin/env python3
"""Query Mastodon database for posts with #openTalk hashtag."""

import psycopg2
from datetime import datetime

# Database connection parameters
MASTODON_DB_HOST = "localhost"
MASTODON_DB_DATABASE = "mastodon"
MASTODON_DB_USER = "mastodon"
MASTODON_DB_PASSWORD = "mastodon"
MASTODON_DB_PORT = 5432


def connect_to_postgres():
    """Connect to the PostgreSQL database."""
    try:
        connection = psycopg2.connect(
            host=MASTODON_DB_HOST,
            database=MASTODON_DB_DATABASE,
            user=MASTODON_DB_USER,
            password=MASTODON_DB_PASSWORD,
            port=MASTODON_DB_PORT,
        )
        cursor = connection.cursor()
        return connection, cursor
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return None, None


def get_statuses_by_hashtag(hashtag_name: str):
    """Get all statuses (posts) with a specific hashtag."""
    conn, cur = connect_to_postgres()
    if conn is None or cur is None:
        return None

    query = """
        SELECT DISTINCT s.id, s.text, s.created_at, s.account_id, a.username
        FROM statuses s
        LEFT JOIN statuses_tags st ON st.status_id = s.id
        LEFT JOIN tags t ON t.id = st.tag_id
        LEFT JOIN accounts a ON a.id = s.account_id
        WHERE t.name = %s
        ORDER BY s.created_at DESC
    """
    
    try:
        cur.execute(query, (hashtag_name,))
        rows = cur.fetchall()
        
        if not rows:
            print(f"No posts found with hashtag #{hashtag_name}")
            return []
        
        statuses = []
        for row in rows:
            statuses.append({
                "id": row[0],
                "text": row[1],
                "created_at": row[2],
                "account_id": row[3],
                "username": row[4]
            })
        
        print(f"Found {len(statuses)} posts with #{hashtag_name}:")
        for status in statuses:
            print(f"\n--- Post ID: {status['id']} by @{status['username']} ---")
            print(f"Created: {status['created_at']}")
            print(f"Text: {status['text'][:500]}...")
        
        return statuses
    
    except Exception as e:
        print(f"Error fetching statuses: {e}")
        return None
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    # Query for #openTalk hashtag (case variations)
    for hashtag in ["openTalk", "opentalk", "OpenTalk"]:
        print(f"\n{'='*60}")
        print(f"Searching for #{hashtag}")
        print('='*60)
        statuses = get_statuses_by_hashtag(hashtag)
        if statuses:
            break
