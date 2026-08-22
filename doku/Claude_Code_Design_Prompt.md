# Claude Code Prompt – Design- & Architektur-System "te ProductionPlanning"

> **Zweck dieses Dokuments:** Wiederverwendbarer Prompt für Claude Code. Wird
> dieser Prompt an den Anfang eines NEUEN Projekts gestellt (z.B. als
> `CLAUDE.md` oder als erster Auftrag), soll die neue Anwendung im selben
> Look & Feel, derselben Struktur und Arbeitsweise entstehen wie
> `te_productionPlanning`. Er ist bewusst **fachlich neutral** gehalten
> (keine Produktionsplanungs-Begriffe), damit er 1:1 für andere interne
> Enterprise-Tools wiederverwendet werden kann. Ersetzt `<APP_NAME>`,
> `<FIRMA>`, `<DOMÄNE>` etc. durch die Werte des neuen Projekts.
>
> Basis: Analyse von `ekey.css`, `base.html`, `config.py`, `db/database.py`,
> `gui/routes.py`, `main.py` sowie des ursprünglichen Design-Prompts
> (`Doku/ekey_Prompt_teProductionPlanning.docx`) der Anwendung
> `te_productionPlanning`.

---

## 1. KI-Rolle

```
# Du bist ein erfahrener Software-Entwickler.
# Programmiersprache: Python (Flask)
# HMI-Design im Web-Browser mit tabellarischen und grafischen UI-Elementen
# Datenbankspezialist (SQL Server / pyodbc)
# Du baust interne Enterprise-/Fachanwendungen für Sachbearbeiter und
  technische Anwender – KEINE Consumer-/Marketing-Software.
```

## 2. Aufgabe

Baue eine **lokale Webserver-Anwendung** (Flask, im Browser über
`http://localhost:<PORT>` bedient) für `<DOMÄNE>` bei `<FIRMA>`. Zielgruppe
sind technische Fachanwender, keine Endkunden. Die Software soll aussehen,
sich bedienen und strukturiert sein wie ein klassisches MES-/ERP-/
Planungssystem – **nicht** wie eine moderne Consumer-Web-App.

---

## 3. Design-Philosophie

Die Software soll:

- funktional statt verspielt wirken
- klar strukturiert und kompakt sein (hohe Informationsdichte)
- professionell und industriell aussehen
- für produktive, repetitive Arbeitsabläufe optimiert sein
- eine konsistente Corporate Identity besitzen
- daten- und workfloworientiert aufgebaut sein
- modern, aber zurückhaltend wirken ("boring by design")
- primär für technische Anwender entwickelt werden, die viele Stunden täglich
  damit arbeiten (Tastatur-/Formular-Effizienz vor visueller Verspieltheit)

**UX-Stil-Vorbilder:** MES-Systeme, Produktionsplanungssysteme, ERP-Systeme,
industrielle Dashboards, BI-Plattformen, Qualitätsmanagementsysteme.

**Unbedingt vermeiden:**

- Glassmorphism, Neon-Designs, Social-Media-Optik, Gaming-Design
- übertriebene Animationen/Transitions, große Schatten, stark abgerundete Ecken
- große Weißraum-/Padding-Werte ("Landingpage-Look")
- Icon-Bibliotheken/Web-Fonts – stattdessen Unicode-Symbole (`&#128203;` etc.)
  oder gar keine Icons, um Abhängigkeiten zu vermeiden

---

## 4. Corporate Design / Farbsystem

Alle Farben ausschließlich über CSS-Variablen in `:root`, nie hartkodiert im
Markup. `<PRIMARY>`/`<PRIMARY_DARK>` durch die Farben von `<FIRMA>` ersetzen,
Struktur/Namensschema beibehalten:

```css
:root {
    --app-primary:         #46067A;  /* Corporate-Farbe <FIRMA> */
    --app-primary-dark:    #2E0451;
    --app-text:            #333333;
    --app-muted:           #666666;
    --app-border:          #BBBBBB;
    --app-btn-bg:          #F7F0F0;
    --app-btn-bg-active:   #46067A;
    --app-btn-text:        #46067A;
    --app-btn-text-active: #FFFFFF;
    --app-header-bg:       #FFFFFF;
    --app-footer-bg:       #F7F0F0;
    --app-sidebar-bg:      #FAF6FB;
    --app-table-header:    #F4ECF7;
    --app-table-row-alt:   #FBF7FC;
    --app-error:           #B00020;
    --app-error-bg:        #FFE9EC;
    --app-success:         #1A7A3A;
    --app-success-bg:      #E8F5EC;
    --app-warning:         #8B5800;
    --app-warning-bg:      #FFF8E1;
    --app-info:            #005B99;
    --app-info-bg:         #E1F0FA;
}
```

