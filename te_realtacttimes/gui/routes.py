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
ptt_bp = Blueprint("ptt", __name__, url_prefix="/ptt")
infor_bp = Blueprint("infor", __name__, url_prefix="/infor")
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


def _get_stale_projekte():
    """Projekte, deren letzte Infor-Übernahme älter ist als die neueste

    Fertigungszeit in MAR_TactTimesCalc (siehe database.get_infor_lag_projects).
    Robust gegenüber (noch) fehlender teCalc_COR_INFORchanges-Tabelle - liefert
    dann einfach eine leere Markierung statt die Seite abstürzen zu lassen.

    Rückgabe: (stale_projekte: set, infor_changes_ddl: str|None). Letzteres ist
    gesetzt, wenn die Tabelle teCalc_COR_INFORchanges nicht automatisch angelegt
    werden konnte (z.B. mangels Berechtigung) - enthält dann die fertige
    CREATE TABLE-Anweisung, damit ein Admin sie manuell ausführen kann.
    """
    infor_changes_ddl = None
    try:
        tabellen_fehler = database.ensure_app_tables()
    except Exception:  # noqa: BLE001
        logger.exception("Konnte App-Tabellen (u.a. teCalc_COR_INFORchanges) nicht anlegen")
        tabellen_fehler = {}
    if "infor_changes" in tabellen_fehler:
        flash(
            f"Tabelle teCalc_COR_INFORchanges konnte nicht automatisch angelegt "
            f"werden: {tabellen_fehler['infor_changes']}",
            "warning",
        )
        try:
            infor_changes_ddl = database.get_ddl_for_table("infor_changes")
        except Exception:  # noqa: BLE001
            logger.exception("DDL für teCalc_COR_INFORchanges konnte nicht ermittelt werden")
    try:
        return database.get_infor_lag_projects(), infor_changes_ddl
    except Exception as exc:  # noqa: BLE001
        logger.exception("Infor-Übernahme-Status konnte nicht ermittelt werden")
        if not getattr(g, "_infor_lag_warning_flashed", False):
            flash(
                f"Status der Infor-Übernahme konnte nicht ermittelt werden – "
                f"Projekte-Liste zeigt daher keine Veraltet-Markierung: {exc}",
                "warning",
            )
            g._infor_lag_warning_flashed = True
        return set(), infor_changes_ddl


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

    # ===== Projekte-Liste (Checkbox-Auswahl links neben TactTimeCheck) =====
    # Solange proj_filter_active nicht gesetzt ist (frischer Seitenaufruf, noch
    # keine Auswahl getroffen), gelten alle Projekte als ausgewählt (kein
    # Regressionsverhalten ggü. vorher). Sobald das Projekte-Formular einmal
    # abgeschickt wurde, ist proj_filter_active=1 gesetzt und die tatsächlich
    # angehakten Projekte (auch: keines) sind maßgeblich.
    projekte_error = None
    try:
        alle_projekte = database.get_mtt_calc_projects()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Projektliste konnte nicht geladen werden")
        alle_projekte = []
        projekte_error = str(exc)

    stale_projekte, infor_changes_ddl = _get_stale_projekte()

    # Projekte-Liste: Projekte mit veralteter Infor-Uebernahme zuerst listen
    # (stabile Sortierung - behaelt die bisherige alphabetische Reihenfolge
    # innerhalb jeder der beiden Gruppen bei, siehe database.get_mtt_calc_projects()).
    alle_projekte = sorted(alle_projekte, key=lambda p: 0 if p in stale_projekte else 1)

    proj_filter_active = request.args.get("proj_filter_active") == "1"
    ausgewaehlte_projekte = request.args.getlist("proj") if proj_filter_active else list(alle_projekte)
    ausgewaehlte_projekte_set = set(ausgewaehlte_projekte)

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

            if proj_filter_active:
                # Schnittmenge mit der Los-Filterung (falls beides gesetzt ist);
                # sonst ist die Checkbox-Auswahl allein maßgeblich.
                if proj_nr_list is not None:
                    proj_nr_list = [p for p in proj_nr_list if p in ausgewaehlte_projekte_set]
                else:
                    proj_nr_list = list(ausgewaehlte_projekte_set)

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

    # Projektdetails werden nicht mehr serverseitig inline gerendert, sondern
    # als PopUp per AJAX nachgeladen (siehe bewerten.projekt_popup). Ist
    # selected_proj gesetzt (z.B. nach einer Infor-Übernahme, die zurück auf
    # das gerade bearbeitete Projekt verlinkt), öffnet das Template das PopUp
    # beim Laden automatisch mit demselben proc_filter.
    proc_filter = request.args.get("proc_filter", "").strip() or None

    return render_template(
        "bewerten/index.html",
        rows=rows, ran=ran, error=error,
        sort_by=sort_by, descending=descending,
        proj_nr_filter=proj_nr_filter, process_filter=process_filter,
        lot_filter=lot_filter, status_filter=status_filter,
        status_labels=config.STATUS_LABELS,
        selected_proj=selected_proj,
        proc_filter=proc_filter,
        thresholds=settings.get_thresholds(),
        alle_projekte=alle_projekte,
        ausgewaehlte_projekte=ausgewaehlte_projekte,
        ausgewaehlte_projekte_set=ausgewaehlte_projekte_set,
        proj_filter_active=proj_filter_active,
        projekte_error=projekte_error,
        stale_projekte=stale_projekte,
        infor_changes_ddl=infor_changes_ddl,
    )


