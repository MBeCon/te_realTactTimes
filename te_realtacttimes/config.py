# =============================================================================
# te_realtacttimes/config.py – Zentrale Konfiguration
# teRealTactTimes – technosert electronic GmbH
# =============================================================================
"""
Zentrale Konstanten der Anwendung. Alle anderen Module importieren
ausschließlich aus config, es werden keine Konstanten dupliziert.

Laufzeit-veränderliche Einstellungen (aktiver Server, Grenzwerte, aktueller
Bearbeiter) liegen NICHT hier, sondern in settings.json (siehe settings.py).
"""

import os

# ----- Pfade -----------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)  # .../te_realTactTimes (übergeordneter Projektordner)

TEMPLATE_DIR = os.path.join(BASE_DIR, "gui", "templates")
STATIC_DIR = os.path.join(BASE_DIR, "gui", "static")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
LOG_FILE = os.path.join(BASE_DIR, "app.log")

# Externe Quelldaten (CSV-Importe für den Demo/Test-Modus), liegt eine Ebene
# über dem Python-Package, siehe Doku Abschnitt 8 der Design-Vorgabe.
DEMO_DATA_DIR = os.path.join(PROJECT_ROOT, "data")
DEMO_DB_FILE = os.path.join(BASE_DIR, "demo_te_realtacttimes.sqlite3")

# ----- App-Stammdaten ----------------------------------------------------------
APP_NAME = "teRealTactTimes"
APP_FULL_NAME = "te RealTactTimes"
APP_DESCRIPTION = "Reale Messdaten der Maschinenzeiten nach Infor übertragen"
APP_VERSION = "0.1.0"
APP_PORT = 5000
FIRMA = "technosert electronic GmbH"
FIRMA_URL = "https://www.technosert.com"

# ----- Datenbankserver ---------------------------------------------------------
# Es kann laut Vorgabe zu genau einem von zwei produktiven SQL-Server-Profilen
# verbunden werden (te / MBe). Zusätzlich gibt es einen dritten, klar
# gekennzeichneten Demo/Test-Modus auf Basis von SQLite mit den mitgelieferten
# CSV-Beispieldaten (data/MAR_TactTimes*.csv) – siehe README.md.
DB_SERVERS = {
    "te": {
        "label": "technosert – SRVDB / DataWarehouse",
        "driver": "mssql",
        "server": "SRVDB",
        "database": "DataWarehouse",
        "odbc_driver": "ODBC Driver 17 for SQL Server",
        "trusted_connection": True,
    },
    "mbe": {
        "label": "MBe-Consulting – localhost",
        "driver": "mssql",
        "server": "localhost",
        "database": "te_realTactTimes",
        "odbc_driver": "ODBC Driver 17 for SQL Server",
        "trusted_connection": True,
    },
    "demo": {
        "label": "Demo/Test (lokale SQLite, Beispieldaten)",
        "driver": "sqlite",
        "path": DEMO_DB_FILE,
    },
}
DEFAULT_SERVER_KEY = "demo"

# ----- Quelltabellen (Ist-Daten MTT, extern per ETL befüllt) -------------------
SOURCE_TABLES = {
    "mtt_calc": "MAR_TactTimesCalc",   # gemittelt über Lose: projNr/process/subProcess
    "mtt_detail": "MAR_TactTimes",     # je Fertigungslos: projNr/lot/process/subProcess
}

# ----- Anwendungstabellen (werden von der App selbst angelegt) -----------------
APP_TABLES = {
    "tact_time_check": "dbo.teCalc_COR_tactTimesCheck",
    "infor_changes": "dbo.teCalc_COR_INFORchanges",
    # PTT (Plan-Taktzeiten) sind laut Vorgabe <TBD> - die eigentliche Quelle aus
    # dem Leitstand ist noch nicht spezifiziert. Bis dahin dient diese Tabelle
    # als manuelle Übergangslösung (Pflege über Konfiguration -> PTT-Pflege),
    # in der Granularität projNr/process/subProcess, damit die Anbindung der
    # echten Leitstand-Quelle später ohne Strukturänderung möglich ist.
    "ptt_manual": "dbo.teCalc_PTT_manual",
}

# ----- Grenzwerte (Default, überschreibbar über settings.json/GUI) -------------
DEFAULT_THRESHOLDS = {
    "warn_lower_pct": -15.0,   # Warngrenze unteres Limit in %
    "warn_upper_pct": 15.0,    # Warngrenze oberes Limit in %
    "action_lower_pct": -30.0,  # Aktionsgrenze unteres Limit in %
    "action_upper_pct": 30.0,   # Aktionsgrenze oberes Limit in %
}

# Bewertungsstatus-Schlüssel (für Markierung/Sortierung/Badges)
STATUS_OK = "ok"
STATUS_WARN = "warn"
STATUS_ACTION = "action"
STATUS_NO_PTT = "no_ptt"

STATUS_LABELS = {
    STATUS_OK: "OK",
    STATUS_WARN: "Warngrenze",
    STATUS_ACTION: "Aktionsgrenze",
    STATUS_NO_PTT: "PTT fehlt",
}