**Stilregeln:**

- weiße Hauptflächen, sehr helle Akzentfarben (Sidebar/Tabellenheader in
  ~5–8% Primärfarbe)
- dezente graue Rahmen (`1px solid var(--app-border)`) statt Schatten zur
  Flächentrennung
- minimale Schatteneffekte (nur bei Flash-Messages/Modals, max.
  `2px 2px 6px rgba(0,0,0,0.12)`)
- klare Hover-Zustände: Hintergrund → Primärfarbe, Text → Weiß
- hohe Lesbarkeit/Kontraste, kompakte Enterprise-Optik

---

## 5. Typografie

```css
body { font-family: Verdana, Geneva, sans-serif; font-size: 10px; }
```

- Schriftfamilie: **Verdana, Geneva, sans-serif** (bewusst keine moderne
  Web-Font – neutral, auf jedem Windows-Client ohne Nachladen verfügbar)
- Basistext: **10px** (bewusst klein/kompakt – viele Daten pro Bildschirm)
- Formulare/Inputs: 10px, Labels 9px (bold, uppercase, `letter-spacing`)
- Tabellenheader: 10–11px bold
- Seitentitel (`.page-title`): 14px bold, Primärfarbe
- Modal-/Section-Header: 11–12px bold
- Kleingedrucktes (`.text-sm`): 9px

---

## 6. Layout

**Klassisches Enterprise-Layout** über CSS Grid, exakt 4 Bereiche, feste
Viewport-Höhe (Seite selbst scrollt nie, nur `main` und `sidebar` scrollen
unabhängig):

```css
.app-wrapper {
    display: grid;
    grid-template-rows: 60px 1fr 32px;
    grid-template-columns: auto 1fr;
    grid-template-areas:
        "header  header"
        "sidebar main"
        "footer  footer";
    height: 100vh;
    overflow: hidden;
    /* Optional: 16:9-Begrenzung + Zentrierung auf Ultra-Wide-Monitoren */
    max-width: calc(100vh * 16 / 9);
    margin: 0 auto;
    background: #FFFFFF;
}
```

- **Header** (`grid-area: header`, 60px, `position: sticky; top:0;`):
  links Logo, Mitte Anwendungstitel (+ Subzeile mit Firma/Zweck, 10px,
  halbtransparent), rechts Statusanzeige (z.B. DB-Verbindung, farbiger Dot)
  + "Beenden"-Button. Hintergrund Primärfarbe, Text weiß.
- **Sidebar** (`grid-area: sidebar`, 200px, einklappbar auf 36px via
  `.collapsed` + JS-Toggle, Zustand in `localStorage`): Navigation in
  thematischen Abschnitten (`.sidebar-section` mit
  `.sidebar-section-title` uppercase 9px), aktiver Link über
  `request.endpoint`-Vergleich in Jinja markiert (`.active`,
  3px linker Primärfarben-Border).
- **Main** (`grid-area: main`, `overflow-y:auto`, 16px Padding):
  Arbeitsbereich. Jede Seite beginnt mit `.page-header`
  (Titel + Subtitel + Aktionen) und gliedert Inhalte in
  `.content-section`-Boxen (weißer Kasten, grauer Rahmen, violetter
  Header-Balken, Body mit 12px Padding).
- **Footer** (`grid-area: footer`, 32px, zentriert, 9px):
  Firmenlink + App-Name/Version.

---

## 7. Komponenten

### Buttons

