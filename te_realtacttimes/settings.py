# =============================================================================
# te_realtacttimes/settings.py – Laufzeit-Einstellungen (settings.json)
# teRealTactTimes – technosert electronic GmbH
# =============================================================================
"""
Kapselt Lesen/Schreiben von settings.json. Laufzeit-Einstellungen sind Dinge,
die sich zur Laufzeit über die GUI ändern (aktiver DB-Server, Grenzwerte,
aktueller Bearbeiter, Webserver-Port) - im Gegensatz zu config.py, das feste
Konstanten enthält.
"""

import json
import os
import threading

import config

_lock = threading.Lock()

_DEFAULTS = {
    "active_server": config.DEFAULT_SERVER_KEY,
    "thresholds": dict(config.DEFAULT_THRESHOLDS),
    "current_user": "",
    "webserver": {
        "host": "127.0.0.1",
        "port": config.APP_PORT,
    },
}


def _read_raw():
    if not os.path.exists(config.SETTINGS_FILE):
        return {}
    try:
        with open(config.SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def load():
    """Lädt settings.json und ergänzt fehlende Schlüssel mit Defaults."""
    with _lock:
        data = _read_raw()
        changed = False
        for key, default_value in _DEFAULTS.items():
            if key not in data:
                data[key] = default_value
                changed = True
            elif isinstance(default_value, dict):
                for sub_key, sub_default in default_value.items():
                    if sub_key not in data[key]:
                        data[key][sub_key] = sub_default
                        changed = True
        if changed or not os.path.exists(config.SETTINGS_FILE):
            _write_raw(data)
        return data


def _write_raw(data):
    os.makedirs(os.path.dirname(config.SETTINGS_FILE), exist_ok=True)
    tmp_file = config.SETTINGS_FILE + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_file, config.SETTINGS_FILE)


def save(data):
    with _lock:
        _write_raw(data)


def get(key, default=None):
    return load().get(key, default)


def update(key, value):
    """Setzt einen einzelnen Top-Level-Schlüssel und speichert sofort."""
    with _lock:
        data = _read_raw()
        for default_key, default_value in _DEFAULTS.items():
            data.setdefault(default_key, default_value)
        data[key] = value
        _write_raw(data)
    return data


def get_active_server():
    return load().get("active_server", config.DEFAULT_SERVER_KEY)


def get_thresholds():
    return load().get("thresholds", dict(config.DEFAULT_THRESHOLDS))


def get_current_user():
    return load().get("current_user", "")
