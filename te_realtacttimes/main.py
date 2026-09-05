# =============================================================================
# te_realtacttimes/main.py – Hauptprogramm / Einstiegspunkt
# teRealTactTimes – technosert electronic GmbH
# =============================================================================
"""
create_app()-Factory: erstellt die Flask-App, registriert alle Blueprints,
setzt secret_key, Error-Handler für 404/500, context_processor für globale
Template-Variablen. Beim direkten Start (python main.py):
  - Auto-Connect zum zuletzt verwendeten/Standard-Server
  - Demo-Daten werden bei Bedarf geladen (nur Profil "demo")
  - Browser wird verzögert automatisch geöffnet
  - use_reloader=False, debug=False (kein Hot-Reload im Auslieferungsbetrieb;
    nach Codeänderungen muss der Prozess manuell neu gestartet werden)
"""

import logging
import logging.handlers
import os
import secrets
import threading
import webbrowser

from flask import Flask, render_template

import config
import settings


def _setup_logging():
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    file_handler = logging.handlers.RotatingFileHandler(
        config.LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console_handler)


def format_komma(value, decimals=None):
    """Formatiert eine Zahl im deutschen Format (Komma statt Punkt als
    Dezimaltrennzeichen) - passend zum Format der Quelldaten (CSV/DB: "0,7631").

    decimals=None: Python-Standarddarstellung (repr), nur der Dezimalpunkt
    wird durch ein Komma ersetzt - für die ungefilterten TactTimes/
    TactTimesCalc-PopUps (voller, unformatierter Inhalt der Quelltabelle).
    decimals=N: feste Nachkommastellen (ersetzt vorheriges "%.<N>f"|format(...))
    für die aufbereiteten Ansichten (TactTimeCheck, Projektdetails, PTT-Pflege).

    Nicht-Gleitkommawerte (Text, Datum, None, int) werden unverändert
    durchgereicht - dort ist kein Dezimaltrennzeichen vorhanden.
    """
    if isinstance(value, float):
        text = f"{value:.{decimals}f}" if decimals is not None else repr(value)
        return text.replace(".", ",")
    return value


def format_statuscolor(status):
    """CSS-Klasse fuer die Schriftfarbe der Spalten Abw./Abw.% je nach Status:
    OK = gruen, Warngrenze = orange, Aktionsgrenze = rot, alles andere = schwarz."""
    mapping = {
        config.STATUS_OK: "status-ok",
        config.STATUS_WARN: "status-warn",
        config.STATUS_ACTION: "status-action",
    }
    return mapping.get(status, "")


def create_app():
    app = Flask(
        __name__,
        template_folder=config.TEMPLATE_DIR,
        static_folder=config.STATIC_DIR,
    )
    app.secret_key = secrets.token_hex(16)
    app.config["UPLOAD_FOLDER"] = config.UPLOAD_FOLDER
    app.jinja_env.filters["komma"] = format_komma
    app.jinja_env.filters["statuscolor"] = format_statuscolor

    from gui.routes import main_bp, bewerten_bp, konfiguration_bp, ptt_bp, infor_bp, api_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(bewerten_bp)
    app.register_blueprint(konfiguration_bp)
    app.register_blueprint(ptt_bp)
    app.register_blueprint(infor_bp)
    app.register_blueprint(api_bp)

    @app.context_processor
    def inject_globals():
        logo_filename = "Logo_technosert_white-270x0-c-default.png"
        logo_path = os.path.join(config.STATIC_DIR, "images", logo_filename)
        return {
            "app_name": config.APP_NAME,
            "app_full_name": config.APP_FULL_NAME,
            "app_description": config.APP_DESCRIPTION,
            "app_version": config.APP_VERSION,
            "firma": config.FIRMA,
            "firma_url": config.FIRMA_URL,
            "servers": config.DB_SERVERS,
            "active_server": settings.get_active_server(),
            "logo_exists": os.path.exists(logo_path),
            "logo_filename": logo_filename,
        }

    @app.errorhandler(404)
    def not_found(_err):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(_err):
        logging.getLogger(__name__).exception("Interner Fehler")
        return render_template("500.html"), 500

    return app


def _auto_connect():
    """Verbindet beim Start zum konfigurierten Server; legt App-Tabellen an."""
    from db import database

    logger = logging.getLogger(__name__)
    server_key = settings.get_active_server()
    profile = config.DB_SERVERS.get(server_key)

    if profile and profile["driver"] == "sqlite":
        try:
            from db import seed_demo
            seed_demo.seed_demo_database(force=False)
        except Exception:
            logger.exception("Demo-Daten konnten nicht geladen werden")

    ok, message = database.test_connection(server_key)
    if ok:
        logger.info(message)
        try:
            database.ensure_app_tables(server_key)
        except Exception:
            logger.exception("App-Tabellen konnten nicht angelegt werden")
    else:
        logger.warning(message)


def _open_browser(url):
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001
        pass


def main():
    _setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starte %s v%s ...", config.APP_NAME, config.APP_VERSION)

    _auto_connect()

    app = create_app()
    webserver = settings.get("webserver") or {"host": "127.0.0.1", "port": config.APP_PORT}
    host, port = webserver["host"], webserver["port"]

    if os.environ.get("TE_NO_BROWSER") != "1":
        url = f"http://{host if host != '0.0.0.0' else '127.0.0.1'}:{port}/"
        threading.Timer(1.0, _open_browser, args=[url]).start()

    app.run(host=host, port=port, use_reloader=False, debug=False)


if __name__ == "__main__":
    main()
###################################
## EOF
###################################