```css
.btn {
    display: inline-flex; align-items: center; justify-content: center; gap: 4px;
    min-height: 28px; min-width: 100px; padding: 4px 12px;
    font-size: 10px; font-weight: bold;
    border: 1px solid var(--app-border);
    background: var(--app-btn-bg); color: var(--app-btn-text);
    cursor: pointer; white-space: nowrap; transition: background 0.15s, color 0.15s;
}
.btn:hover { background: var(--app-primary); color: #FFFFFF; border-color: var(--app-primary); }
.btn-primary { background: var(--app-primary); color: white; border-color: var(--app-primary-dark); }
.btn-danger  { background: var(--app-error-bg); color: var(--app-error); border-color: var(--app-error); }
.btn-sm      { min-height: 22px; min-width: 60px; padding: 2px 8px; font-size: 9px; }
```

Rechteckig, klare Rahmen, kompakte Höhe, minimaler Hover-Effekt, aktive
Zustände immer in Primärfarbe. Varianten: `.btn-primary`, `.btn-danger`,
`.btn-sm`, `.btn-icon`, gruppiert in `.btn-group` (flex, gap 4px, wrap).

### Formulare

- Labels **oberhalb** der Felder, 9px bold uppercase, `color: var(--app-muted)`
- Inputs/Selects/Textareas: 10px, weißer Hintergrund, grauer Rahmen, 28px
  Höhe, Fokus = Primärfarben-Rahmen + dezenter `box-shadow`
  (`0 0 0 2px rgba(primary, 0.1)`)
- Layout über `.form-grid` (`repeat(auto-fill, minmax(200px,1fr))`) oder
  `.form-row` (flex, `align-items:flex-end`) für Inline-Formulare
- `.form-actions` (Buttons) durch Trennlinie vom Rest abgesetzt

### Tabellen

Zentrales Bauelement der Software – kompakt, hoch lesbar, datenorientiert:

```css
table.data-table thead tr { background: var(--app-table-header); }
table.data-table thead th {
    font-weight: bold; color: var(--app-primary);
    border-bottom: 2px solid var(--app-primary); padding: 6px 8px;
}
table.data-table tbody tr:nth-child(even) { background: var(--app-table-row-alt); }
table.data-table tbody tr:hover { background: var(--app-table-header); }
```

Wechselnde Zeilenfarben, violette (Primärfarben-)Header mit dicker
Unterstreichung, Aktionsbuttons direkt in der letzten Spalte, in
`.table-wrapper` (`overflow-x:auto`) für Responsivität.

### Flash-Messages (Toast-Benachrichtigungen)

Fixiert oben rechts (`position:fixed; top:68px; right:12px`), 4 Kategorien
`success/error/warning/info` (Hintergrund + Randfarbe je Kategorie aus den
CSS-Variablen), Einblend-Animation (`slideIn`, 0.2s), automatisches
Ausblenden nach 6s per JS, manuelles Schließen per `×`-Button.

### Modals

Zentriert, `position:fixed; inset:0` mit halbtransparentem Backdrop
(`rgba(0,0,0,0.4)`), `.modal-box` mit `.modal-header` (Primärfarben-Titel
auf `--app-table-header`-Hintergrund), `.modal-body`, `.modal-footer`
(Buttons rechtsbündig). Varianten für breitere Inhalte
(`.modal-box-lg`, feste Seitenverhältnis-Varianten für Tabellen/Historie).

### Badges

`.badge` + `.badge-primary/-success/-error/-warning/-muted`: kleine,
umrandete Status-Pillen (9px bold), z.B. für Verbindungsstatus, Kollisionen,
Freigaben.

### Fachspezifische Visualisierungen (z.B. Gantt/Zeitachsen)

Bei Zeitachsen-/Prozessvisualisierung: eigene `.gantt-*`-Klassen, KEINE
externe Chart-Bibliothek, sondern reines HTML/CSS + Server-Daten (Zeilen aus
Label-Spalte `.gantt-label` + absolut positionierten Balken
`.gantt-bar` in `.gantt-bar-area`). Hält die App abhängigkeitsfrei und
leicht anpassbar.

### Utilities

Kleine Helper-Klassen statt Utility-Framework: `.text-primary/-muted/-error
/-success`, `.text-right/-center/-bold/-sm`, `.mt-1..3/.mb-1..3`,
`.flex/.flex-gap/.align-center/.flex-wrap`, `.w-full`, `.hidden`.

---

## 8. Technische Architektur

### Projektstruktur (1:1 übernehmen, Namen anpassen)

