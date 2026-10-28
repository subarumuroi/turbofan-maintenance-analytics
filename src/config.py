from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
SQL_DIR = ROOT / "sql"
OUT = ROOT / "outputs"
DB_PATH = ROOT / "data" / "turbofan.db"

SETTINGS = ["set1", "set2", "set3"]
SENSORS = [f"s{i}" for i in range(1, 22)]
COLUMNS = ["unit", "cycle"] + SETTINGS + SENSORS

RUL_CAP = 125          # common convention: engines are treated as "healthy" until ~125 cycles from failure
BASELINE_CYCLES = 20   # each engine's own first cycles define its healthy baseline
DRIFT_THRESHOLD = 1.0  # min |late-life mean - early-life mean| in early-life SDs for a channel to be modelled
