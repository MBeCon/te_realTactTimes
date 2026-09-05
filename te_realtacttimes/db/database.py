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

import datetime
import uuid
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


def _qtable(table):
    """Bracket-quotet einen (ggf. schema-qualifizierten) Tabellennamen sicher fuer SQL.

    `table` ist z.B. "teCalc_PTT_manual" (sqlite) oder "dbo.teCalc_PTT_manual"
    (mssql, siehe _table_name()). [dbo.teCalc_PTT_manual] als EIN
    zusammenhaengender Bracket-Ausdruck ist auf SQL Server UNGUELTIG - das wird
    als eine Tabelle interpretiert, deren Name woertlich den Punkt enthaelt,
    und schlaegt mit "Ungueltiger Objektname" fehl. Schema und Tabellenname
    muessen stattdessen getrennt geklammert werden: [dbo].[teCalc_PTT_manual].
    Ohne Punkt (sqlite) liefert das schlicht [table] wie zuvor.
    """
    return ".".join(f"[{part}]" for part in table.split("."))


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
                [status] NVARCHAR(20) NOT NULL DEFAULT 'offen',
                [info] NVARCHAR(MAX) NULL,
                [vorgang_id] NVARCHAR(64) NULL
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
                [status] TEXT NOT NULL DEFAULT 'offen',
                [info] TEXT,
                [vorgang_id] TEXT
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


# Spalten, die NACH der urspruenglichen Tabellenanlage hinzugekommen sind:
# CREATE TABLE IF NOT EXISTS (sqlite) bzw. das IF NOT EXISTS-Guard (mssql) legt
# bei einer bereits bestehenden Tabelle KEINE fehlenden Spalten nach - daher
# uebernimmt _ensure_extra_columns() das per ALTER TABLE, wenn ensure_app_tables()
# eine bereits vorhandene Tabelle vorfindet, die eine neuere Spalte noch nicht hat.
_EXTRA_COLUMNS = {
    "infor_changes": [
        # (Spaltenname, SQLite-Typ, MSSQL-Typ)
        ("info", "TEXT", "NVARCHAR(MAX)"),
        # Eindeutige ID je Uebernahme-VORGANG (1 Klick auf "Uebernehmen" im
        # Bestaetigungs-PopUp = 1 vorgang_id, geteilt von allen Prozess-Zeilen
        # dieses Klicks). Noetig, weil (projNr, uebernahmedatum, bearbeiter)
        # allein NICHT eindeutig ist: uebernahmedatum hat nur Sekunden-
        # Genauigkeit, zwei getrennte Uebernahmen derselben Person fuer
        # dasselbe Projekt innerhalb derselben Sekunde wuerden sonst faelschlich
        # zu einem einzigen "Vorgang" verschmolzen (siehe
        # dokumentation.group_infor_changes_by_uebernahme).
        ("vorgang_id", "TEXT", "NVARCHAR(64)"),
    ],
}


def _existing_columns(conn, driver, table):
    """Liefert die (kleingeschriebenen) Spaltennamen einer bestehenden Tabelle."""
    cur = conn.cursor()
    if driver == "mssql":
        schema, _, bare = table.partition(".")
        if not bare:
            schema, bare = "dbo", schema
        cur.execute(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?",
            [schema, bare],
        )
        return {row[0].lower() for row in cur.fetchall()}
    bare = table.split(".", 1)[1] if table.lower().startswith("dbo.") else table
    cur.execute(f"PRAGMA table_info([{bare}])")
    return {row[1].lower() for row in cur.fetchall()}


def _ensure_extra_columns(conn, driver, key, table):
    """Fuegt neu eingefuehrte Spalten per ALTER TABLE nach, falls die Tabelle
    schon vor Einfuehrung dieser Spalte angelegt wurde (siehe _EXTRA_COLUMNS)."""
    extras = _EXTRA_COLUMNS.get(key)
    if not extras:
        return
    existing = _existing_columns(conn, driver, table)
    cur = conn.cursor()
    for column, sqlite_type, mssql_type in extras:
        if column.lower() in existing:
            continue
        coltype = mssql_type if driver == "mssql" else sqlite_type
        cur.execute(f"ALTER TABLE {_qtable(table)} ADD [{column}] {coltype} NULL")


