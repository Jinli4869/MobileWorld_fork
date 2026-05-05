#!/bin/bash
# Check Mattermost backend status
cd /home/jinli/Project/MobileWorld_fork
docker compose -f docker-compose.yml -f docker-compose.without-nginx.yml -C /app/mattermost-docker ps 2>/dev/null || echo "Mattermost backend not running"