@bewerten_bp.route("/ttcheck", methods=["POST"])
def ttcheck():
    try:
        mtt_rows = database.get_mtt_calc()
        ptt_map = _get_ptt_map()
        thresholds = settings.get_thresholds()
        proc_rows = bewertung.compute_process_level(mtt_rows, ptt_map, thresholds)

        # Nur die in der Projekte-Liste angehakten Projekte werden betrachtet
        # (das Projekte-Formular schickt proj_filter_active=1 immer mit, auch
        # wenn keine einzige Checkbox angehakt ist - dann werden bewusst keine
        # Zeilen berücksichtigt/gespeichert).
        if request.form.get("proj_filter_active") == "1":
            ausgewaehlte_projekte = request.form.getlist("proj")
            proc_rows = bewertung.filter_process_rows(proc_rows, proj_nr_list=ausgewaehlte_projekte)

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
    if (request.args.get("proj_filter_active") or request.form.get("proj_filter_active")) == "1":
        projekte = request.form.getlist("proj") or request.args.getlist("proj")
        keep["proj_filter_active"] = "1"
        keep["proj"] = projekte
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


@bewerten_bp.route("/projekt/<proj_nr>/popup")
def projekt_popup(proj_nr):
    """Projektdetails als PopUp (Klick auf eine TactTimeCheck-Zeile).

    Die Uebernahme-nach-Infor-Ansicht (Uebernehmen-Checkboxen + Korrektur-
    Spalten) wird immer direkt angezeigt - kein gesonderter Zwischenschritt
    mehr noetig.
    """
    proc_filter = request.args.get("proc_filter", "").strip() or None
    details = _load_projektdetails(proj_nr, proc_filter)
    return render_template("bewerten/_projektdetails_popup.html", d=details, status_labels=config.STATUS_LABELS)


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
    return render_template(
        "konfiguration/index.html",
        servers=config.DB_SERVERS,
        active_server=settings.get_active_server(),
        thresholds=settings.get_thresholds(),
        current_user=settings.get_current_user(),
        webserver=settings.get("webserver"),
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


@konfiguration_bp.route("/nutzerrechte")
def nutzerrechte():
    flash("Nutzerrechte-Verwaltung ist noch nicht implementiert (siehe Prompt: kommt erst später).", "info")
    return redirect(url_for("konfiguration.index"))


# =============================================================================
# ===== ptt_bp – manuelle PTT-Eingabe (Übergangslösung) =====
# =============================================================================
# Eigene Seite (eigener Menüpunkt in der linken Navigation), vorher ein Modal
# auf der Konfigurationsseite. Solange die echte Leitstand-Anbindung <TBD>
# ist, werden Plan-Taktzeiten hier manuell je projNr/process/subProcess in
# teCalc_PTT_manual gepflegt.

@ptt_bp.route("/")
def index():
    ptt_rows = []
    db_error = None
    ptt_manual_ddl = None
    if _active_server_ok():
        try:
            # Selbstheilung: Falls die App-Tabellen (u.a. teCalc_PTT_manual) auf dem
            # aktiven Server noch fehlen, hier erneut versuchen anzulegen. Jede
            # Tabelle wird von ensure_app_tables() einzeln angelegt - ein Fehler bei
            # einer anderen App-Tabelle (z.B. teCalc_COR_tactTimesCheck) blockiert
            # also nicht mehr das Anlegen von teCalc_PTT_manual.
            tabellen_fehler = database.ensure_app_tables()
        except Exception:  # noqa: BLE001
            logger.exception("Konnte App-Tabellen beim Aufruf der PTT-Eingabe nicht anlegen")
            tabellen_fehler = {}
        if "ptt_manual" in tabellen_fehler:
            # Konnte die Tabelle nicht automatisch angelegt werden (z.B. mangels
            # CREATE TABLE-Berechtigung auf dem Server), die konkrete Ursache
            # anzeigen + die DDL, damit sie ein Admin manuell ausführen kann.
            flash(
                f"Tabelle teCalc_PTT_manual konnte nicht automatisch angelegt "
                f"werden: {tabellen_fehler['ptt_manual']}",
                "warning",
            )
            try:
                ptt_manual_ddl = database.get_ddl_for_table("ptt_manual")
            except Exception:  # noqa: BLE001
                logger.exception("DDL für teCalc_PTT_manual konnte nicht ermittelt werden")
        try:
            ptt_rows = database.get_ptt_rows()
        except Exception as exc:  # noqa: BLE001
            logger.exception("PTT-Einträge konnten nicht geladen werden")
            db_error = str(exc)

    # process/subProcess als Kombinationsfelder (Auswahlliste statt Freitext),
    # Werte distinct aus MAR_TactTimes; bei Fehler Fallback auf Freitext-Inputs
    # (siehe ptt/index.html), damit die Seite trotzdem nutzbar bleibt.
    process_subprocess_pairs = []
    if _active_server_ok():
        try:
            process_subprocess_pairs = database.get_process_subprocess_pairs()
        except Exception as exc:  # noqa: BLE001
            logger.exception("process/subProcess-Auswahllisten (MAR_TactTimes) konnten nicht geladen werden")
            flash(
                f"process/subProcess-Auswahllisten konnten nicht geladen werden – "
                f"es wird Freitext-Eingabe verwendet: {exc}",
                "warning",
            )

    distinct_processes = sorted({r["process"] for r in process_subprocess_pairs})
    distinct_subprocesses = sorted({r["subProcess"] for r in process_subprocess_pairs})

    return render_template(
        "ptt/index.html", ptt_rows=ptt_rows, db_error=db_error,
        ptt_manual_ddl=ptt_manual_ddl,
        process_subprocess_pairs=process_subprocess_pairs,
        distinct_processes=distinct_processes,
        distinct_subprocesses=distinct_subprocesses,
    )


@ptt_bp.route("/bearbeiten")
def bearbeiten_popup():
    """PopUp zum Aendern eines bestehenden PTT-Eintrags (Doppelklick auf die
    Projektnummer in der PTT-Pflege-Liste, oder der Button "Aendern" davor).
    Das Formular im PopUp postet an die bestehende ptt.speichern-Route, die
    ueber database.upsert_ptt() bereits Update-then-Insert beherrscht - fuer
    einen bestehenden (projNr, process, subProcess)-Schluessel wird also
    einfach der PTT-Wert aktualisiert, kein neuer Code fuer den Schreibweg
    noetig.
    """
    proj_nr = request.args.get("projNr", "").strip()
    process = request.args.get("process", "").strip()
    sub_process = request.args.get("subProcess", "").strip()
    row = None
    error = None
    if proj_nr and process and sub_process:
        try:
            rows = database.get_ptt_rows(proj_nr)
            row = next(
                (r for r in rows if r["process"] == process and r["subProcess"] == sub_process),
                None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("PTT-Eintrag zum Bearbeiten konnte nicht geladen werden")
            error = str(exc)
    return render_template("ptt/_bearbeiten_popup.html", row=row, error=error)


@ptt_bp.route("/speichern", methods=["POST"])
def speichern():
    proj_nr = request.form.get("projNr", "").strip()
    process = request.form.get("process", "").strip()
    sub_process = request.form.get("subProcess", "").strip()
    ptt_raw = request.form.get("ptt", "").strip().replace(",", ".")
    if not (proj_nr and process and sub_process and ptt_raw):
        flash("Bitte projNr, process, subProcess und PTT ausfüllen.", "error")
        return redirect(url_for("ptt.index"))
    try:
        ptt = float(ptt_raw)
    except ValueError:
        flash("PTT muss eine Zahl sein.", "error")
        return redirect(url_for("ptt.index"))
    try:
        database.ensure_app_tables()
    except Exception:  # noqa: BLE001
        logger.exception("Konnte App-Tabellen beim Speichern der PTT nicht anlegen")
    try:
        database.upsert_ptt(proj_nr, process, sub_process, ptt, _current_user())
    except Exception as exc:  # noqa: BLE001
        logger.exception("PTT konnte nicht gespeichert werden")
        flash(f"PTT konnte nicht gespeichert werden: {exc}", "error")
        return redirect(url_for("ptt.index"))
    flash("PTT gespeichert.", "success")
    return redirect(url_for("ptt.index"))


@ptt_bp.route("/loeschen", methods=["POST"])
def loeschen():
    proj_nr = request.form.get("projNr", "")
    process = request.form.get("process", "")
    sub_process = request.form.get("subProcess", "")
    try:
        database.delete_ptt(proj_nr, process, sub_process)
    except Exception as exc:  # noqa: BLE001
        logger.exception("PTT-Eintrag konnte nicht gelöscht werden")
        flash(f"PTT-Eintrag konnte nicht gelöscht werden: {exc}", "error")
        return redirect(url_for("ptt.index"))
    flash("PTT-Eintrag gelöscht.", "success")
    return redirect(url_for("ptt.index"))


# =============================================================================
# ===== infor_bp – Liste der Uebernahmen ins Infor =====
# =============================================================================
# Zeigt teCalc_COR_INFORchanges (wird von bewerten.infor_uebernehmen() ueber
# dokumentation.record_infor_transfer()/database.save_infor_change_rows()
# befuellt) als eigene, dedizierte Liste - vorher nur indirekt sichtbar (z.B.
# als Grundlage der "veraltet"-Markierung in der Bewerten-Projekte-Liste).

@infor_bp.route("/")
def index():
    rows = []
    db_error = None
    infor_changes_ddl = None
    if _active_server_ok():
        try:
            tabellen_fehler = database.ensure_app_tables()
        except Exception:  # noqa: BLE001
            logger.exception("Konnte App-Tabellen beim Aufruf der INFOR-Übernahme-Liste nicht anlegen")
            tabellen_fehler = {}
        if "infor_changes" in tabellen_fehler:
            flash(
                f"Tabelle teCalc_COR_INFORchanges konnte nicht automatisch angelegt "
                f"werden: {tabellen_fehler['infor_changes']}",
                "warning",
            )
            try:
                infor_changes_ddl = database.get_ddl_for_table("infor_changes")
            except Exception:  # noqa: BLE001
                logger.exception("DDL für teCalc_COR_INFORchanges konnte nicht ermittelt werden")
        try:
            rows = dokumentation.get_infor_changes()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Liste der Infor-Übernahmen konnte nicht geladen werden")
            db_error = str(exc)
    return render_template(
        "infor/index.html", rows=rows, db_error=db_error, infor_changes_ddl=infor_changes_ddl,
    )


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
