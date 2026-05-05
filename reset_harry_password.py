#!/usr/bin/env python3
"""Reset Harry's password and verify Mattermost backend."""

import subprocess
import sys

MATTERMOST_DOCKER_DIR = "/app/mattermost-docker"
COMPOSE_FILES = ["-f", "docker-compose.yml", "-f", "docker-compose.without-nginx.yml"]

def exec_in_container(command: str) -> tuple[int, str, str]:
    """Execute a command inside the Mattermost container."""
    full_command = [
        "docker",
        "exec",
        "-i",
        f"mattermost-docker-mattermost-1",
        "bash",
        "-c",
        command,
    ]
    result = subprocess.run(full_command, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr

def reset_password(username: str, new_password: str) -> bool:
    """Reset a user's password using admin account."""
    admin_username = "admin@test.com"
    admin_password = "password"
    
    # First login as admin
    login_command = f'''
echo "{admin_password}" > /tmp/mmctl_pass.txt && \\
mmctl auth login http://127.0.0.1:8065 \\
    --name admin-session-reset \\
    --username {admin_username} \\
    --password-file /tmp/mmctl_pass.txt && \\
rm -f /tmp/mmctl_pass.txt
'''
    returncode, stdout, stderr = exec_in_container(login_command)
    if returncode != 0 or "stored" not in stdout:
        print(f"Failed to login as admin: {stderr or stdout}")
        return False
    
    # Reset the target user's password
    reset_command = f'mmctl user change-password {username} --password "{new_password}"'
    returncode, stdout, stderr = exec_in_container(reset_command)
    
    # Cleanup admin session
    exec_in_container(f"mmctl auth delete admin-session-reset")
    
    if returncode == 0:
        print(f"Password reset successful for {username}")
        return True
    else:
        print(f"Failed to reset password: {stderr or stdout}")
        return False

if __name__ == "__main__":
    # Reset Harry's password
    success = reset_password("harry.kong@neuralforge.ai", "password")
    if success:
        print("✓ Harry's password has been reset to 'password'")
    else:
        print("✗ Failed to reset Harry's password")
        sys.exit(1)