def _table_exists(conn, driver, table):
    """Prüft direkt über die (bereits offene) Verbindung, ob eine Tabelle existiert.

    Wird nach einem CREATE TABLE zur Verifikation genutzt: manche Server-
    Konfigurationen (z.B. ein DDL-Trigger, der die Anlage protokolliert und
    dabei zurückrollt, oder eine abweichende Standard-Datenbank/Schema pro
    Verbindung) können ein CREATE TABLE ohne Fehlermeldung durchlaufen lassen,
    ohne dass die Tabelle danach tatsächlich auffindbar ist - ohne diese
    Verifikation würde ensure_app_tables() das fälschlich als Erfolg werten.
    """
    cur = conn.cursor()
    if driver == "mssql":
        cur.execute(
            "SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(?) AND type = N'U'",
            [table],
        )
    else:  # sqlite
        bare = table.split(".", 1)[1] if table.lower().startswith("dbo.") else table
        cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", [bare])
    return cur.fetchone() is not None


def ensure_app_tables(server_key=None):
    """Legt die von der App verwalteten Tabellen an, falls sie noch nicht existieren.

    Jede Tabelle wird in einer eigenen Transaktion angelegt (statt vorher: eine
    gemeinsame Transaktion für alle App-Tabellen). Grund: schlug früher die DDL
    für eine Tabelle fehl (z.B. fehlende CREATE TABLE-Berechtigung nur für
    dbo.teCalc_COR_tactTimesCheck), wurden dadurch auch bereits erfolgreich
    angelegte Tabellen in derselben Transaktion wieder zurückgerollt (u.a.
    dbo.teCalc_PTT_manual) - ein einzelner Fehler blockierte so sämtliche
    App-Tabellen, nicht nur die betroffene.

    Nach jedem CREATE TABLE wird zusätzlich per _table_exists() verifiziert,
    dass die Tabelle danach wirklich existiert (siehe dortige Erklärung) -
    läuft die DDL ohne Exception durch, die Tabelle ist aber trotzdem nicht
    auffindbar, wird das jetzt ebenfalls als Fehler gemeldet statt als Erfolg.

    Rückgabe: dict {table_key: Fehlermeldung} für alle Tabellen, deren Anlage
    fehlgeschlagen ist (leer = alle angelegt/bereits vorhanden). Der Aufrufer
    kann damit gezielt melden, welche Tabelle fehlt und warum - statt nur
    einer generischen Meldung.
    """
    server_key, profile = get_server_profile(server_key)
    driver = profile["driver"]
    fehler = {}
    for key, ddl_by_driver in _DDL.items():
        table = _table_name(key, driver)
        ddl = ddl_by_driver[driver].format(table=table)
        try:
            with db_connection(server_key) as (conn, _driver):
                conn.cursor().execute(ddl)
                if not _table_exists(conn, driver, table):
                    raise RuntimeError(
                        f"CREATE TABLE für {table} lief ohne Fehlermeldung durch, "
                        f"die Tabelle ist danach aber trotzdem nicht auffindbar "
                        f"(sys.objects bzw. sqlite_master) - möglicherweise eine "
                        f"abweichende Datenbank/Schema-Berechtigung oder ein "
                        f"serverseitiger DDL-Trigger, der die Anlage verhindert."
                    )
                _ensure_extra_columns(conn, driver, key, table)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Konnte App-Tabelle %s (%s) nicht anlegen", key, table)
            fehler[key] = str(exc)
    return fehler