```
<app_name>/
├── Doku/                          # Anforderungs-/Design-Prompts (.docx/.md)
├── data/                          # Externe Quelldaten (Excel/CSV-Importe), _Archiv/ Unterordner
├── image/                         # Firmenlogos, Titelbilder (außerhalb der App, für Doku)
├── <app_package>/                 # Python-Package der eigentlichen Anwendung
│   ├── main.py                    # Einstiegspunkt: create_app(), Server-Start
│   ├── config.py                  # ZENTRALE Konstanten (siehe unten)
│   ├── settings.json              # Laufzeit-Settings (z.B. Standard-Server), NICHT in config.py
│   ├── requirements.txt
│   ├── start.bat                  # Doppelklick-Start für Windows-Anwender
│   ├── app.log                    # Rotierendes Logfile (siehe Logging unten)
│   ├── db/
│   │   ├── __init__.py
│   │   └── database.py            # EINZIGE Datei mit SQL-Zugriffen
│   ├── <domänen_modul>/           # z.B. planning/, snapshot/ – reine Logik, kein Flask
│   │   ├── __init__.py
│   │   └── *.py
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── routes.py              # ALLE Blueprints in einer Datei, siehe unten
│   │   ├── static/
│   │   │   ├── css/app.css        # EINE zentrale CSS-Datei (kein Framework)
│   │   │   ├── js/                # nur bei Bedarf, sonst <script> inline in Templates
│   │   │   └── images/
│   │   └── templates/
│   │       ├── base.html          # Layout-Grundgerüst (siehe Abschnitt 9)
│   │       ├── 404.html / 500.html
│   │       └── <bereich>/*.html   # 1 Unterordner pro Sidebar-Bereich
│   └── uploads/                   # Datei-Uploads zur Laufzeit
```

### `config.py` – zentrale Konfiguration

Eine Datei für **alle** Konstanten: DB-Server-Definitionen (mehrere
benannte Umgebungen, z.B. Produktiv-/Entwicklungsserver, umschaltbar über
GUI), Tabellennamen, Domänen-Konfiguration (z.B. feste Prozess-/
Ablauf-Definitionen als `dict`/`list`, NICHT verstreut im Code), Pfade
(`BASE_DIR`, `TEMPLATE_DIR`, `UPLOAD_FOLDER` via `os.path.join`),
`APP_NAME`/`APP_VERSION`/`APP_PORT`. Andere Module importieren ausschließlich
aus `config`, nie eigene Konstanten duplizieren.

### `db/database.py` – Datenbankzugriff

- **Ein** globaler Verbindungsstatus (`_active_server`), umschaltbar zur
  Laufzeit über die GUI (mehrere Server zur Auswahl, z.B. Produktiv/Test)
- `@contextmanager db_connection()` kapselt Connect/Commit/Close
- Alle SQL-Statements ausschließlich hier – kein SQL in `routes.py`
- Jede Funktion macht **eine** klar benannte Sache
  (`get_x`, `save_x`, `delete_x`, `update_x_times`), Rückgabe als
  `List[dict]`/`dict` (nie rohe Cursor-Objekte nach außen geben)
- Laufzeit-Einstellungen (Standard-Server o.ä.) in `settings.json` neben
  `config.py`, nicht in der Datenbank und nicht hartkodiert

### `gui/routes.py` – Flask-Routen

- **Mehrere Blueprints in einer Datei**, gruppiert per Kommentar-Banner
  (siehe Abschnitt 10), url-prefixed nach Fachbereich:
  ```python
  main_bp = Blueprint("main", __name__)
  <bereich>_bp = Blueprint("<bereich>", __name__, url_prefix="/<bereich>")
  api_bp = Blueprint("api", __name__, url_prefix="/api")
  ```
- Route-Funktionen bleiben dünn: Formular/Query lesen → `db.*`/Domänen-Modul
  aufrufen → `render_template`/`redirect` + `flash()`. Geschäftslogik lebt
  in `db/` bzw. dem Domänen-Modul, nicht in der Route.
- Statusrückmeldungen **immer** über `flash(message, category)` mit
  `category` ∈ `success/error/warning/info` (siehe Flash-CSS)
- Bei mehrstufigen Server-Operationen (Simulation/Neuplanung o.ä.): eigene
  Hilfsfunktionen mit `_`-Präfix im selben File, ausführlich dokumentiert

