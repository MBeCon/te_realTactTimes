# =============================================================================
# te_realtacttimes/gui/routes.py – Flask-Routen
# teRealTactTimes – technosert electronic GmbH
# =============================================================================
"""
Alle Blueprints der Anwendung in einer Datei, gruppiert per Kommentar-Banner.
Route-Funktionen bleiben dünn: Formular/Query lesen -> db.*/Domänen-Modul
aufrufen -> render_template/redirect + flash(). Geschäftslogik lebt in
bewertung.py/dokumentation.py/db/database.py, nicht hier.
"""

import logging
import os
import threading

from flask import (
    Blueprint, flash, g, jsonify, redirect, render_template,
    request, url_for,
)

import bewertung
import config
import dokumentation
import settings
from db import database

logger = logging.getLogger(__name__)

main_bp = Blueprint("main", __name__)
bewerten_bp = Blueprint("bewerten", __name__, url_prefix="/bewerten")
konfiguration_bp = Blueprint("konfiguration", __name__, url_prefix="/konfiguration")
api_bp = Blueprint("api", __name__, url_prefix="/api")


# =============================================================================
# ===== Hilfsfunktionen =====
# =============================================================================

def _current_user():
    user = settings.get_current_user()
    return user or "Unbekannt"


def _active_server_ok():
    """Prüft, ob überhaupt ein Server aktiv/konfiguriert ist."""
    try:
        database.get_server_profile()
        return True
    except Exception:  # noqa: BLE001
        return False


def _get_ptt_map(proj_nr=None):
    """Lädt die PTT-Map, robust gegenüber einer (noch) fehlenden teCalc_PTT_manual.

    Solange die echte Leitstand-Anbindung <TBD> ist, ist die manuelle
    PTT-Tabelle auf manchen Servern eventuell noch nicht angelegt oder leer.
    In dem Fall soll TTCheck trotzdem mit den vorhandenen MTT-Daten laufen
    (jede Zeile bekommt dann Status 'PTT fehlt' statt eines Abbruchs) - siehe
    bewertung.classify()/STATUS_NO_PTT.
    """
    try:
        database.ensure_app_tables()
    except Exception:  # noqa: BLE001
        logger.exception("Konnte App-Tabellen (u.a. teCalc_PTT_manual) nicht anlegen")
    try:
        return database.get_ptt_map(proj_nr)
    except Exception as exc:  # noqa: BLE001
        logger.exception("PTT-Daten konnten nicht geladen werden, TTCheck läuft ohne PTT weiter")
        if not getattr(g, "_ptt_warning_flashed", False):
            flash(
                f"PTT-Daten (teCalc_PTT_manual) konnten nicht geladen werden – "
                f"TTCheck zeigt die MTT-Daten trotzdem, Status 'PTT fehlt': {exc}",
                "warning",
            )
            g._ptt_warning_flashed = True
        return {}


# =============================================================================
# ===== main_bp – Startseite, allgemeine Aktionen =====
# =============================================================================

@main_bp.route("/")
def index():
    active_server = settings.get_active_server()
    return render_template(
        "main/index.html",
        servers=config.DB_SERVERS,
        active_server=active_server,
    )


@main_bp.route("/server/wechseln", methods=["POST"])
def server_wechseln():
    server_key = request.form.get("server_key")
    if server_key not in config.DB_SERVERS:
        flash(f"Unbekanntes Server-Profil: {server_key}", "error")
        return redirect(request.referrer or url_for("main.index"))

    ok, message = database.test_connection(server_key)
    if ok:
        settings.update("active_server", server_key)
        try:
            database.ensure_app_tables(server_key)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Konnte App-Tabellen nicht anlegen")
            flash(f"Verbunden, aber Tabellenanlage fehlgeschlagen: {exc}", "warning")
        flash(message, "success")
    else:
        flash(message, "error")
    return redirect(request.referrer or url_for("main.index"))


@main_bp.route("/shutdown", methods=["POST"])
def shutdown():
    logger.info("Software beenden angefordert.")

    def _stop():
        import time
        time.sleep(0.5)
        os._exit(0)

    threading.Thread(target=_stop, daemon=True).start()
    return render_template("main/shutdown.html")


@main_bp.route("/tacttimes")
def tacttimes_popup():
    """PopUp Startseite: kompletter Inhalt der Datentabelle MAR_TactTimes."""
    try:
        rows = database.get_mtt_detail_alle()
        error = None
    except Exception as exc:  # noqa: BLE001
        logger.exception("TactTimes-PopUp: Laden von MAR_TactTimes fehlgeschlagen")
        rows = []
        error = str(exc)
    return render_template("main/_tacttimes.html", rows=rows, error=error,
                            table_name=config.SOURCE_TABLES["mtt_detail"])


