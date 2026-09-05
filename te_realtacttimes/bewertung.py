# =============================================================================
# te_realtacttimes/bewertung.py – Vergleichslogik MTT vs. PTT (TTCheck)
# teRealTactTimes – technosert electronic GmbH
# =============================================================================
"""
Reine Python-Logik ohne Flask- und ohne DB-Abhängigkeit (testbar, wiederverwendbar).
Nimmt einfache Datenstrukturen (Listen von dicts, wie sie db.database liefert)
entgegen und gibt ebensolche zurück. Die eigentlichen DB-Zugriffe erfolgen vorher
in routes.py über db.database.*.

Zwei Betrachtungsebenen:
  - Prozessebene (TTCheck-Liste, Abschnitt 5.3.3.1): 1 Zeile je projNr+process,
    MTT/PTT über alle subProcess dieses process aufsummiert.
  - Subprozessebene (Projektdetails, Abschnitt 5.3.3.2): 1 Zeile je
    projNr+process+subProcess, jeweils eigene Abweichung.
"""

import config

STATUS_OK = config.STATUS_OK
STATUS_WARN = config.STATUS_WARN
STATUS_ACTION = config.STATUS_ACTION
STATUS_NO_PTT = config.STATUS_NO_PTT


def validate_thresholds(thresholds):
    """Prüft: Warngrenze muss innerhalb der Aktionsgrenze liegen. Liefert Fehlerliste."""
    errors = []
    wl, wu = thresholds["warn_lower_pct"], thresholds["warn_upper_pct"]
    al, au = thresholds["action_lower_pct"], thresholds["action_upper_pct"]
    if wl > wu:
        errors.append("Warngrenze: unteres Limit darf nicht größer als oberes Limit sein.")
    if al > au:
        errors.append("Aktionsgrenze: unteres Limit darf nicht größer als oberes Limit sein.")
    if al > wl:
        errors.append("Aktionsgrenze (unten) muss außerhalb (kleiner/gleich) der Warngrenze (unten) liegen.")
    if au < wu:
        errors.append("Aktionsgrenze (oben) muss außerhalb (größer/gleich) der Warngrenze (oben) liegen.")
    return errors


def classify(abweichung_pct, thresholds):
    """Ordnet eine prozentuale Abweichung einem Status (ok/warn/action/no_ptt) zu."""
    if abweichung_pct is None:
        return STATUS_NO_PTT
    if abweichung_pct < thresholds["action_lower_pct"] or abweichung_pct > thresholds["action_upper_pct"]:
        return STATUS_ACTION
    if abweichung_pct < thresholds["warn_lower_pct"] or abweichung_pct > thresholds["warn_upper_pct"]:
        return STATUS_WARN
    return STATUS_OK


def _deviation(mtt, ptt):
    """(Abw., Abw%) für MTT-PTT bzw. (MTT-PTT)/PTT. None wenn PTT fehlt oder 0."""
    if mtt is None or ptt is None:
        return None, None
    abw = mtt - ptt
    if ptt == 0:
        return abw, None
    return abw, (abw / ptt) * 100.0


def compute_subprocess_level(mtt_calc_rows, ptt_map, thresholds):
    """Zeilen je projNr+process+subProcess mit eigener Abweichung (Projektdetails)."""
    result = []
    for row in mtt_calc_rows:
        key = (row["projNr"], row["process"], row["subProcess"])
        mtt = row.get("board_tactTime_brutto")
        ptt = ptt_map.get(key)
        abw, abw_pct = _deviation(mtt, ptt)
        status = classify(abw_pct, thresholds)
        result.append({
            **row,
            "mtt": mtt,
            "ptt": ptt,
            "abweichung": abw,
            "abweichung_pct": abw_pct,
            "status": status,
            "status_label": config.STATUS_LABELS[status],
        })
    return result


def compute_process_level(mtt_calc_rows, ptt_map, thresholds):
    """Zeilen je projNr+process: MTT/PTT über die subProcess-Zeilen aufsummiert (TTCheck-Liste)."""
    groups = {}
    order = []
    for row in mtt_calc_rows:
        gkey = (row["projNr"], row["process"])
        if gkey not in groups:
            groups[gkey] = []
            order.append(gkey)
        groups[gkey].append(row)

    result = []
    for gkey in order:
        proj_nr, process = gkey
        rows = groups[gkey]
        # Fehlende Werte einzelner Subprozesse werden bei der Summe uebersprungen
        # (nicht als 0 gezaehlt, aber auch nicht die ganze Summe auf None setzen) -
        # nur wenn ALLE Subprozesse eines process fehlen, ist die Summe None
        # (=> Status "... fehlt").
        mtt_values = [v for v in (r.get("board_tactTime_brutto") for r in rows) if v is not None]
        mtt_sum = sum(mtt_values) if mtt_values else None

        ptt_values = [v for v in (ptt_map.get((proj_nr, process, r["subProcess"])) for r in rows) if v is not None]
        ptt_sum = sum(ptt_values) if ptt_values else None

        abw, abw_pct = _deviation(mtt_sum, ptt_sum)
        status = classify(abw_pct, thresholds)
        result.append({
            "projNr": proj_nr,
            "process": process,
            "prozessOrder": rows[0].get("prozessOrder"),
            "sub_process_count": len(rows),
            "mtt": mtt_sum,
            "ptt": ptt_sum,
            "abweichung": abw,
            "abweichung_pct": abw_pct,
            "status": status,
            "status_label": config.STATUS_LABELS[status],
        })
    return result


def filter_process_rows(rows, proj_nr=None, process=None, status=None, proj_nr_list=None):
    filtered = rows
    if proj_nr:
        needle = proj_nr.strip().lower()
        filtered = [r for r in filtered if needle in r["projNr"].lower()]
    if proj_nr_list is not None:
        allowed = set(proj_nr_list)
        filtered = [r for r in filtered if r["projNr"] in allowed]
    if process:
        needle = process.strip().lower()
        filtered = [r for r in filtered if needle in r["process"].lower()]
    if status:
        filtered = [r for r in filtered if r["status"] == status]
    return filtered


_SORT_KEYS = {
    "projNr": lambda r: (r["projNr"], r["process"]),
    "process": lambda r: (r["process"], r["projNr"]),
    "abweichung_pct": lambda r: (
        abs(r["abweichung_pct"]) if r["abweichung_pct"] is not None else -1
    ),
}


def sort_process_rows(rows, sort_by="projNr", descending=False):
    key_func = _SORT_KEYS.get(sort_by, _SORT_KEYS["projNr"])
    return sorted(rows, key=key_func, reverse=descending)


def totals(process_rows):
    """Summen ueber die PROZESS-Zeilen eines Projekts (Subprozesse fliessen
    bewusst NICHT ein - die sind in den Projektdetails nur Zusatzinformation):
    Summe MTT, Summe PTT, Summe Abw. Fehlende Werte (None, z.B. PTT fehlt fuer
    einen Prozess) werden bei der jeweiligen Summe uebersprungen statt sie auf
    0 zu setzen."""
    mtt_sum = sum(r["mtt"] for r in process_rows if r.get("mtt") is not None)
    ptt_sum = sum(r["ptt"] for r in process_rows if r.get("ptt") is not None)
    abweichung_sum = sum(r["abweichung"] for r in process_rows if r.get("abweichung") is not None)
    return {"mtt_sum": mtt_sum, "ptt_sum": ptt_sum, "abweichung_sum": abweichung_sum}
