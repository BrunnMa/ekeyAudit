"""
config.py - Zentrale Konfiguration fuer die ekeyAudit Flask-Anwendung.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------------------
# Datenbank-Backend
# --------------------------------------------------------------------------
# "mssql"  = zentraler SQL-Server (Server SATURN, Datenbank ekeyAuditGovernance).
#            Tabellen werden beim Start automatisch angelegt, falls nicht vorhanden.
# "sqlite" = lokale Datei (nur fuer Entwicklung/Test ohne Netzwerkzugriff auf SATURN).
# Umschaltbar per Umgebungsvariable, z.B. fuer lokale Tests: EKEY_DB_BACKEND=sqlite
DB_BACKEND = os.environ.get("EKEY_DB_BACKEND", "mssql").strip().lower()

# SQLite Datenbankdatei im Projektordner (nur relevant wenn DB_BACKEND=sqlite)
DB_PATH = os.path.join(BASE_DIR, "ekeyQMAudits.db")

# --------------------------------------------------------------------------
# SQL Server (Windows-Authentifizierung / Trusted Connection)
# --------------------------------------------------------------------------
# Voraussetzung: ODBC-Treiber fuer SQL Server ist auf dem Rechner installiert
# (z.B. "ODBC Driver 17 for SQL Server") und pyodbc ist installiert.
# Bei Windows-Authentifizierung sind keine Zugangsdaten noetig - die Anwendung
# verbindet sich mit dem Windows-Benutzerkonto, unter dem sie laeuft.
MSSQL_SERVER = os.environ.get("EKEY_MSSQL_SERVER", "SATURN")
MSSQL_DATABASE = os.environ.get("EKEY_MSSQL_DATABASE", "ekeyAuditGovernance")
MSSQL_DRIVER = os.environ.get("EKEY_MSSQL_DRIVER", "ODBC Driver 17 for SQL Server")
MSSQL_TRUSTED_CONNECTION = os.environ.get("EKEY_MSSQL_TRUSTED_CONNECTION", "yes").lower() in ("1", "true", "yes")
# Nur relevant, falls MSSQL_TRUSTED_CONNECTION=no (dedizierter SQL-Login statt Windows-Auth):
MSSQL_USER = os.environ.get("EKEY_MSSQL_USER", "")
MSSQL_PASSWORD = os.environ.get("EKEY_MSSQL_PASSWORD", "")
MSSQL_TIMEOUT_SEKUNDEN = int(os.environ.get("EKEY_MSSQL_TIMEOUT", "5"))

# Ordner fuer hochgeladene Anhaenge (Proof-Anhaenge)
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

# Ordner fuer erzeugte PDF-Berichte
REPORT_DIR = os.path.join(BASE_DIR, "reports_out")

# Flask Secret Key (fuer Session-Cookies). In Produktion durch sicheren Wert ersetzen.
SECRET_KEY = os.environ.get("EKEY_AUDIT_SECRET_KEY", "ekey-audit-dev-secret-key-2026-change-me")

# Server-Einstellungen
HOST = "127.0.0.1"
PORT = 8080
DEBUG = True

# Firmenname / Anwendungstitel
APP_TITLE = "ekeyAudit - QM Auditmanagement (ISO 9001)"

# Norm-Standardwert
DEFAULT_NORM = "ISO9001:2015"

# --------------------------------------------------------------------------
# Active Directory / LDAP - fuer den Mitarbeiter-Abgleich (Auditor-Auswahl)
# --------------------------------------------------------------------------
# Ist AD_SERVER leer, bleibt die Mitarbeiterliste rein manuell (kein LDAP-Zugriff).
# Zugangsdaten bitte NICHT im Klartext hier eintragen, sondern per Umgebungsvariable
# setzen (z.B. in einer .env-Datei oder den Windows-Umgebungsvariablen des Nutzers).
AD_SERVER = os.environ.get("EKEY_AD_SERVER", "")            # z.B. "ldap://dc01.ekey.local"
AD_USE_SSL = os.environ.get("EKEY_AD_USE_SSL", "true").lower() in ("1", "true", "yes")
AD_BASE_DN = os.environ.get("EKEY_AD_BASE_DN", "")           # z.B. "OU=Mitarbeiter,DC=ekey,DC=local"
AD_BIND_USER = os.environ.get("EKEY_AD_BIND_USER", "")       # Service-Account, z.B. "ekey\\svc_audit"
AD_BIND_PASSWORD = os.environ.get("EKEY_AD_BIND_PASSWORD", "")
# LDAP-Filter fuer aktive Benutzerkonten (Standard: AD-Personenkonten, keine deaktivierten/keine Gruppen)
AD_USER_FILTER = os.environ.get(
    "EKEY_AD_USER_FILTER",
    "(&(objectClass=user)(objectCategory=person)(!(userAccountControl:1.2.840.113556.1.4.803:=2)))",
)
# Attribut-Zuordnung AD -> Mitarbeiterliste
AD_ATTR_NAME = "displayName"
AD_ATTR_USERNAME = "sAMAccountName"
AD_ATTR_EMAIL = "mail"
AD_ATTR_DEPARTMENT = "department"

for _d in (UPLOAD_DIR, REPORT_DIR):
    if not os.path.isdir(_d):
        os.makedirs(_d, exist_ok=True)
