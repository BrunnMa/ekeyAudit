# ekeyAudit

Lauffaehige Flask-Webanwendung fuer QM-Audits nach ISO 9001.

## Installation

```
pip install -r requirements.txt
```

(Falls auf dem System noetig, kann alternativ `pip install -r requirements.txt --break-system-packages` verwendet werden.)

## Start

```
python main.py
```

Danach im Browser oeffnen: http://localhost:8080

## Login

- Benutzername: `admin`
- Passwort: `ekey2026`

Die SQLite-Datenbank `ekeyQMAudits.db` wird beim ersten Start automatisch im Projektordner angelegt und
mit den Lookup-Tabellen (Audit-Typ, Audit-Status, Audit-Bewertung, Beispiel-Prozesse) sowie dem Admin-User befuellt.
Ein erneuter Start seedet die Daten nicht doppelt.

## Hinweise

- "AuditCheck" (automatisierte Pruefungen) und der teilautomatisierte "AuditInfo"-Bereich sind laut
  Spezifikation noch offen (TBD) und wurden bewusst nicht implementiert (Platzhalter-Hinweis in der GUI:
  "in Entwicklung").
- E-Mail-Erinnerungen (`com.py`) sind aktuell nur als Logging-Dummy umgesetzt (kein echter SMTP-Versand).
- Der Ordner `Dokumentation/` mit den bestehenden Word-Dateien wurde nicht veraendert.