def get_ddl_for_table(key, server_key=None):
    """Liefert die rohe CREATE-TABLE-Anweisung für eine App-Tabelle (key aus

    _DDL, z.B. 'ptt_manual') im Dialekt des aktiven/angegebenen Servers - zum
    Anzeigen, falls die automatische Anlage fehlschlägt (z.B. mangels
    Berechtigung), damit ein Admin sie manuell ausführen kann.
    """
    _, profile = get_server_profile(server_key)
    driver = profile["driver"]
    table = _table_name(key, driver)
    return _DDL[key][driver].format(table=table).strip()


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


def get_mtt_detail_alle(server_key=None):
    """Alle Zeilen aus MAR_TactTimes (ungefiltert).

    Für das TactTimes-PopUp auf der Startseite, das den kompletten Inhalt der
    Quelltabelle anzeigt (siehe config.SOURCE_TABLES['mtt_detail']).
    """
    cols = ", ".join(f"[{c}]" for c in _MTT_DETAIL_COLUMNS)
    sql = f"SELECT {cols} FROM [{config.SOURCE_TABLES['mtt_detail']}] ORDER BY [projNr], [lot], [process], [subProcess]"
    return execute_query(sql, server_key=server_key)


def get_process_subprocess_pairs(server_key=None):
    """Distinct (process, subProcess)-Paare aus MAR_TactTimes.

    Für Auswahllisten mit Kaskadierung (z.B. PTT-Pflege: Kombinationsfelder
    process/subProcess) - lt. Datenmodell hat jeder subProcess genau einen
    zugehörigen process, ein process kann aber mehrere subProcesse haben.
    """
    sql = (
        f"SELECT DISTINCT [process], [subProcess] "
        f"FROM [{config.SOURCE_TABLES['mtt_detail']}] "
        f"WHERE [process] IS NOT NULL AND [subProcess] IS NOT NULL "
        f"ORDER BY [process], [subProcess]"
    )
    return execute_query(sql, server_key=server_key)


def _parse_date_loose(value):
    """Wandelt einen DB-Wert (date/datetime-Objekt oder Text) in ein reines
    datetime.date um - unabhängig davon, ob die Quelle (SQLite-Text oder
    MSSQL date/datetime) Uhrzeit mitliefert. Liefert None bei leerem/
    unlesbarem Wert.
    """
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    s = str(value).strip()
    if len(s) < 10:
        return None
    try:
        return datetime.date.fromisoformat(s[:10])
    except ValueError:
        return None


def get_infor_lag_projects(server_key=None):
    """Projekte, deren letzte Infor-Übernahme (teCalc_COR_INFORchanges.

    uebernahmedatum) älter ist als die neueste Fertigungszeit in
    MAR_TactTimesCalc.manufacturingTime - oder für die es noch nie eine
    Infor-Übernahme gab, obwohl bereits Fertigungsdaten vorliegen.

    Rückgabe: set der betroffenen projNr (für die Markierung in der
    Projekte-Liste auf der Bewerten-Seite).
    """
    mtt_sql = (
        f"SELECT [projNr], MAX([manufacturingTime]) AS letzte_fertigung "
        f"FROM [{config.SOURCE_TABLES['mtt_calc']}] GROUP BY [projNr]"
    )
    mtt_rows = execute_query(mtt_sql, server_key=server_key)

    _, profile = get_server_profile(server_key)
    infor_table = _table_name("infor_changes", profile["driver"])
    infor_sql = (
        f"SELECT [projNr], MAX([uebernahmedatum]) AS letzte_uebernahme "
        f"FROM {_qtable(infor_table)} GROUP BY [projNr]"
    )
    infor_rows = execute_query(infor_sql, server_key=server_key)
    infor_map = {
        r["projNr"]: _parse_date_loose(r["letzte_uebernahme"]) for r in infor_rows
    }

    stale = set()
    for r in mtt_rows:
        letzte_fertigung = _parse_date_loose(r["letzte_fertigung"])
        if letzte_fertigung is None:
            continue
        letzte_uebernahme = infor_map.get(r["projNr"])
        if letzte_uebernahme is None or letzte_uebernahme < letzte_fertigung:
            stale.add(r["projNr"])
    return stale


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
    sql = f"SELECT [projNr], [process], [subProcess], [ptt] FROM {_qtable(table)}"
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
    sql = f"SELECT [projNr], [process], [subProcess], [ptt], [updated_by], [updated_at] FROM {_qtable(table)}"
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
        f"UPDATE {_qtable(table)} SET [ptt] = ?, [updated_by] = ?, [updated_at] = ? "
        f"WHERE [projNr] = ? AND [process] = ? AND [subProcess] = ?"
    )
    rowcount = execute_write(
        upd_sql, [ptt, user, now, proj_nr, process, sub_process], server_key=server_key
    )
    if rowcount == 0:
        ins_sql = (
            f"INSERT INTO {_qtable(table)} ([projNr], [process], [subProcess], [ptt], [updated_by], [updated_at]) "
            f"VALUES (?, ?, ?, ?, ?, ?)"
        )
        execute_write(
            ins_sql, [proj_nr, process, sub_process, ptt, user, now], server_key=server_key
        )


