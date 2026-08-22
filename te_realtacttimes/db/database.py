# =============================================================================
# te_realtacttimes/db/database.py – Datenbankzugriff
# teRealTactTimes – technosert electronic GmbH
# =============================================================================
"""
Einzige Datei mit SQL-Zugriffen der Anwendung. Alle anderen Module (routes.py,
bewertung.py, dokumentation.py, infor.py) rufen ausschließlich Funktionen aus
diesem Modul auf, es wird nirgendwo sonst SQL geschrieben.

Es werden zwei Zieltreiber unterstützt:
  - "mssql"  -> pyodbc, für die beiden produktiven Server-Profile ("te"/"mbe")
  - "sqlite" -> stdlib sqlite3, ausschließlich für das Profil "demo"
                (siehe config.DB_SERVERS und README.md)

Beide Dialekte werden über Bracket-Quoting ([spalte]) angesprochen, das sowohl
von SQL Server als auch von SQLite verstanden wird - dadurch kann derselbe
SQL-Text für beide Treiber verwendet werden.
"""

import logging
import sqlite3
from contextlib import contextmanager

import config
import settings

logger = logging.getLogger(__name__)


# =============================================================================
# ===== Verbindungsaufbau =====
# =============================================================================

def get_server_profile(server_key=None):
    """Liefert das config.DB_SERVERS-Profil für server_key (Default: aktiver Server)."""
    server_key = server_key or settings.get_active_server()
    profile = config.DB_SERVERS.get(server_key)
    if profile is None:
        raise ValueError(f"Unbekanntes Server-Profil: {server_key!r}")
    return server_key, profile


def _build_mssql_conn_str(profile):
    parts = [
        f"DRIVER={{{profile['odbc_driver']}}}",
        f"SERVER={profile['server']}",
        f"DATABASE={profile['database']}",
    ]
    if profile.get("trusted_connection", True):
        parts.append("Trusted_Connection=yes")
    else:
        parts.append(f"UID={profile.get('user', '')}")
        parts.append(f"PWD={profile.get('password', '')}")
    return ";".join(parts) + ";"


def _connect_mssql(profile):
    try:
        import pyodbc
    except ImportError as exc:  # pragma: no cover - nur relevant ohne pyodbc-Installation
        raise RuntimeError(
            "pyodbc ist nicht installiert. Für den Betrieb gegen einen SQL-Server "
            "bitte 'pip install -r requirements.txt' ausführen."
        ) from exc
    conn_str = _build_mssql_conn_str(profile)
    return pyodbc.connect(conn_str, timeout=5)


