# teRealTactTimes

Webserver-Anwendung (Flask) zum Erfassen, Einlesen und Vergleichen von
Maschinen-Taktzeiten (MTT, Ist) mit Plan-Taktzeiten (PTT, Soll) in der
Elektronikfertigung, inkl. Dokumentation und Vorbereitung der Übernahme
nach Infor. Umgesetzt nach dem Prompt in `doku/ekey_Prompt_teCalcRealValues.docx`
sowie dem Design-System aus `doku/Claude_Code_Design_Prompt.md`.

## Schnellstart (Demo-Modus, ohne SQL-Server)

```bash
cd te_realtacttimes
pip install -r requirements.txt
python main.py
```

Der Browser öffnet automatisch `http://127.0.0.1:5000/`. Beim ersten Start
werden die mitgelieferten Beispieldaten (`data/MAR_TactTimes.csv`,
`data/MAR_TactTimesCalc.csv`, 349 Projekte) automatisch in eine lokale
SQLite-Datei geladen (Server-Profil **"Demo/Test"**). Unter Windows kann
alternativ `start.bat` per Doppelklick verwendet werden (legt automatisch
eine virtuelle Umgebung an).

## Anbindung an einen echten SQL-Server

Unter **Konfiguration → SQL-Server konfigurieren** stehen zwei produktive
Profile bereit (`config.py` → `DB_SERVERS`):

- **technosert** – Server `SRVDB`, Datenbank `DataWarehouse`
- **MBe-Consulting** – Server `localhost`, Datenbank `te_realTactTimes`

Beide nutzen `pyodbc` mit `ODBC Driver 17 for SQL Server` und Windows-
Authentifizierung (Trusted Connection). Für den Betrieb muss der ODBC-
Treiber auf dem Zielrechner installiert sein; `pyodbc` selbst ist bereits
in `requirements.txt` enthalten. Die App legt die benötigten Tabellen
(`teCalc_COR_tactTimesCheck`, `teCalc_COR_INFORchanges`,
`teCalc_PTT_manual`) beim Verbinden automatisch an, falls sie noch nicht
existieren.

## Projektstruktur

```
te_realTactTimes/
├── data/                     # Beispieldaten (CSV) für den Demo-Modus
├── doku/                     # Ursprüngliche Anforderungs-Prompts
├── img/                      # Logo & Titelbild
└── te_realtacttimes/         # Python-Package der Anwendung
    ├── main.py                # Einstiegspunkt (create_app, Auto-Connect, Browser-Start)
    ├── config.py               # Zentrale Konstanten (DB-Server, Tabellennamen, Grenzwerte)
    ├── settings.py / settings.json   # Laufzeit-Einstellungen (aktiver Server, Grenzwerte, Bearbeiter)
    ├── bewertung.py             # Vergleichslogik MTT vs. PTT (TTCheck), reine Python-Logik
    ├── dokumentation.py         # Speichern der Bewertungs-/Infor-Snapshots
    ├── infor.py                 # Vorbereiteter Stub für die spätere Infor-Anbindung
    ├── db/
    │   ├── database.py          # Einzige Datei mit SQL-Zugriffen (pyodbc + sqlite)
    │   └── seed_demo.py         # Lädt data/*.csv in die Demo-SQLite-DB
    └── gui/
        ├── routes.py            # Flask-Blueprints (main, bewerten, konfiguration, api)
        ├── static/css/app.css   # Corporate-Design (technosert-Farben, Enterprise-Layout)
        ├── static/images/       # Logo & Titelbild (Kopie aus img/)
        └── templates/           # base.html + Fachseiten
```

## Wichtige Annahmen & Abweichungen vom Prompt-Text

Der gelieferte Prompt enthielt einige Widersprüche bzw. offene Punkte, die
für eine lauffähige Anwendung entschieden werden mussten. Diese Entscheidungen
bitte gegenprüfen:

1. **Branding**: Der Prompt-Text nennt teils "ekeyProductionPlanning",
   `ekey_logo.jpg` und `www.ekey.net` – das sind erkennbar Restspuren aus
   einer anderen Projektvorlage. Umgesetzt wurde stattdessen **technosert**-
   Branding (Name "teRealTactTimes", mitgeliefertes technosert-Logo,
   Footer-Link technosert.com), passend zu Ordnername, Logo-Datei und
   Doku-Deckblatt. Auf Wunsch jederzeit in `config.py`
   (`APP_NAME`, `FIRMA`, `FIRMA_URL`) und `gui/templates/base.html` anpassbar.
