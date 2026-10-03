"""
One-shot DB setup: applies schema.sql to the running postgres container.
Run once after `docker compose up -d postgres`.
"""

import subprocess
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

USER = os.getenv("POSTGRES_USER", "postgres")
DB   = os.getenv("POSTGRES_DB", "newsrag")
SCHEMA = Path("db/schema.sql")


def run(cmd: list, input_text=None):
    return subprocess.run(
        cmd,
        input=input_text,
        capture_output=True,
        text=True,
    )


def wait_for_postgres(retries=15, delay=3):
    print("Waiting for postgres to be ready...")
    for i in range(retries):
        result = run(["docker", "compose", "exec", "postgres",
                      "pg_isready", "-U", USER])
        if result.returncode == 0:
            print("Postgres is ready.")
            return
        print(f"  ({i+1}/{retries}) not ready yet, retrying in {delay}s...")
        time.sleep(delay)
    print("Postgres did not become ready in time.")
    sys.exit(1)


def apply_schema():
    if not SCHEMA.exists():
        print(f"Schema file not found: {SCHEMA}")
        sys.exit(1)

    print(f"Applying {SCHEMA} to database '{DB}'...")
    sql = SCHEMA.read_text(encoding="utf-8")
    result = run(
        ["docker", "compose", "exec", "-T", "postgres",
         "psql", "-U", USER, "-d", DB],
        input_text=sql,
    )
    if result.returncode != 0:
        print("Schema apply failed:")
        print(result.stderr)
        sys.exit(1)
    print("Schema applied.")


def verify_tables():
    print("Verifying tables...")
    result = run(
        ["docker", "compose", "exec", "postgres",
         "psql", "-U", USER, "-d", DB, "-c", "\\dt"]
    )
    print(result.stdout)


if __name__ == "__main__":
    wait_for_postgres()
    apply_schema()
    verify_tables()
    print("DB setup complete. Ready to run the pipeline.")