@main_bp.route("/tacttimescalc")
def tacttimescalc_popup():
    """PopUp Startseite: kompletter Inhalt der Datentabelle MAR_TactTimesCalc."""
    try:
        rows = database.get_mtt_calc()
        error = None
    except Exception as exc:  # noqa: BLE001
        logger.exception("TactTimesCalc-PopUp: Laden von MAR_TactTimesCalc fehlgeschlagen")
        rows = []
        error = str(exc)
    return render_template("main/_tacttimescalc.html", rows=rows, error=error,
                            table_name=config.SOURCE_TABLES["mtt_calc"])


# =============================================================================
# ===== bewerten_bp – TTCheck, Projektdetails, Processdetails, Infor-Übernahme
# =============================================================================

@bewerten_bp.route("/")
def index():
    sort_by = request.args.get("sort", "projNr")
    descending = request.args.get("dir", "asc") == "desc"
    proj_nr_filter = request.args.get("proj_nr", "").strip()
    process_filter = request.args.get("process", "").strip()
    lot_filter = request.args.get("lot", "").strip()
    status_filter = request.args.get("status", "").strip() or None
    ran = request.args.get("ran") == "1"
    selected_proj = request.args.get("selected_proj", "").strip() or None

    rows = []
    error = None
    if ran:
        try:
            proj_nr_list = None
            if lot_filter:
                lot_rows = database.execute_query(
                    f"SELECT DISTINCT [projNr] FROM [{config.SOURCE_TABLES['mtt_detail']}] WHERE [lot] LIKE ?",
                    [f"%{lot_filter}%"],
                )
                proj_nr_list = [r["projNr"] for r in lot_rows]

            mtt_rows = database.get_mtt_calc()
            ptt_map = _get_ptt_map()
            thresholds = settings.get_thresholds()
            proc_rows = bewertung.compute_process_level(mtt_rows, ptt_map, thresholds)
            proc_rows = bewertung.filter_process_rows(
                proc_rows, proj_nr=proj_nr_filter or None, process=process_filter or None,
                status=status_filter, proj_nr_list=proj_nr_list,
            )
            rows = bewertung.sort_process_rows(proc_rows, sort_by=sort_by, descending=descending)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Fehler beim TTCheck")
            error = str(exc)
            flash(f"TTCheck fehlgeschlagen: {exc}", "error")

    projektdetails = None
    if selected_proj:
        projektdetails = _load_projektdetails(selected_proj, request.args.get("proc_filter", "").strip() or None)

    return render_template(
        "bewerten/index.html",
        rows=rows, ran=ran, error=error,
        sort_by=sort_by, descending=descending,
        proj_nr_filter=proj_nr_filter, process_filter=process_filter,
        lot_filter=lot_filter, status_filter=status_filter,
        status_labels=config.STATUS_LABELS,
        selected_proj=selected_proj,
        projektdetails=projektdetails,
        thresholds=settings.get_thresholds(),
    )


@bewerten_bp.route("/ttcheck", methods=["POST"])
def ttcheck():
    try:
        mtt_rows = database.get_mtt_calc()
        ptt_map = _get_ptt_map()
        thresholds = settings.get_thresholds()
        proc_rows = bewertung.compute_process_level(mtt_rows, ptt_map, thresholds)
        count = dokumentation.record_ttcheck_run(proc_rows, _current_user())
        flash(f"TTCheck ausgeführt und dokumentiert ({count} Zeilen).", "success")
    except Exception as exc:  # noqa: BLE001
        logger.exception("TTCheck fehlgeschlagen")
        flash(f"TTCheck fehlgeschlagen: {exc}", "error")
    return redirect(url_for("bewerten.index", ran=1, **_keep_args()))


def _keep_args():
    keep = {}
    for key in ("sort", "dir", "proj_nr", "process", "lot", "status", "selected_proj", "proc_filter"):
        val = request.args.get(key) or request.form.get(key)
        if val:
            keep[key] = val
    return keep


