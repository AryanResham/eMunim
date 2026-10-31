"""Explicit database setup: python manage.py init-db (uses DATABASE_URL)."""
import argparse
from services.storage import engine

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["init-db"])
    parser.parse_args()
    engine()
    print("Database schema v1 initialized.")