def delete_ptt(proj_nr, process, sub_process, server_key=None):
    _, profile = get_server_profile(server_key)
    table = _table_name("ptt_manual", profile["driver"])
    sql = f"DELETE FROM {_qtable(table)} WHERE [projNr] = ? AND [process] = ? AND [subProcess] = ?"
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
        f"INSERT INTO {_qtable(table)} "
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


def save_infor_change_rows(rows, bearbeiter, info=None, server_key=None):
    """Speichert die vom Nutzer freigegebenen Korrekturwerte (Button 'übernehmen').

    info: optionaler Freitext (Richtext-HTML) aus dem Bestätigungs-PopUp, wird
    fuer jede Zeile derselben Übernahme identisch mitgespeichert.

    Alle Zeilen EINES Aufrufs (= ein Klick auf "Übernehmen") teilen sich
    zusätzlich eine neu generierte `vorgang_id` (UUID4-Hex) - das ist der
    zuverlässige Gruppierungsschlüssel für "1 Übernahme-Vorgang" in der GUI
    (siehe dokumentation.group_infor_changes_by_uebernahme), weil
    `uebernahmedatum` nur Sekunden-Genauigkeit hat und daher allein NICHT
    garantiert eindeutig zwei getrennte, aber schnell aufeinanderfolgende
    Übernahmen derselben Person für dasselbe Projekt unterscheiden könnte.
    """
    _, profile = get_server_profile(server_key)
    table = _table_name("infor_changes", profile["driver"])
    now = _now_str()
    vorgang_id = uuid.uuid4().hex
    sql = (
        f"INSERT INTO {_qtable(table)} "
        f"([projNr], [uebernahmedatum], [bearbeiter], [process], [mtt], [ptt], [abweichung], [abweichung_pct], [ptt_neu], [status], [info], [vorgang_id]) "
        f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'offen', ?, ?)"
    )
    params = [
        (r["projNr"], now, bearbeiter, r["process"], r["mtt"], r["ptt"],
         r["abweichung"], r["abweichung_pct"], r["ptt_neu"], info, vorgang_id)
        for r in rows
    ]
    if params:
        execute_many(sql, params, server_key=server_key)
    return len(params)


def get_tact_time_check_history(proj_nr=None, server_key=None):
    _, profile = get_server_profile(server_key)
    table = _table_name("tact_time_check", profile["driver"])
    sql = f"SELECT * FROM {_qtable(table)}"
    params = []
    if proj_nr:
        sql += " WHERE [projNr] = ?"
        params.append(proj_nr)
    sql += " ORDER BY [bewertungsdatum] DESC"
    return execute_query(sql, params, server_key=server_key)


def get_infor_changes(proj_nr=None, server_key=None):
    _, profile = get_server_profile(server_key)
    table = _table_name("infor_changes", profile["driver"])
    sql = f"SELECT * FROM {_qtable(table)}"
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
