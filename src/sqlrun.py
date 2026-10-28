import re
import sqlite3
import pandas as pd
from .config import SQL_DIR, DB_PATH


def connect(path=DB_PATH):
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run: python -m src.build_db")
    return sqlite3.connect(path)


def load_named_queries(file=SQL_DIR / "02_queries.sql"):
    """Split a SQL file into {name: statement} using '-- name: <id>' markers."""
    parts = re.split(r"^-- name:\s*(\w+)\s*$", file.read_text(), flags=re.M)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def run(name, con):
    return pd.read_sql_query(load_named_queries()[name], con)
