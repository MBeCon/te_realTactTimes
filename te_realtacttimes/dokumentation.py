# =============================================================================
# te_realtacttimes/dokumentation.py – Dokumentation der durchgeführten Bewertung
# teRealTactTimes – technosert electronic GmbH
# =============================================================================
"""
Kapselt die Geschäftsregeln rund um das Dokumentieren von Bewertungen
(dbo.teCalc_COR_tactTimesCheck) und Infor-Übernahmen (dbo.teCalc_COR_INFORchanges).
Ruft ausschließlich db.database auf - kein SQL in dieser Datei.
"""

import logging

from db import database

logger = logging.getLogger(__name__)


def record_ttcheck_run(process_level_rows, bearbeiter, server_key=None):
    """Speichert einen Snapshot des TTCheck-Laufs (alle projNr/process-Zeilen).

    Wird bei jedem Ausführen von [TTCheck] auf der Seite "Bewerten" aufgerufen,
    damit jede Bewertung nachvollziehbar dokumentiert ist (Historie/Audit-Trail).
    """
    if not bearbeiter:
        raise ValueError("Bearbeiter/Name ist nicht gesetzt (siehe Konfiguration).")
    count = database.save_tact_time_check_rows(process_level_rows, bearbeiter, server_key=server_key)
    logger.info("TTCheck-Snapshot gespeichert: %s Zeilen (Bearbeiter=%s)", count, bearbeiter)
    return count


def record_infor_transfer(selected_rows, bearbeiter, server_key=None):
    """Speichert die vom Nutzer für die Infor-Übernahme freigegebenen Korrekturen.

    selected_rows: Liste von dicts mit projNr, process, mtt, ptt, abweichung,
    abweichung_pct, ptt_neu (Pflichtfeld - der neue, nach Infor zu übertragende
    Wert für board_tactTime_brutto).
    """
    if not bearbeiter:
        raise ValueError("Bearbeiter/Name ist nicht gesetzt (siehe Konfiguration).")
    for row in selected_rows:
        if row.get("ptt_neu") is None:
            raise ValueError(f"Korrekturwert (PTT_neu) fehlt für Prozess {row.get('process')}.")
    count = database.save_infor_change_rows(selected_rows, bearbeiter, server_key=server_key)
    logger.info("Infor-Übernahme dokumentiert: %s Zeilen (Bearbeiter=%s)", count, bearbeiter)
    return count


def get_ttcheck_history(proj_nr=None, server_key=None):
    return database.get_tact_time_check_history(proj_nr, server_key=server_key)


def get_infor_changes(proj_nr=None, server_key=None):
    return database.get_infor_changes(proj_nr, server_key=server_key)
