"""Load the raw C-MAPSS FD001 text files into a SQLite database.

Usage: python -m src.build_db
"""
import sqlite3
import pandas as pd
from .config import RAW, SQL_DIR, DB_PATH, COLUMNS, SETTINGS, SENSORS


def read_raw(name):
    return pd.read_csv(RAW / name, sep=r"\s+", header=None, names=COLUMNS)


def main():
    train = read_raw("train_FD001.txt").assign(split="train")
    test = read_raw("test_FD001.txt").assign(split="test")
    cycles = pd.concat([train, test], ignore_index=True)[["split"] + COLUMNS]
    rul = pd.read_csv(RAW / "RUL_FD001.txt", header=None, names=["rul"])
    rul.insert(0, "unit", range(1, len(rul) + 1))

    long = cycles.melt(id_vars=["split", "unit", "cycle"], value_vars=SETTINGS + SENSORS,
                       var_name="sensor", value_name="value")

    DB_PATH.unlink(missing_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript((SQL_DIR / "01_schema.sql").read_text())
    cycles.to_sql("cycles", con, if_exists="append", index=False)
    long.to_sql("readings", con, if_exists="append", index=False)
    rul.to_sql("test_rul", con, if_exists="append", index=False)
    con.commit()
    for t in ("cycles", "readings", "test_rul"):
        print(t, con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0], "rows")
    con.close()


if __name__ == "__main__":
    main()
