#!/usr/bin/env python
import socket
import time
import os
import sys
from urllib.parse import urlparse


def get_db_config():
    # Get the database URL from environment variables
    db_url = os.environ.get("DATABASE_URL")

    # Fallback to individual environment variables if DATABASE_URL is not set
    if not db_url:
        db_host = os.environ.get("DB_HOST", "db")
        db_port = int(os.environ.get("DB_PORT", 5432))
        return db_host, db_port

    parsed_url = urlparse(db_url)

    # Extract hostname and port
    db_host = parsed_url.hostname
    db_port = parsed_url.port or 5432  # Default PostgreSQL port

    return db_host, db_port


def main():
    # Maximum number of retries
    max_retries = 30
    retry_interval = 2  # seconds

    db_host, db_port = get_db_config()

    print(f"Attempting to connect to database at {db_host}:{db_port}...")

    # Try to connect to the database
    for retry in range(max_retries):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5)  # 5-second timeout for connection
                s.connect((db_host, db_port))
                print("Database is available! Continuing...")
                return 0
        except (socket.error, socket.timeout) as e:
            print(f"Connection failed: {e}")
            print(f"Database not available. Retry {retry+1}/{max_retries}...")
            time.sleep(retry_interval)

    print("Failed to connect to the database after multiple retries. Exiting...")
    return 1


if __name__ == "__main__":
    sys.exit(main())
