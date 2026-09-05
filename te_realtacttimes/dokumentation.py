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


def record_infor_transfer(selected_rows, bearbeiter, info=None, server_key=None):
    """Speichert die vom Nutzer für die Infor-Übernahme freigegebenen Korrekturen.

    selected_rows: Liste von dicts mit projNr, process, mtt, ptt, abweichung,
    abweichung_pct, ptt_neu (Pflichtfeld - der neue, nach Infor zu übertragende
    Wert für board_tactTime_brutto).
    info: optionaler Freitext (Richtext-HTML) aus dem Bestätigungs-PopUp.
    """
    if not bearbeiter:
        raise ValueError("Bearbeiter/Name ist nicht gesetzt (siehe Konfiguration).")
    for row in selected_rows:
        if row.get("ptt_neu") is None:
            raise ValueError(f"Korrekturwert (PTT_neu) fehlt für Prozess {row.get('process')}.")
    count = database.save_infor_change_rows(selected_rows, bearbeiter, info=info, server_key=server_key)
    logger.info("Infor-Übernahme dokumentiert: %s Zeilen (Bearbeiter=%s)", count, bearbeiter)
    return count


def get_ttcheck_history(proj_nr=None, server_key=None):
    return database.get_tact_time_check_history(proj_nr, server_key=server_key)


def get_infor_changes(proj_nr=None, server_key=None):
    return database.get_infor_changes(proj_nr, server_key=server_key)


def group_infor_changes_by_uebernahme(rows):
    """Gruppiert die flachen Zeilen aus get_infor_changes() (1 Zeile je
    projNr+process) zu den eigentlichen Übernahme-VORGÄNGEN für die Seite
    "INFOR-Übernahme".

    Ein Klick auf "Übernehmen" im Bestätigungs-PopUp (bewerten.
    infor_uebernehmen) kann mehrere Prozesse auf einmal übernehmen - diese
    teilen sich denselben (projNr, uebernahmedatum, bearbeiter)-Schlüssel,
    weil sie in einem Rutsch mit demselben Zeitstempel gespeichert wurden
    (siehe database.save_infor_change_rows()). Für die GUI sollen sie als
    EIN Eintrag erscheinen (nicht als N Einzelzeilen je Prozess).

    Gruppierungsschlüssel: bevorzugt `vorgang_id` (seit der Einführung dieser
    Spalte pro Aufruf von database.save_infor_change_rows() eindeutig neu
    generiert - siehe dort). Für ältere, bereits vor dieser Spalte
    gespeicherte Zeilen (vorgang_id ist dort NULL) wird ersatzweise auf
    (projNr, uebernahmedatum, bearbeiter) zurückgegriffen - das ist für diese
    historischen Daten weiterhin die einzig verfügbare Näherung (siehe
    save_infor_change_rows()-Docstring: reine Sekunden-Genauigkeit von
    uebernahmedatum wäre für sich allein NICHT zuverlässig eindeutig, betrifft
    aber nur Alt-Daten ohne vorgang_id).

    Rückgabe: (projekte_uebersicht, uebernahmen)
    - projekte_uebersicht: 1 Eintrag {projNr, uebernahmedatum, bearbeiter,
      status} je distinct projNr - jeweils die Werte der NEUESTEN Übernahme
      dieses Projekts (rows kommt bereits `ORDER BY uebernahmedatum DESC`
      aus get_infor_changes(), der erste Treffer je projNr ist also
      automatisch der neueste). Sortiert nach Projektnummer aufsteigend -
      dient als Filterliste (Checkbox-Panel).
    - uebernahmen: 1 Eintrag {projNr, uebernahmedatum, bearbeiter, status,
      info, vorgang_id, prozesse: [Zeilen]} je Übernahme-Vorgang, in der
      Reihenfolge des ersten Auftretens (= neueste zuerst, da rows bereits
      DESC sortiert ist). `vorgang_id` ist bei Alt-Daten ohne diese Spalte
      `None` - der Aufrufer muss dann auf projNr/uebernahmedatum/bearbeiter
      zur Identifikation zurückgreifen (siehe
      gui.routes.uebernahme_details_popup()).
    """
    projekte_seen = set()
    projekte_uebersicht = []
    gruppen_index = {}
    uebernahmen = []
    for r in rows:
        proj_nr = r["projNr"]
        if proj_nr not in projekte_seen:
            projekte_seen.add(proj_nr)
            projekte_uebersicht.append({
                "projNr": proj_nr, "uebernahmedatum": r["uebernahmedatum"],
                "bearbeiter": r["bearbeiter"], "status": r["status"],
            })
        vorgang_id = r.get("vorgang_id")
        key = vorgang_id if vorgang_id else ("legacy", proj_nr, r["uebernahmedatum"], r["bearbeiter"])
        gruppe = gruppen_index.get(key)
        if gruppe is None:
            gruppe = {
                "projNr": proj_nr, "uebernahmedatum": r["uebernahmedatum"],
                "bearbeiter": r["bearbeiter"], "status": r["status"],
                "info": r.get("info"), "vorgang_id": vorgang_id, "prozesse": [],
            }
            gruppen_index[key] = gruppe
            uebernahmen.append(gruppe)
        gruppe["prozesse"].append(r)

    projekte_uebersicht.sort(key=lambda p: p["projNr"])
    return projekte_uebersicht, uebernahmen
