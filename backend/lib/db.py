"""Shared Mongo handle — import `client`/`db` from here (server.py, routers, seed.py)."""

import os
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).parent.parent / ".env")

mongo_url = os.environ["MONGO_URL"]

# Configure connection with security-conscious defaults
# w="majority" ensures writes are acknowledged by majority of replicas
connection_options = {
    "w": "majority",                      # Write concern: wait for majority acknowledgment
    "wtimeoutms": 5000,                   # Write concern timeout (ms)
    "maxPoolSize": 20,                    # Connection pool size for high-throughput
    "minPoolSize": 5,                     # Minimum connections to maintain
    "serverSelectionTimeoutMS": 5000,     # Fail fast on connection issues
    "socketTimeoutMS": 10000,             # Socket timeout for operations
    "connectTimeoutMS": 5000,             # Connection timeout
}

client = AsyncIOMotorClient(mongo_url, **connection_options)
db = client[os.environ["DB_NAME"]]