### `main.py` – Einstiegspunkt

- `create_app()`-Factory: erstellt Flask-App, registriert alle Blueprints,
  setzt `secret_key`, Error-Handler für 404/500, `context_processor` für
  globale Template-Variablen (App-Name, Version, aktiver Server, Logo-Check)
- Auto-Connect zum zuletzt verwendeten/Standard-Server beim Start
- Browser wird verzögert automatisch geöffnet (`threading.Timer` + `webbrowser.open`)
- **`use_reloader=False`, `debug=False`** im Auslieferungsbetrieb – kein
  Hot-Reload. Wichtig für Tests: Nach Codeänderungen muss der Prozess
  manuell neu gestartet werden (`/shutdown`-Route + `start.bat`).
- Logging zentral über `logging.basicConfig` in `main.py`: Konsole +
  `app.log`-Datei, Format `%(asctime)s [%(levelname)s] %(name)s: %(message)s`

### `<domänen_modul>/` – Fachlogik

Reine Python-Logik ohne Flask-Abhängigkeit (testbar, wiederverwendbar),
z.B. Simulation/Berechnung. Nimmt einfache Datenstrukturen (Listen von
Dicts) entgegen, gibt ebensolche zurück – keine DB-Zugriffe hier (die
liefert `routes.py` vorher aus `db.*`).

---

## 9. `base.html` – Layout-Grundgerüst (Vorlage, generalisiert)

```html
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}{{ app_name }}{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/app.css') }}">
    {% block extra_head %}{% endblock %}
</head>
<body class="{% block body_class %}{% endblock %}">
<div class="app-wrapper">
    <header class="app-header">
        <div class="header-logo">
            {% if logo_exists %}
                <img src="{{ url_for('static', filename='images/logo.png') }}" alt="<FIRMA> Logo">
            {% else %}
                <span class="logo-placeholder"><KÜRZEL></span>
            {% endif %}
        </div>
        <div class="header-title">
            <APP_NAME>
            <span><FIRMA> – <DOMÄNE_BESCHREIBUNG></span>
        </div>
        <div class="header-actions">
            <div class="server-indicator">
                <span class="dot {% if active_server %}connected{% else %}disconnected{% endif %}"></span>
                {{ servers[active_server].label if active_server else "Kein Server" }}
            </div>
            <form method="POST" action="{{ url_for('main.shutdown') }}"
                  onsubmit="return confirm('Anwendung wirklich beenden?')">
                <button type="submit" class="btn btn-sm">&#10005; Software beenden</button>
            </form>
        </div>
    </header>

    <nav class="app-sidebar" id="appSidebar">
        <div class="sidebar-toggle" onclick="toggleSidebar()">
            <span id="sidebarToggleIcon">&#9664;</span>
        </div>
        <div class="sidebar-section">
            <div class="sidebar-section-title sidebar-text">Navigation</div>
            <div class="sidebar-nav">
                <a href="{{ url_for('main.index') }}"
                   class="{% if request.endpoint == 'main.index' %}active{% endif %} sidebar-text">
                    &#127968; Startseite
                </a>
            </div>
        </div>
        <!-- Weitere .sidebar-section Blöcke: 1 pro Fachbereich, siehe Abschnitt 8 -->
    </nav>

    <main class="app-main">
        {% block content %}{% endblock %}
    </main>

    <footer class="app-footer">
        <a href="https://www.<firma>.<tld>" target="_blank">www.<firma>.<tld></a>
        &nbsp;|&nbsp; {{ app_name }} v{{ app_version }}
    </footer>
</div>

<div class="flash-container" id="flashContainer">
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% for category, message in messages %}
        <div class="flash-msg {{ category }}">
            <span>{{ message }}</span>
            <button class="flash-close" onclick="this.parentElement.remove()">&#10005;</button>
        </div>
        {% endfor %}
    {% endwith %}
</div>

<script>
function toggleSidebar() {
    const sb = document.getElementById('appSidebar');
    const icon = document.getElementById('sidebarToggleIcon');
    sb.classList.toggle('collapsed');
    icon.textContent = sb.classList.contains('collapsed') ? '▶' : '◀';
    document.querySelectorAll('.sidebar-text').forEach(el => {
        el.style.display = sb.classList.contains('collapsed') ? 'none' : '';
    });
    localStorage.setItem('sidebarCollapsed', sb.classList.contains('collapsed'));
}
setTimeout(() => document.querySelectorAll('.flash-msg').forEach(el => el.remove()), 6000);
window.addEventListener('DOMContentLoaded', () => {
    if (localStorage.getItem('sidebarCollapsed') === 'true') {
        document.getElementById('appSidebar').classList.add('collapsed');
        document.getElementById('sidebarToggleIcon').textContent = '▶';
        document.querySelectorAll('.sidebar-text').forEach(el => el.style.display = 'none');
    }
});
</script>
{% block extra_scripts %}{% endblock %}
</body>
</html>
```