2. **Startseiten-/Sidebar-Buttons**: Die im Prompt genannten Buttons
   "[Aufträge][Planung][Snapshot]" bzw. "[Daten erfassen][Daten einlesen]
   [Daten aufbereiten]" passen zu keiner der beschriebenen Funktionen und
   wurden durch die tatsächlich in der GUI-Seitenstruktur definierten
   Bereiche ersetzt: **Bewerten, Konfiguration, KPIs** (KPIs bewusst als
   Platzhalter, siehe Prompt "kommt später").
3. **PTT-Quelle (Soll-Zeiten) ist laut Prompt "TBD"**: Damit TTCheck
   trotzdem benutzbar/testbar ist, wurde eine Übergangstabelle
   `teCalc_PTT_manual` (projNr/process/subProcess → PTT) plus Pflegemaske
   unter **Konfiguration → PTT-Pflege** ergänzt. Die eigentliche Anbindung
   an den Leitstand ist als einzige Stelle `db.database.get_ptt_map()`
   austauschbar, sobald die reale Quelle feststeht – der Rest der
   Anwendung muss dafür nicht geändert werden.
4. **Aggregation MTT/PTT**: `MAR_TactTimesCalc` liegt auf Ebene
   projNr/process/**subProcess** vor (ein `process` kann mehrere
   `subProcess` haben, z.B. `4_AOI` → SIDEA/SIDEB/SMT). Die TTCheck-Liste
   (Abschnitt 5.3.3.1) aggregiert je `process` durch Summation der
   `board_tactTime_brutto`-Werte seiner Subprozesse; die Projektdetails
   (5.3.3.2) zeigen zusätzlich jede Subprozess-Zeile einzeln mit eigener
   Abweichung. Fehlt für auch nur einen Subprozess eines Prozesses ein
   PTT-Wert, wird der ganze Prozess als "PTT fehlt" markiert (keine
   irreführenden Teil-Summen).
5. **"Nach Infor übertragen"**: Checkbox/Korrekturfeld werden je **Prozess**
   eingeblendet (nicht je Subprozess), passend zur Tabellenstruktur von
   `teCalc_COR_INFORchanges` (dort gibt es nur eine `process`-, keine
   `subProcess`-Spalte).
6. **Infor-Anbindung**: Der Workflow endet bewusst mit dem Speichern in
   `teCalc_COR_INFORchanges` (`dokumentation.py`). Die tatsächliche
   Übertragung nach Infor ist in `infor.py` als Stub vorbereitet
   (`push_changes()`), aber laut Prompt noch nicht spezifiziert.
7. **"Aktueller Bearbeiter"**: Da Access/Security laut Prompt "TBD" ist,
   gibt es noch kein Login. Ersatzweise kann unter Konfiguration ein
   Bearbeiter-Name hinterlegt werden, der als "Name" in den
   Dokumentationstabellen gespeichert wird.
8. **Demo/Test-Server-Profil**: Zusätzlich zu den zwei in Prompt genannten
   MSSQL-Servern (te/MBe) wurde ein drittes Profil **"Demo/Test"** (SQLite,
   Beispieldaten) ergänzt, damit die Anwendung ohne Zugriff auf einen
   echten SQL-Server sofort lauffähig ist. Es ist klar als Test-Profil
   gekennzeichnet und kann in `config.py` (`DB_SERVERS`) bei Bedarf entfernt
   werden.

## Offene Punkte laut Prompt (bewusst nicht implementiert)

- **PTT-Quelle aus dem Leitstand** (Abschnitt 5.3.2) – siehe Punkt 3 oben.
- **Infor-Schnittstelle** (`infor.py`) – Format/API noch nicht spezifiziert.
- **KPIs/Dashboards** – laut Prompt "kommt später", Menüpunkt vorhanden,
  aber deaktiviert/Platzhalter.
- **Nutzerrechte/Login** – laut Prompt "kommt später", Menüpunkt vorhanden,
  aber deaktiviert/Platzhalter.
- **Abschnitt 5.3.5 "Ändern"** – im Prompt nur mit `<TBD>` markiert, keine
  weiteren Angaben vorhanden.

## Getestet

Die Anwendung wurde im Demo-Modus vollständig durchgetestet (Startseite,
Server-Umschaltung inkl. Fehlerfall ohne echten SQL-Server, TTCheck über
alle 349 Beispielprojekte, Sortieren/Filtern inkl. Lot-Suche,
Projektdetails mit Prozess-/Subprozess-Aggregation, Processdetails-PopUp,
Nach-Infor-Übertragen inkl. Dokumentation, Grenzwert-Validierung,
PTT-Pflege). Screenshots der wichtigsten Seiten liegen dieser Auslieferung
bei.