def _connect_sqlite(profile):
    import os
    os.makedirs(os.path.dirname(profile["path"]) or ".", exist_ok=True)
    conn = sqlite3.connect(profile["path"])
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_connection(server_key=None):
    """Kontextmanager: verbindet, committet bei Erfolg, rollt bei Fehler zurück, schließt immer."""
    server_key, profile = get_server_profile(server_key)
    if profile["driver"] == "mssql":
        conn = _connect_mssql(profile)
    elif profile["driver"] == "sqlite":
        conn = _connect_sqlite(profile)
    else:
        raise ValueError(f"Unbekannter Treiber: {profile['driver']!r}")
    try:
        yield conn, profile["driver"]
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _rows_to_dicts(cursor):
    columns = [c[0] for c in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def execute_query(sql, params=None, server_key=None):
    """Führt ein SELECT aus und liefert eine Liste von dicts zurück."""
    with db_connection(server_key) as (conn, _driver):
        cur = conn.cursor()
        cur.execute(sql, params or [])
        return _rows_to_dicts(cur)


def execute_write(sql, params=None, server_key=None):
    """Führt INSERT/UPDATE/DELETE aus, liefert die Anzahl betroffener Zeilen."""
    with db_connection(server_key) as (conn, _driver):
        cur = conn.cursor()
        cur.execute(sql, params or [])
        return cur.rowcount


def execute_many(sql, param_list, server_key=None):
    """Führt dieselbe SQL-Anweisung für eine Liste von Parametersets aus (Bulk)."""
    with db_connection(server_key) as (conn, _driver):
        cur = conn.cursor()
        cur.executemany(sql, param_list)
        return cur.rowcount


def test_connection(server_key=None):
    """Prüft die Verbindung zu einem Server-Profil. Liefert (ok: bool, message: str)."""
    server_key, profile = get_server_profile(server_key)
    try:
        with db_connection(server_key) as (conn, _driver):
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchall()
        return True, f"Verbindung zu '{profile['label']}' erfolgreich."
    except Exception as exc:  # noqa: BLE001 - Nutzerfeedback, bewusst breit gefangen
        logger.exception("Verbindungstest zu %s fehlgeschlagen", server_key)
        return False, f"Verbindung zu '{profile['label']}' fehlgeschlagen: {exc}"


# =============================================================================
# ===== Anwendungstabellen anlegen (DDL) =====
# =============================================================================

def _table_name(key, driver):
    """Liefert den Tabellennamen für den jeweiligen Dialekt.

    SQLite kennt kein Schema-Präfix "dbo." - daher wird es dort entfernt.
    """
    name = config.APP_TABLES[key]
    if driver == "sqlite" and name.lower().startswith("dbo."):
        return name.split(".", 1)[1]
    return name


_DDL = {
    "tact_time_check": {
        "mssql": """
            IF NOT EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'{table}') AND type = N'U')
            CREATE TABLE {table} (
                id INT IDENTITY(1,1) PRIMARY KEY,
                [projNr] NVARCHAR(50) NOT NULL,
                [bewertungsdatum] DATETIME2 NOT NULL,
                [bearbeiter] NVARCHAR(100) NOT NULL,
                [process] NVARCHAR(50) NOT NULL,
                [mtt] FLOAT NULL,
                [ptt] FLOAT NULL,
                [abweichung] FLOAT NULL,
                [abweichung_pct] FLOAT NULL,
                [status] NVARCHAR(20) NOT NULL
            );
        """,
        "sqlite": """
            CREATE TABLE IF NOT EXISTS [{table}] (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                [projNr] TEXT NOT NULL,
                [bewertungsdatum] TEXT NOT NULL,
                [bearbeiter] TEXT NOT NULL,
                [process] TEXT NOT NULL,
                [mtt] REAL,
                [ptt] REAL,
                [abweichung] REAL,
                [abweichung_pct] REAL,
                [status] TEXT NOT NULL
            );
        """,
    },
    "infor_changes": {
        "mssql": """
            IF NOT EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'{table}') AND type = N'U')
            CREATE TABLE {table} (
                id INT IDENTITY(1,1) PRIMARY KEY,
                [projNr] NVARCHAR(50) NOT NULL,
                [uebernahmedatum] DATETIME2 NOT NULL,
                [bearbeiter] NVARCHAR(100) NOT NULL,
                [process] NVARCHAR(50) NOT NULL,
                [mtt] FLOAT NULL,
                [ptt] FLOAT NULL,
                [abweichung] FLOAT NULL,
                [abweichung_pct] FLOAT NULL,
                [ptt_neu] FLOAT NOT NULL,
                [status] NVARCHAR(20) NOT NULL DEFAULT 'offen'
            );
        """,
        "sqlite": """
            CREATE TABLE IF NOT EXISTS [{table}] (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                [projNr] TEXT NOT NULL,
                [uebernahmedatum] TEXT NOT NULL,
                [bearbeiter] TEXT NOT NULL,
                [process] TEXT NOT NULL,
                [mtt] REAL,
                [ptt] REAL,
                [abweichung] REAL,
                [abweichung_pct] REAL,
                [ptt_neu] REAL NOT NULL,
                [status] TEXT NOT NULL DEFAULT 'offen'
            );
        """,
    },
    "ptt_manual": {
        # Übergangslösung solange die echte Leitstand-PTT-Quelle <TBD> ist.
        "mssql": """
            IF NOT EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'{table}') AND type = N'U')
            CREATE TABLE {table} (
                [projNr] NVARCHAR(50) NOT NULL,
                [process] NVARCHAR(50) NOT NULL,
                [subProcess] NVARCHAR(50) NOT NULL,
                [ptt] FLOAT NOT NULL,
                [updated_by] NVARCHAR(100) NULL,
                [updated_at] DATETIME2 NULL,
                PRIMARY KEY ([projNr], [process], [subProcess])
            );
        """,
        "sqlite": """
            CREATE TABLE IF NOT EXISTS [{table}] (
                [projNr] TEXT NOT NULL,
                [process] TEXT NOT NULL,
                [subProcess] TEXT NOT NULL,
                [ptt] REAL NOT NULL,
                [updated_by] TEXT,
                [updated_at] TEXT,
                PRIMARY KEY ([projNr], [process], [subProcess])
            );
        """,
    },
}


def ensure_app_tables(server_key=None):
    """Legt die von der App verwalteten Tabellen an, falls sie noch nicht existieren."""
    server_key, profile = get_server_profile(server_key)
    driver = profile["driver"]
    with db_connection(server_key) as (conn, _driver):
        cur = conn.cursor()
        for key, ddl_by_driver in _DDL.items():
            table = _table_name(key, driver)
            ddl = ddl_by_driver[driver].format(table=table)
            cur.execute(ddl)


# =============================================================================
# ===== MTT (Ist-Daten) – MAR_TactTimesCalc / MAR_TactTimes =====
# =============================================================================

_MTT_CALC_COLUMNS = [
    "projNr", "process", "subProcess", "prozessOrder",
    "lots", "boards", "panels", "anzahlFrames", "panelSize", "boardsInFrame",
    "frame_tactTime_brutto", "frame_tactTime_netto",
    "panel_tactTime_brutto", "panel_tactTime_netto",
    "board_tactTime_brutto", "board_tactTime_netto",
    "manufacturingTime",
]

_MTT_DETAIL_COLUMNS = [
    "lot", "panels", "boards", "panelSize", "boardsInFrame", "anzahlFrames",
    "projNr", "machineId", "process", "subProcess", "ManufacturingTime",
    "prozessOrder", "tactTime_brutto", "tactTime_netto", "testDauer",
]


def get_mtt_calc_projects(server_key=None):
    """Liste aller distinct projNr in MAR_TactTimesCalc (für Auswahl/Filter)."""
    sql = f"SELECT DISTINCT [projNr] FROM [{config.SOURCE_TABLES['mtt_calc']}] ORDER BY [projNr]"
    rows = execute_query(sql, server_key=server_key)
    return [r["projNr"] for r in rows]


def get_mtt_calc(proj_nr=None, server_key=None):
    """MTT (gemittelt über Lose) aus MAR_TactTimesCalc, optional gefiltert nach projNr."""
    cols = ", ".join(f"[{c}]" for c in _MTT_CALC_COLUMNS)
    sql = f"SELECT {cols} FROM [{config.SOURCE_TABLES['mtt_calc']}]"
    params = []
    if proj_nr:
        sql += " WHERE [projNr] = ?"
        params.append(proj_nr)
    sql += " ORDER BY [projNr], [prozessOrder], [subProcess]"
    return execute_query(sql, params, server_key=server_key)


def get_mtt_detail(proj_nr, process=None, sub_process=None, server_key=None):
    """MTT je Fertigungslos aus MAR_TactTimes (für Processdetails-PopUp)."""
    cols = ", ".join(f"[{c}]" for c in _MTT_DETAIL_COLUMNS)
    sql = f"SELECT {cols} FROM [{config.SOURCE_TABLES['mtt_detail']}] WHERE [projNr] = ?"
    params = [proj_nr]
    if process:
        sql += " AND [process] = ?"
        params.append(process)
    if sub_process:
        sql += " AND [subProcess] = ?"
        params.append(sub_process)
    sql += " ORDER BY [lot], [ManufacturingTime]"
    return execute_query(sql, params, server_key=server_key)


# =============================================================================
# ===== PTT (Soll-Daten) – Übergangslösung teCalc_PTT_manual =====
# =============================================================================
# Die eigentliche Anbindung an den Leitstand ist laut Vorgabe <TBD>. Bis diese
# Quelle feststeht, kann PTT manuell je projNr/process/subProcess gepflegt
# werden (Konfiguration -> PTT-Pflege). get_ptt_map() ist die einzige Stelle,
# die bei Anbindung der echten Quelle ausgetauscht werden muss.

def get_ptt_map(proj_nr=None, server_key=None):
    """Liefert PTT-Werte als dict {(projNr, process, subProcess): ptt}."""
    _, profile = get_server_profile(server_key)
    table = _table_name("ptt_manual", profile["driver"])
    sql = f"SELECT [projNr], [process], [subProcess], [ptt] FROM [{table}]"
    params = []
    if proj_nr:
        sql += " WHERE [projNr] = ?"
        params.append(proj_nr)
    rows = execute_query(sql, params, server_key=server_key)
    return {(r["projNr"], r["process"], r["subProcess"]): r["ptt"] for r in rows}


def get_ptt_rows(proj_nr=None, server_key=None):
    """PTT-Einträge als Liste (für die PTT-Pflege-Seite)."""
    _, profile = get_server_profile(server_key)
    table = _table_name("ptt_manual", profile["driver"])
    sql = f"SELECT [projNr], [process], [subProcess], [ptt], [updated_by], [updated_at] FROM [{table}]"
    params = []
    if proj_nr:
        sql += " WHERE [projNr] = ?"
        params.append(proj_nr)
    sql += " ORDER BY [projNr], [process], [subProcess]"
    return execute_query(sql, params, server_key=server_key)


def upsert_ptt(proj_nr, process, sub_process, ptt, user, server_key=None):
    """Legt einen manuellen PTT-Wert an oder aktualisiert ihn (Update-then-Insert)."""
    _, profile = get_server_profile(server_key)
    table = _table_name("ptt_manual", profile["driver"])
    now = _now_str()
    upd_sql = (
        f"UPDATE [{table}] SET [ptt] = ?, [updated_by] = ?, [updated_at] = ? "
        f"WHERE [projNr] = ? AND [process] = ? AND [subProcess] = ?"
    )
    rowcount = execute_write(
        upd_sql, [ptt, user, now, proj_nr, process, sub_process], server_key=server_key
    )
    if rowcount == 0:
        ins_sql = (
            f"INSERT INTO [{table}] ([projNr], [process], [subProcess], [ptt], [updated_by], [updated_at]) "
            f"VALUES (?, ?, ?, ?, ?, ?)"
        )
        execute_write(
            ins_sql, [proj_nr, process, sub_process, ptt, user, now], server_key=server_key
        )


def delete_ptt(proj_nr, process, sub_process, server_key=None):
    _, profile = get_server_profile(server_key)
    table = _table_name("ptt_manual", profile["driver"])
    sql = f"DELETE FROM [{table}] WHERE [projNr] = ? AND [process] = ? AND [subProcess] = ?"
    execute_write(sql, [proj_nr, process, sub_process], server_key=server_key)


# =============================================================================
# ===== Dokumentation – teCalc_COR_tactTimesCheck / teCalc_COR_INFORchanges ====
# =============================================================================

def _now_str():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def save_tact_time_check_rows(rows, bearbeiter, server_key=None):
    """Speichert einen Bewertungs-Snapshot (1 Zeile je projNr+process) beim Ausführen von TTCheck."""
    _, profile = get_server_profile(server_key)
    table = _table_name("tact_time_check", profile["driver"])
    now = _now_str()
    sql = (
        f"INSERT INTO [{table}] "
        f"([projNr], [bewertungsdatum], [bearbeiter], [process], [mtt], [ptt], [abweichung], [abweichung_pct], [status]) "
        f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    params = [
        (r["projNr"], now, bearbeiter, r["process"], r["mtt"], r["ptt"],
         r["abweichung"], r["abweichung_pct"], r["status"])
        for r in rows
    ]
    if params:
        execute_many(sql, params, server_key=server_key)
    return len(params)


def save_infor_change_rows(rows, bearbeiter, server_key=None):
    """Speichert die vom Nutzer freigegebenen Korrekturwerte (Button 'übernehmen')."""
    _, profile = get_server_profile(server_key)
    table = _table_name("infor_changes", profile["driver"])
    now = _now_str()
    sql = (
        f"INSERT INTO [{table}] "
        f"([projNr], [uebernahmedatum], [bearbeiter], [process], [mtt], [ptt], [abweichung], [abweichung_pct], [ptt_neu], [status]) "
        f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'offen')"
    )
    params = [
        (r["projNr"], now, bearbeiter, r["process"], r["mtt"], r["ptt"],
         r["abweichung"], r["abweichung_pct"], r["ptt_neu"])
        for r in rows
    ]
    if params:
        execute_many(sql, params, server_key=server_key)
    return len(params)


def get_tact_time_check_history(proj_nr=None, server_key=None):
    _, profile = get_server_profile(server_key)
    table = _table_name("tact_time_check", profile["driver"])
    sql = f"SELECT * FROM [{table}]"
    params = []
    if proj_nr:
        sql += " WHERE [projNr] = ?"
        params.append(proj_nr)
    sql += " ORDER BY [bewertungsdatum] DESC"
    return execute_query(sql, params, server_key=server_key)


def get_infor_changes(proj_nr=None, server_key=None):
    _, profile = get_server_profile(server_key)
    table = _table_name("infor_changes", profile["driver"])
    sql = f"SELECT * FROM [{table}]"
    params = []
    if proj_nr:
        sql += " WHERE [projNr] = ?"
        params.append(proj_nr)
    sql += " ORDER BY [uebernahmedatum] DESC"
    return execute_query(sql, params, server_key=server_key)


# =============================================================================
# ===== Demo-Daten (nur Profil "demo") =====
# =============================================================================

def demo_data_loaded(server_key="demo"):
    _, profile = get_server_profile(server_key)
    if profile["driver"] != "sqlite":
        return True
    try:
        rows = execute_query(
            f"SELECT COUNT(*) AS n FROM [{config.SOURCE_TABLES['mtt_calc']}]",
            server_key=server_key,
        )
        return rows and rows[0]["n"] > 0
    except Exception:
        return False
