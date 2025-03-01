#!/usr/bin/env python
import socket
import time
import os
from urllib.parse import urlparse

# Get the database URL from environment variables
db_url = os.environ.get("DATABASE_URL")
parsed_url = urlparse(db_url)

# Extract hostname and port
db_host = parsed_url.hostname
db_port = parsed_url.port or 5432  # Default PostgreSQL port

# Maximum number of retries
max_retries = 30
retry_interval = 2  # seconds

print(f"Waiting for database at {db_host}:{db_port}...")

# Try to connect to the database
for retry in range(max_retries):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((db_host, db_port))
            print("Database is available! Continuing...")
            exit(0)
    except socket.error:
        print(f"Database not available yet. Retry {retry+1}/{max_retries}...")
        time.sleep(retry_interval)

print("Failed to connect to the database after multiple retries. Exiting...")
exit(1)