Jede Fachseite erbt davon:

```jinja
{% extends "base.html" %}
{% block title %}<Seitentitel> – {{ app_name }}{% endblock %}
{% block content %}
<div class="page-header">
    <div>
        <div class="page-title"><Seitentitel></div>
        <div class="page-subtitle"><Kurzbeschreibung></div>
    </div>
</div>
<div class="content-section">
    <div class="content-section-header">Abschnittstitel</div>
    <div class="content-section-body">...</div>
</div>
{% endblock %}
```

---

## 10. Code-Konventionen

- **Kommentarsprache: Deutsch**, Code (Variablen/Funktionen): Englisch/
  fachlich neutral gemischt, wie im Original (`get_taktzeiten_for_auftrag`
  etc.) – konsistent zur Domänensprache des Fachbereichs
- Jede Datei beginnt mit Banner-Kommentar:
  ```python
  # =============================================================================
  # <pfad>/<datei>.py – <Kurzbeschreibung>
  # <APP_NAME> – <FIRMA>
  # =============================================================================
  ```
- Innerhalb von `routes.py` gliedern `# ===== BEREICH =====`-Banner die
  Blueprints thematisch
- **Docstrings erklären das WARUM, nicht nur das WAS** – insbesondere bei
  Bugfixes: kurze Begründung + Datum, z.B.
  `"""Bugfix 12.08.2026: ... - Grund: ..."""`. Das macht spätere Änderungen
  durch Claude Code nachvollziehbar, ohne Git-Historie durchsuchen zu müssen.
- Geschäftsregeln (z.B. feste Ablaufreihenfolgen) **immer zentral in
  `config.py`** als Datenstruktur, nie als verstreute `if`-Ketten
- Serverseitige Validierung vor jeder schreibenden Aktion, Fehler über
  `flash(..., "error")` + `logger.exception(...)`, nie stille Fehler
- Bei komplexen Neuberechnungen: Sicherheits-Check NACH der Berechnung
  (z.B. Kollisionsprüfung), der die Änderung verwirft und einen Fehler
  meldet, statt inkonsistente Daten zu speichern

---

## 11. Checkliste: neues Projekt im selben Look & Feel starten

1. Ordnerstruktur aus Abschnitt 8 anlegen, `<app_package>` benennen
2. `app.css` mit dem Farbsystem aus Abschnitt 4 erstellen (Variablenprefix
   ggf. umbenennen, Werte nur ändern wenn explizit eine andere Corporate
   Identity gefordert ist)
3. `base.html` aus Abschnitt 9 übernehmen, Platzhalter ersetzen
4. `config.py` mit `APP_NAME`, `APP_PORT`, `DB_SERVERS`, Domänen-Konstanten
   anlegen
5. `db/database.py` mit `db_connection()`-Contextmanager + Server-Umschaltung
   aufbauen
6. `main.py` mit `create_app()`-Factory, Auto-Connect, Browser-Autostart,
   `use_reloader=False` anlegen
7. Pro Fachbereich: 1 Blueprint in `routes.py`, 1 Unterordner in
   `templates/`, 1 Sidebar-Section in `base.html`
8. Tabellen/Formulare/Modals ausschließlich mit den Klassen aus Abschnitt 7
   bauen – keine neuen visuellen Muster ohne Rücksprache einführen
9. Bei jeder Server-Codeänderung: App **neu starten** (kein Auto-Reload) und
   `app.log` als erste Diagnosequelle nutzen, bevor DB-Zugriff nötig wird