def _load_projektdetails(proj_nr, proc_filter=None):
    mtt_rows = database.get_mtt_calc(proj_nr)
    empty_totals = {"board_tactTime_brutto_sum": 0, "panel_tactTime_brutto_sum": 0}
    if not mtt_rows:
        return {"proj_nr": proj_nr, "groups": [], "processes": [], "totals": empty_totals, "proc_filter": proc_filter}
    ptt_map = _get_ptt_map(proj_nr)
    thresholds = settings.get_thresholds()
    sub_rows = bewertung.compute_subprocess_level(mtt_rows, ptt_map, thresholds)
    proc_rows = bewertung.compute_process_level(mtt_rows, ptt_map, thresholds)
    processes = sorted({r["process"] for r in sub_rows})

    if proc_filter:
        sub_rows = [r for r in sub_rows if r["process"] == proc_filter]
        proc_rows = [r for r in proc_rows if r["process"] == proc_filter]

    sub_by_process = {}
    for r in sub_rows:
        sub_by_process.setdefault(r["process"], []).append(r)

    groups = []
    for proc in sorted(proc_rows, key=lambda r: (r.get("prozessOrder") if r.get("prozessOrder") is not None else 999, r["process"])):
        groups.append({"process_row": proc, "sub_rows": sub_by_process.get(proc["process"], [])})

    totals = bewertung.totals(sub_rows)
    return {"proj_nr": proj_nr, "groups": groups, "processes": processes, "totals": totals, "proc_filter": proc_filter}


@bewerten_bp.route("/projekt/<proj_nr>")
def projekt_partial(proj_nr):
    proc_filter = request.args.get("proc_filter", "").strip() or None
    details = _load_projektdetails(proj_nr, proc_filter)
    return render_template("bewerten/_projektdetails.html", d=details, status_labels=config.STATUS_LABELS)


@bewerten_bp.route("/prozess/<proj_nr>/<process>")
def prozess_popup(proj_nr, process):
    rows = database.get_mtt_detail(proj_nr, process)
    return render_template("bewerten/_processdetails.html", proj_nr=proj_nr, process=process, rows=rows)


@bewerten_bp.route("/infor/uebernehmen", methods=["POST"])
def infor_uebernehmen():
    proj_nr = request.form.get("proj_nr", "").strip()
    processes = request.form.getlist("uebernehmen")
    if not proj_nr:
        flash("Kein Projekt ausgewählt.", "error")
        return redirect(url_for("bewerten.index", **_keep_args()))
    if not processes:
        flash("Es wurde kein Prozess zur Übernahme markiert.", "warning")
        return redirect(url_for("bewerten.index", selected_proj=proj_nr, **_keep_args()))

    try:
        details = _load_projektdetails(proj_nr)
        by_process = {g["process_row"]["process"]: g["process_row"] for g in details["groups"]}

        selected_rows = []
        for process in processes:
            proc_row = by_process.get(process)
            if proc_row is None:
                continue
            mtt_val = proc_row.get("mtt")
            korrektur_field = f"korrektur_{process}"
            ptt_neu_raw = request.form.get(korrektur_field, "").strip().replace(",", ".")
            try:
                ptt_neu = float(ptt_neu_raw) if ptt_neu_raw else mtt_val
            except ValueError:
                ptt_neu = mtt_val
            selected_rows.append({
                "projNr": proj_nr, "process": process, "mtt": mtt_val, "ptt": proc_row.get("ptt"),
                "abweichung": proc_row.get("abweichung"), "abweichung_pct": proc_row.get("abweichung_pct"),
                "ptt_neu": ptt_neu,
            })

        count = dokumentation.record_infor_transfer(selected_rows, _current_user())
        flash(f"{count} Korrektur(en) für {proj_nr} nach teCalc_COR_INFORchanges übernommen.", "success")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Infor-Übernahme fehlgeschlagen")
        flash(f"Übernahme fehlgeschlagen: {exc}", "error")

    return redirect(url_for("bewerten.index", selected_proj=proj_nr, **_keep_args()))


# =============================================================================
# ===== konfiguration_bp – Grenzwerte, SQL-Server, Webserver, PTT-Pflege =====
# =============================================================================

@konfiguration_bp.route("/")
def index():
    ptt_rows = []
    db_error = None
    if _active_server_ok():
        try:
            # Selbstheilung: Falls die App-Tabellen (u.a. teCalc_PTT_manual) auf dem
            # aktiven Server noch fehlen oder bei einem früheren Verbinden nicht
            # angelegt werden konnten, hier erneut versuchen.
            database.ensure_app_tables()
        except Exception:  # noqa: BLE001
            logger.exception("Konnte App-Tabellen beim Aufruf der Konfigurationsseite nicht anlegen")
        try:
            ptt_rows = database.get_ptt_rows()
        except Exception as exc:  # noqa: BLE001
            logger.exception("PTT-Einträge konnten nicht geladen werden")
            db_error = str(exc)

    return render_template(
        "konfiguration/index.html",
        servers=config.DB_SERVERS,
        active_server=settings.get_active_server(),
        thresholds=settings.get_thresholds(),
        current_user=settings.get_current_user(),
        webserver=settings.get("webserver"),
        ptt_rows=ptt_rows,
        db_error=db_error,
    )


