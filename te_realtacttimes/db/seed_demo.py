# =============================================================================
# te_realtacttimes/db/seed_demo.py – Demo-Daten aus CSV in SQLite laden
# teRealTactTimes – technosert electronic GmbH
# =============================================================================
"""
Befüllt die lokale Demo-SQLite-Datenbank (Profil "demo") mit den mitgelieferten
CSV-Beispieldaten aus data/MAR_TactTimes.csv und data/MAR_TactTimesCalc.csv.

Diese Tabellen entsprechen im Echtbetrieb externen, per ETL befüllten Quellen
im DataWarehouse (siehe config.SOURCE_TABLES) - im Demo-Modus übernimmt dieses
Skript die Rolle des ETL, ausschließlich zu Test-/Vorführzwecken.

Format der CSV-Dateien: Semikolon-getrennt, UTF-8 mit BOM, deutsches
Dezimalkomma ("0,7056"), fehlende Werte als Text "NULL".
"""

import csv
import logging
import os

import config
from db import database

logger = logging.getLogger(__name__)

_CALC_FILE = "MAR_TactTimesCalc.csv"
_DETAIL_FILE = "MAR_TactTimes.csv"

# Spalten, die numerisch (Gleitkomma) sind und aus dem deutschen Format
# ("0,7056" / "NULL") in float/None gewandelt werden müssen.
_CALC_NUMERIC = [
    "lots", "boards", "panels", "anzahlFrames", "panelSize", "boardsInFrame",
    "prozessOrder", "frame_tactTime_brutto", "frame_tactTime_netto",
    "panel_tactTime_brutto", "panel_tactTime_netto",
    "board_tactTime_brutto", "board_tactTime_netto",
]
_DETAIL_NUMERIC = [
    "panels", "boards", "panelSize", "boardsInFrame", "anzahlFrames",
    "prozessOrder", "tactTime_brutto", "tactTime_netto", "testDauer",
]


def _to_float(value):
    if value is None:
        return None
    value = value.strip()
    if value == "" or value.upper() == "NULL":
        return None
    return float(value.replace(",", "."))


def _read_csv(path, numeric_columns):
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = []
        for raw in reader:
            row = dict(raw)
            for col in numeric_columns:
                if col in row:
                    row[col] = _to_float(row[col])
            rows.append(row)
        return rows, reader.fieldnames


def _create_and_fill(conn, table, csv_path, numeric_columns):
    rows, fieldnames = _read_csv(csv_path, numeric_columns)
    if not rows:
        logger.warning("Keine Zeilen in %s gefunden - überspringe.", csv_path)
        return 0

    def sql_type(col):
        return "REAL" if col in numeric_columns else "TEXT"

    col_defs = ", ".join(f"[{c}] {sql_type(c)}" for c in fieldnames)
    conn.execute(f"DROP TABLE IF EXISTS [{table}]")
    conn.execute(f"CREATE TABLE [{table}] ({col_defs})")

    placeholders = ", ".join("?" for _ in fieldnames)
    col_list = ", ".join(f"[{c}]" for c in fieldnames)
    insert_sql = f"INSERT INTO [{table}] ({col_list}) VALUES ({placeholders})"
    conn.executemany(insert_sql, [[row[c] for c in fieldnames] for row in rows])
    conn.commit()
    return len(rows)


def seed_demo_database(force=False):
    """Lädt die Demo-Quelltabellen (MAR_TactTimesCalc/MAR_TactTimes) neu ein.

    force=False: überspringt das Neuladen, wenn bereits Daten vorhanden sind.
    """
    import sqlite3

    profile = config.DB_SERVERS["demo"]
    if profile["driver"] != "sqlite":
        raise RuntimeError("seed_demo_database ist nur für das Profil 'demo' vorgesehen.")

    if not force and database.demo_data_loaded("demo"):
        logger.info("Demo-Daten bereits vorhanden - kein erneutes Laden nötig.")
        return {"skipped": True}

    calc_path = os.path.join(config.DEMO_DATA_DIR, _CALC_FILE)
    detail_path = os.path.join(config.DEMO_DATA_DIR, _DETAIL_FILE)
    if not os.path.exists(calc_path) or not os.path.exists(detail_path):
        raise FileNotFoundError(
            f"Demo-CSV-Dateien nicht gefunden unter {config.DEMO_DATA_DIR}. "
            f"Erwartet: {_CALC_FILE}, {_DETAIL_FILE}"
        )

    os.makedirs(os.path.dirname(profile["path"]) or ".", exist_ok=True)
    conn = sqlite3.connect(profile["path"])
    try:
        n_calc = _create_and_fill(conn, config.SOURCE_TABLES["mtt_calc"], calc_path, _CALC_NUMERIC)
        n_detail = _create_and_fill(conn, config.SOURCE_TABLES["mtt_detail"], detail_path, _DETAIL_NUMERIC)
    finally:
        conn.close()

    database.ensure_app_tables("demo")
    logger.info("Demo-Daten geladen: %s MTT-Calc-Zeilen, %s MTT-Detail-Zeilen.", n_calc, n_detail)
    return {"skipped": False, "mtt_calc_rows": n_calc, "mtt_detail_rows": n_detail}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = seed_demo_database(force=True)
    print(result)
