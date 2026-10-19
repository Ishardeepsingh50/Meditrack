"""
config.py - Central configuration for the MediTrack project.

The connection string can be overridden with an environment variable so the
same code works for a local MongoDB server and for MongoDB Atlas:

    Windows (PowerShell):  $env:MONGO_URI = "mongodb+srv://user:pass@cluster.mongodb.net"
    Linux / macOS:         export MONGO_URI="mongodb://localhost:27017"
"""
import os

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MEDITRACK_DB", "meditrack_db")

# Fixed reference date used by the seed script so that results are reproducible.
SEED = 42
