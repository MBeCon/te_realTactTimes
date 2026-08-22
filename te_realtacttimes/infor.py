# =============================================================================
# te_realtacttimes/infor.py – Anbindung an Infor (vorbereitet, kommt später)
# teRealTactTimes – technosert electronic GmbH
# =============================================================================
"""
Platzhalter-Modul für die spätere direkte Anbindung an Infor (siehe Prompt
Abschnitt 5.2.3.2: "infor.py (vorsehen, kommt erst später)").

Aktuell endet der Workflow "Nach Infor übertragen" bewusst mit dem Speichern
der Korrekturwerte in dbo.teCalc_COR_INFORchanges (siehe dokumentation.py) -
die tatsächliche Übertragung der neuen Planzeiten (PTT_neu) nach Infor selbst
ist fachlich/technisch noch nicht spezifiziert (Schnittstelle, Format,
Berechtigung). Dieses Modul stellt die Stelle bereit, an der das später
angeschlossen wird, ohne den Rest der Anwendung ändern zu müssen.
"""

import logging

logger = logging.getLogger(__name__)


def is_available():
    """Liefert False, solange keine echte Infor-Schnittstelle angebunden ist."""
    return False


def push_changes(change_rows):
    """Würde die freigegebenen Änderungen (PTT_neu) nach Infor übertragen.

    TODO (sobald spezifiziert): Infor-Schnittstelle (API/Datei/DB-Link),
    Feldmapping projNr/process -> Infor-Auftragsstruktur, Fehlerbehandlung,
    Rückmeldung/Status-Update in dbo.teCalc_COR_INFORchanges.status.
    """
    logger.warning(
        "infor.push_changes() aufgerufen, aber Infor-Anbindung ist noch nicht "
        "implementiert. %s Datensätze wurden NICHT nach Infor übertragen, "
        "sondern nur in teCalc_COR_INFORchanges dokumentiert.",
        len(change_rows),
    )
    raise NotImplementedError(
        "Die direkte Übertragung nach Infor ist noch nicht angebunden. "
        "Die Korrekturwerte wurden in teCalc_COR_INFORchanges dokumentiert "
        "und können manuell in Infor nachgepflegt werden."
    )