@konfiguration_bp.route("/grenzwerte", methods=["POST"])
def grenzwerte_speichern():
    try:
        thresholds = {
            "warn_lower_pct": float(request.form["warn_lower_pct"].replace(",", ".")),
            "warn_upper_pct": float(request.form["warn_upper_pct"].replace(",", ".")),
            "action_lower_pct": float(request.form["action_lower_pct"].replace(",", ".")),
            "action_upper_pct": float(request.form["action_upper_pct"].replace(",", ".")),
        }
    except (KeyError, ValueError):
        flash("Ungültige Eingabe bei den Grenzwerten.", "error")
        return redirect(url_for("konfiguration.index"))

    errors = bewertung.validate_thresholds(thresholds)
    if errors:
        for err in errors:
            flash(err, "error")
        return redirect(url_for("konfiguration.index"))

    settings.update("thresholds", thresholds)
    flash("Grenzwerte gespeichert.", "success")
    return redirect(url_for("konfiguration.index"))


@konfiguration_bp.route("/server", methods=["POST"])
def server_speichern():
    server_key = request.form.get("server_key")
    if server_key not in config.DB_SERVERS:
        flash("Unbekanntes Server-Profil.", "error")
        return redirect(url_for("konfiguration.index"))
    ok, message = database.test_connection(server_key)
    if ok:
        settings.update("active_server", server_key)
        try:
            database.ensure_app_tables(server_key)
        except Exception as exc:  # noqa: BLE001
            flash(f"Verbunden, aber Tabellenanlage fehlgeschlagen: {exc}", "warning")
        flash(message, "success")
    else:
        flash(message, "error")
    return redirect(url_for("konfiguration.index"))


@konfiguration_bp.route("/webserver", methods=["POST"])
def webserver_speichern():
    host = request.form.get("host", "127.0.0.1").strip()
    try:
        port = int(request.form.get("port", config.APP_PORT))
    except ValueError:
        flash("Ungültiger Port.", "error")
        return redirect(url_for("konfiguration.index"))
    settings.update("webserver", {"host": host, "port": port})
    flash("Webserver-Einstellung gespeichert. Wirkt erst nach Neustart der Anwendung.", "info")
    return redirect(url_for("konfiguration.index"))


@konfiguration_bp.route("/bearbeiter", methods=["POST"])
def bearbeiter_speichern():
    name = request.form.get("current_user", "").strip()
    settings.update("current_user", name)
    flash("Aktueller Bearbeiter gespeichert.", "success")
    return redirect(url_for("konfiguration.index"))


@konfiguration_bp.route("/ptt/speichern", methods=["POST"])
def ptt_speichern():
    proj_nr = request.form.get("projNr", "").strip()
    process = request.form.get("process", "").strip()
    sub_process = request.form.get("subProcess", "").strip()
    ptt_raw = request.form.get("ptt", "").strip().replace(",", ".")
    if not (proj_nr and process and sub_process and ptt_raw):
        flash("Bitte projNr, process, subProcess und PTT ausfüllen.", "error")
        return redirect(url_for("konfiguration.index"))
    try:
        ptt = float(ptt_raw)
    except ValueError:
        flash("PTT muss eine Zahl sein.", "error")
        return redirect(url_for("konfiguration.index"))
    database.upsert_ptt(proj_nr, process, sub_process, ptt, _current_user())
    flash("PTT gespeichert.", "success")
    return redirect(url_for("konfiguration.index"))


@konfiguration_bp.route("/ptt/loeschen", methods=["POST"])
def ptt_loeschen():
    proj_nr = request.form.get("projNr", "")
    process = request.form.get("process", "")
    sub_process = request.form.get("subProcess", "")
    database.delete_ptt(proj_nr, process, sub_process)
    flash("PTT-Eintrag gelöscht.", "success")
    return redirect(url_for("konfiguration.index"))


@konfiguration_bp.route("/nutzerrechte")
def nutzerrechte():
    flash("Nutzerrechte-Verwaltung ist noch nicht implementiert (siehe Prompt: kommt erst später).", "info")
    return redirect(url_for("konfiguration.index"))


# =============================================================================
# ===== api_bp – kleine JSON-Hilfsendpunkte =====
# =============================================================================

@api_bp.route("/server-test")
def server_test():
    server_key = request.args.get("server", settings.get_active_server())
    ok, message = database.test_connection(server_key)
    return jsonify({"ok": ok, "message": message})


@api_bp.route("/kpis")
def kpis_stub():
    return jsonify({"ok": False, "message": "KPIs sind laut Vorgabe noch nicht implementiert (kommt später)."})
