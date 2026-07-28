"""
database.py - Datenbankzugriff fuer ekeyAudit.

Enthaelt:
 - Verbindungsaufbau fuer zwei Backends: SQL Server (config.DB_BACKEND == "mssql",
   Standard - zentraler Server SATURN / Datenbank ekeyAuditGovernance, Windows-Auth)
   und SQLite (config.DB_BACKEND == "sqlite", nur fuer lokale Entwicklung/Tests).
 - Schema-Erstellung (Tabellen werden angelegt, falls noch nicht vorhanden) fuer
   alle Arbeits-, Vorlagen- und Lookup-Tabellen, in beiden Dialekten.
 - Seed der Lookup-Tabellen und eines Admin-Users (idempotent, kein doppeltes Seeding bei Neustart)
 - Generische und spezifische CRUD-Hilfsfunktionen fuer alle Tabellen
"""

import sqlite3
from werkzeug.security import generate_password_hash

import config


class DatabaseConnectionError(Exception):
    """Wird ausgeloest, wenn keine Verbindung zur konfigurierten Datenbank hergestellt werden kann.
    Bewusst kein stiller Fallback auf eine lokale Datei - siehe main.py/gui/routes.py fuer die
    Fehleranzeige in der GUI."""


def get_connection():
    """Liefert eine neue Datenbank-Connection fuer das konfigurierte Backend."""
    if config.DB_BACKEND == "mssql":
        return _get_mssql_connection()
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _get_mssql_connection():
    try:
        import pyodbc
    except ImportError as exc:
        raise DatabaseConnectionError(
            "Paket 'pyodbc' ist nicht installiert (pip install pyodbc) oder der ODBC-Treiber "
            "fuer SQL Server fehlt auf diesem Rechner."
        ) from exc

    parts = [
        f"DRIVER={{{config.MSSQL_DRIVER}}}",
        f"SERVER={config.MSSQL_SERVER}",
        f"DATABASE={config.MSSQL_DATABASE}",
    ]
    if config.MSSQL_TRUSTED_CONNECTION:
        parts.append("Trusted_Connection=yes")
    else:
        parts.append(f"UID={config.MSSQL_USER}")
        parts.append(f"PWD={config.MSSQL_PASSWORD}")
    conn_str = ";".join(parts) + ";"

    try:
        return pyodbc.connect(conn_str, timeout=config.MSSQL_TIMEOUT_SEKUNDEN, autocommit=False)
    except Exception as exc:  # noqa: BLE001 - jede Verbindungsstoerung soll klar gemeldet werden
        raise DatabaseConnectionError(
            f"Verbindung zum SQL-Server '{config.MSSQL_SERVER}' "
            f"(Datenbank '{config.MSSQL_DATABASE}') fehlgeschlagen: {exc}"
        ) from exc


def _row_to_dict(cur, row):
    if row is None:
        return None
    if config.DB_BACKEND == "mssql":
        columns = [c[0] for c in cur.description]
        return dict(zip(columns, row))
    return dict(row)


def _get_last_insert_id(conn, cur):
    if config.DB_BACKEND == "mssql":
        cur.execute("SELECT CAST(SCOPE_IDENTITY() AS INT) AS newid")
        row = cur.fetchone()
        return row[0] if row else None
    return cur.lastrowid


def query(sql, params=(), fetchone=False, commit=False):
    """Generische Hilfsfunktion: fuehrt SQL aus, gibt Row(s) zurueck oder committet.
    Funktioniert identisch fuer SQLite und SQL Server (beide unterstuetzen "?" als
    Parameter-Platzhalter ueber sqlite3 bzw. pyodbc)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        if commit:
            new_id = _get_last_insert_id(conn, cur)
            conn.commit()
            return new_id
        if fetchone:
            row = cur.fetchone()
            return _row_to_dict(cur, row)
        rows = cur.fetchall()
        return [_row_to_dict(cur, r) for r in rows]
    finally:
        conn.close()


def execute(sql, params=()):
    """Fuehrt ein INSERT/UPDATE/DELETE aus und gibt die lastrowid zurueck."""
    return query(sql, params, commit=True)


# --------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------

SCHEMA_STATEMENTS = [
    # ---- Benutzerverwaltung ----
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        rolle TEXT NOT NULL DEFAULT 'Auditor',
        aktiv INTEGER NOT NULL DEFAULT 1
    )
    """,

    # ---- Anwendungseinstellungen (Key/Value) ----
    """
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """,

    # ---- Lookups ----
    """
    CREATE TABLE IF NOT EXISTS Look_QM_AuditTyp (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        auditTyp TEXT NOT NULL,
        info TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS Look_QM_AuditStatus (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        auditStatus TEXT NOT NULL,
        info TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS Look_QM_AuditBewertung (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        auditResult TEXT NOT NULL,
        info TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS Look_QM_AuditProzess (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        processName TEXT NOT NULL,
        processNumber TEXT,
        processOwner TEXT,
        fachbereich TEXT,
        link TEXT,
        normKapitel TEXT,
        info TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS Look_QM_Fachbereich (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fachbereich TEXT NOT NULL,
        leitung TEXT,
        info TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS Look_QM_Mitarbeiter (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        username TEXT UNIQUE,
        email TEXT,
        abteilung TEXT,
        quelle TEXT NOT NULL DEFAULT 'manuell',
        aktiv INTEGER NOT NULL DEFAULT 1,
        letzterSync TEXT
    )
    """,

    # ---- Arbeitsdaten ----
    """
    CREATE TABLE IF NOT EXISTS STG_QM_AuditProgramm (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        auditTyp TEXT,
        auditJahr INTEGER,
        norm TEXT,
        auditor TEXT,
        auditStatus INTEGER,
        unternehmen TEXT,
        standort TEXT,
        startDatum TEXT,
        endDatum TEXT,
        beauftragt TEXT,
        beauftragtAm TEXT,
        beauftragtInfo TEXT,
        FOREIGN KEY (auditStatus) REFERENCES Look_QM_AuditStatus(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS STG_QM_AuditZiele (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        auditProgramId INTEGER NOT NULL,
        auditZiel TEXT,
        FOREIGN KEY (auditProgramId) REFERENCES STG_QM_AuditProgramm(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS STG_QM_AuditPlan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        auditProgrammId INTEGER NOT NULL,
        fachbereich TEXT,
        auditProzess INTEGER,
        verantwortlich TEXT,
        datumAuditEnde TEXT,
        datumInterview TEXT,
        info TEXT,
        auditStatus INTEGER,
        checklisteId INTEGER,
        FOREIGN KEY (auditProgrammId) REFERENCES STG_QM_AuditProgramm(id),
        FOREIGN KEY (auditProzess) REFERENCES Look_QM_AuditProzess(id),
        FOREIGN KEY (auditStatus) REFERENCES Look_QM_AuditStatus(id),
        FOREIGN KEY (checklisteId) REFERENCES STG_QM_AuditCheckliste(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS STG_QM_AuditProofs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        auditPlanId INTEGER NOT NULL,
        auditChecklisteID INTEGER,
        auditFrage TEXT,
        normKapitel TEXT,
        anhangId INTEGER,
        linkId INTEGER,
        auditresultId INTEGER,
        auditResultInfo TEXT,
        punkte INTEGER,
        auditor TEXT,
        bewertung TEXT,
        beispiel TEXT,
        FOREIGN KEY (auditPlanId) REFERENCES STG_QM_AuditPlan(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS STG_QM_AuditAnhang (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        auditProofsId INTEGER,
        auditChecklisteID INTEGER,
        anhang TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS STG_QM_AuditLink (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        auditProofsId INTEGER,
        auditChecklisteID INTEGER,
        link TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS STG_QM_AuditInterview (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        auditProofsId INTEGER NOT NULL,
        nameAuditor TEXT,
        inhalt TEXT,
        FOREIGN KEY (auditProofsId) REFERENCES STG_QM_AuditProofs(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS STG_QM_AuditResult (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        auditProofsId INTEGER NOT NULL,
        nameAuditor TEXT,
        auditBewertungID INTEGER,
        datumerfasst TEXT,
        antwort TEXT,
        auditResultInfo TEXT,
        FOREIGN KEY (auditProofsId) REFERENCES STG_QM_AuditProofs(id),
        FOREIGN KEY (auditBewertungID) REFERENCES Look_QM_AuditBewertung(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS STG_QM_AuditAbweichung (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        auditResultID INTEGER NOT NULL,
        abweichung TEXT,
        abweichungStatus INTEGER,
        nameAuditor TEXT,
        datumErfasst TEXT,
        nameEigner TEXT,
        FOREIGN KEY (auditResultID) REFERENCES STG_QM_AuditResult(id),
        FOREIGN KEY (abweichungStatus) REFERENCES Look_QM_AuditStatus(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS STG_QM_AuditMassnahme (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        auditAbweichungID INTEGER NOT NULL,
        massnahme TEXT,
        datumMassnahme TEXT,
        nameEigner TEXT,
        FOREIGN KEY (auditAbweichungID) REFERENCES STG_QM_AuditAbweichung(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS STG_QM_StatusMassnahme (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        auditMassnahmeID INTEGER NOT NULL,
        statusDatum TEXT,
        status INTEGER,
        statusNeu INTEGER,
        statusName TEXT,
        infoStatus TEXT,
        FOREIGN KEY (auditMassnahmeID) REFERENCES STG_QM_AuditMassnahme(id),
        FOREIGN KEY (status) REFERENCES Look_QM_AuditStatus(id),
        FOREIGN KEY (statusNeu) REFERENCES Look_QM_AuditStatus(id)
    )
    """,

    # ---- Vorlagen ----
    """
    CREATE TABLE IF NOT EXISTS STG_QM_AuditCheckliste (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prozessId INTEGER,
        bezeichnung TEXT,
        link TEXT,
        eigner TEXT,
        FOREIGN KEY (prozessId) REFERENCES Look_QM_AuditProzess(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS STG_QM_AuditChecklisteVersion (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        auditChecklisteID INTEGER NOT NULL,
        version INTEGER,
        datumVersion TEXT,
        nameVersion TEXT,
        infoVersion TEXT,
        FOREIGN KEY (auditChecklisteID) REFERENCES STG_QM_AuditCheckliste(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS STG_QM_AuditChecklisteProofs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        auditChecklisteID INTEGER NOT NULL,
        auditFrage TEXT,
        normKapitel TEXT,
        anhangId INTEGER,
        linkId INTEGER,
        auditresultId INTEGER,
        auditResultInfo TEXT,
        FOREIGN KEY (auditChecklisteID) REFERENCES STG_QM_AuditCheckliste(id)
    )
    """,

    # ---- TBD lt. Spezifikation: nur Platzhalter-Tabelle, nicht funktional genutzt ----
    """
    CREATE TABLE IF NOT EXISTS STG_QM_AuditCheck (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        info TEXT DEFAULT 'TBD - automatisierte Pruefungen sind laut Spezifikation noch offen / in Entwicklung'
    )
    """,
]


# --------------------------------------------------------------------------
# Schema fuer SQL Server (T-SQL-Dialekt). Gleiche Tabellen/Spalten/Reihenfolge
# wie SCHEMA_STATEMENTS (SQLite), nur mit IDENTITY statt AUTOINCREMENT und
# NVARCHAR statt TEXT. Jeder Eintrag ist (Tabellenname, CREATE-TABLE-Body ohne
# das "CREATE TABLE IF NOT EXISTS" - die Existenzpruefung erfolgt separat
# per IF OBJECT_ID(...) IS NULL, da T-SQL kein "IF NOT EXISTS" fuer CREATE TABLE kennt).
# --------------------------------------------------------------------------

SCHEMA_STATEMENTS_MSSQL = [
    ("users", """
        id INT IDENTITY(1,1) PRIMARY KEY,
        username NVARCHAR(255) UNIQUE NOT NULL,
        password_hash NVARCHAR(255) NOT NULL,
        rolle NVARCHAR(50) NOT NULL DEFAULT 'Auditor',
        aktiv INT NOT NULL DEFAULT 1
    """),
    ("app_settings", """
        [key] NVARCHAR(255) PRIMARY KEY,
        value NVARCHAR(MAX)
    """),
    ("Look_QM_AuditTyp", """
        id INT IDENTITY(1,1) PRIMARY KEY,
        auditTyp NVARCHAR(255) NOT NULL,
        info NVARCHAR(MAX)
    """),
    ("Look_QM_AuditStatus", """
        id INT IDENTITY(1,1) PRIMARY KEY,
        auditStatus NVARCHAR(255) NOT NULL,
        info NVARCHAR(MAX)
    """),
    ("Look_QM_AuditBewertung", """
        id INT IDENTITY(1,1) PRIMARY KEY,
        auditResult NVARCHAR(255) NOT NULL,
        info NVARCHAR(MAX)
    """),
    ("Look_QM_AuditProzess", """
        id INT IDENTITY(1,1) PRIMARY KEY,
        processName NVARCHAR(255) NOT NULL,
        processNumber NVARCHAR(100),
        processOwner NVARCHAR(255),
        fachbereich NVARCHAR(50),
        link NVARCHAR(MAX),
        normKapitel NVARCHAR(255),
        info NVARCHAR(MAX)
    """),
    ("Look_QM_Fachbereich", """
        id INT IDENTITY(1,1) PRIMARY KEY,
        fachbereich NVARCHAR(255) NOT NULL,
        leitung NVARCHAR(255),
        info NVARCHAR(MAX)
    """),
    ("Look_QM_Mitarbeiter", """
        id INT IDENTITY(1,1) PRIMARY KEY,
        name NVARCHAR(255) NOT NULL,
        username NVARCHAR(255),
        email NVARCHAR(255),
        abteilung NVARCHAR(255),
        quelle NVARCHAR(50) NOT NULL DEFAULT 'manuell',
        aktiv INT NOT NULL DEFAULT 1,
        letzterSync NVARCHAR(50)
    """),
    ("STG_QM_AuditProgramm", """
        id INT IDENTITY(1,1) PRIMARY KEY,
        auditTyp NVARCHAR(255),
        auditJahr INT,
        norm NVARCHAR(100),
        auditor NVARCHAR(MAX),
        auditStatus INT,
        unternehmen NVARCHAR(255),
        standort NVARCHAR(255),
        startDatum NVARCHAR(20),
        endDatum NVARCHAR(20),
        beauftragt NVARCHAR(255),
        beauftragtAm NVARCHAR(20),
        beauftragtInfo NVARCHAR(MAX),
        FOREIGN KEY (auditStatus) REFERENCES Look_QM_AuditStatus(id)
    """),
    ("STG_QM_AuditZiele", """
        id INT IDENTITY(1,1) PRIMARY KEY,
        auditProgramId INT NOT NULL,
        auditZiel NVARCHAR(MAX),
        FOREIGN KEY (auditProgramId) REFERENCES STG_QM_AuditProgramm(id)
    """),
    ("STG_QM_AuditPlan", """
        id INT IDENTITY(1,1) PRIMARY KEY,
        auditProgrammId INT NOT NULL,
        fachbereich NVARCHAR(50),
        auditProzess INT,
        verantwortlich NVARCHAR(255),
        datumAuditEnde NVARCHAR(20),
        datumInterview NVARCHAR(20),
        info NVARCHAR(MAX),
        auditStatus INT,
        checklisteId INT,
        FOREIGN KEY (auditProgrammId) REFERENCES STG_QM_AuditProgramm(id),
        FOREIGN KEY (auditProzess) REFERENCES Look_QM_AuditProzess(id),
        FOREIGN KEY (auditStatus) REFERENCES Look_QM_AuditStatus(id)
    """),
    ("STG_QM_AuditProofs", """
        id INT IDENTITY(1,1) PRIMARY KEY,
        auditPlanId INT NOT NULL,
        auditChecklisteID INT,
        auditFrage NVARCHAR(MAX),
        normKapitel NVARCHAR(255),
        anhangId INT,
        linkId INT,
        auditresultId INT,
        auditResultInfo NVARCHAR(MAX),
        punkte INT,
        auditor NVARCHAR(255),
        bewertung NVARCHAR(MAX),
        beispiel NVARCHAR(MAX),
        FOREIGN KEY (auditPlanId) REFERENCES STG_QM_AuditPlan(id)
    """),
    ("STG_QM_AuditAnhang", """
        id INT IDENTITY(1,1) PRIMARY KEY,
        auditProofsId INT,
        auditChecklisteID INT,
        anhang NVARCHAR(MAX)
    """),
    ("STG_QM_AuditLink", """
        id INT IDENTITY(1,1) PRIMARY KEY,
        auditProofsId INT,
        auditChecklisteID INT,
        link NVARCHAR(MAX)
    """),
    ("STG_QM_AuditInterview", """
        id INT IDENTITY(1,1) PRIMARY KEY,
        auditProofsId INT NOT NULL,
        nameAuditor NVARCHAR(255),
        inhalt NVARCHAR(MAX),
        FOREIGN KEY (auditProofsId) REFERENCES STG_QM_AuditProofs(id)
    """),
    ("STG_QM_AuditResult", """
        id INT IDENTITY(1,1) PRIMARY KEY,
        auditProofsId INT NOT NULL,
        nameAuditor NVARCHAR(255),
        auditBewertungID INT,
        datumerfasst NVARCHAR(20),
        antwort NVARCHAR(MAX),
        auditResultInfo NVARCHAR(MAX),
        FOREIGN KEY (auditProofsId) REFERENCES STG_QM_AuditProofs(id),
        FOREIGN KEY (auditBewertungID) REFERENCES Look_QM_AuditBewertung(id)
    """),
    ("STG_QM_AuditAbweichung", """
        id INT IDENTITY(1,1) PRIMARY KEY,
        auditResultID INT NOT NULL,
        abweichung NVARCHAR(MAX),
        abweichungStatus INT,
        nameAuditor NVARCHAR(255),
        datumErfasst NVARCHAR(20),
        nameEigner NVARCHAR(255),
        FOREIGN KEY (auditResultID) REFERENCES STG_QM_AuditResult(id),
        FOREIGN KEY (abweichungStatus) REFERENCES Look_QM_AuditStatus(id)
    """),
    ("STG_QM_AuditMassnahme", """
        id INT IDENTITY(1,1) PRIMARY KEY,
        auditAbweichungID INT NOT NULL,
        massnahme NVARCHAR(MAX),
        datumMassnahme NVARCHAR(20),
        nameEigner NVARCHAR(255),
        FOREIGN KEY (auditAbweichungID) REFERENCES STG_QM_AuditAbweichung(id)
    """),
    ("STG_QM_StatusMassnahme", """
        id INT IDENTITY(1,1) PRIMARY KEY,
        auditMassnahmeID INT NOT NULL,
        statusDatum NVARCHAR(20),
        status INT,
        statusNeu INT,
        statusName NVARCHAR(255),
        infoStatus NVARCHAR(MAX),
        FOREIGN KEY (auditMassnahmeID) REFERENCES STG_QM_AuditMassnahme(id),
        FOREIGN KEY (status) REFERENCES Look_QM_AuditStatus(id),
        FOREIGN KEY (statusNeu) REFERENCES Look_QM_AuditStatus(id)
    """),
    ("STG_QM_AuditCheckliste", """
        id INT IDENTITY(1,1) PRIMARY KEY,
        prozessId INT,
        bezeichnung NVARCHAR(255),
        link NVARCHAR(MAX),
        eigner NVARCHAR(255),
        FOREIGN KEY (prozessId) REFERENCES Look_QM_AuditProzess(id)
    """),
    ("STG_QM_AuditChecklisteVersion", """
        id INT IDENTITY(1,1) PRIMARY KEY,
        auditChecklisteID INT NOT NULL,
        version INT,
        datumVersion NVARCHAR(20),
        nameVersion NVARCHAR(255),
        infoVersion NVARCHAR(MAX),
        FOREIGN KEY (auditChecklisteID) REFERENCES STG_QM_AuditCheckliste(id)
    """),
    ("STG_QM_AuditChecklisteProofs", """
        id INT IDENTITY(1,1) PRIMARY KEY,
        auditChecklisteID INT NOT NULL,
        auditFrage NVARCHAR(MAX),
        normKapitel NVARCHAR(255),
        anhangId INT,
        linkId INT,
        auditresultId INT,
        auditResultInfo NVARCHAR(MAX),
        FOREIGN KEY (auditChecklisteID) REFERENCES STG_QM_AuditCheckliste(id)
    """),
    ("STG_QM_AuditCheck", """
        id INT IDENTITY(1,1) PRIMARY KEY,
        info NVARCHAR(MAX) DEFAULT 'TBD - automatisierte Pruefungen sind laut Spezifikation noch offen / in Entwicklung'
    """),
]


def init_db():
    """Legt beim ersten Start alle Tabellen an (SQL Server oder SQLite, je nach
    config.DB_BACKEND) und seeded Lookup-Daten + Admin-User (idempotent)."""
    if config.DB_BACKEND == "mssql":
        _init_schema_mssql()
    else:
        _init_schema_sqlite()

    _seed_lookups()
    _seed_admin_user()
    _seed_example_prozesse()
    _seed_example_mitarbeiter()
    _seed_default_settings()
    _fix_legacy_fachbereich_values()
    _migrate_auditproofs_enrichment_columns()
    _migrate_auditplan_checkliste_column()


def _column_exists(cur, table, column):
    if config.DB_BACKEND == "mssql":
        cur.execute("""
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = ? AND COLUMN_NAME = ?
        """, (table, column))
        return cur.fetchone() is not None
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def _migrate_auditproofs_enrichment_columns():
    """Nachtraeglich eingefuehrte Spalten fuer die direkt im Audit-Plan angereicherte
    Checkliste (Punkte/Auditor/Bewertung/Beispiel je Proof). Bei bereits bestehenden
    Datenbanken (aeltere Installation) werden fehlende Spalten per ALTER TABLE ergaenzt,
    damit keine Daten verloren gehen. Bei Neuinstallationen enthaelt CREATE TABLE die
    Spalten bereits, hier passiert dann nichts."""
    columns = [
        ("punkte", "INTEGER", "INT"),
        ("auditor", "TEXT", "NVARCHAR(255)"),
        ("bewertung", "TEXT", "NVARCHAR(MAX)"),
        ("beispiel", "TEXT", "NVARCHAR(MAX)"),
    ]
    conn = get_connection()
    try:
        cur = conn.cursor()
        for column, sqlite_type, mssql_type in columns:
            if _column_exists(cur, "STG_QM_AuditProofs", column):
                continue
            if config.DB_BACKEND == "mssql":
                cur.execute(f"ALTER TABLE dbo.STG_QM_AuditProofs ADD {column} {mssql_type}")
            else:
                cur.execute(f"ALTER TABLE STG_QM_AuditProofs ADD COLUMN {column} {sqlite_type}")
        conn.commit()
    finally:
        conn.close()


def _migrate_auditplan_checkliste_column():
    """Nachtraeglich eingefuehrte Spalte STG_QM_AuditPlan.checklisteId: speichert die
    zugeordnete Checkliste direkt am Plan-Eintrag, unabhaengig davon, ob die Checkliste
    (noch) Proofs enthaelt. Vorher wurde die Zuordnung nur indirekt aus dem ersten kopierten
    Proof abgeleitet - das fuehrte dazu, dass eine Checkliste ohne Pruefpunkte (Proofs) als
    'nicht zugeordnet' erschien, obwohl sie sehr wohl gewaehlt und uebernommen wurde.
    Bei bereits bestehenden Datenbanken wird die Spalte per ALTER TABLE ergaenzt und, sofern
    moeglich, aus bereits vorhandenen Proofs rueckwirkend befuellt (Altbestand)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        if not _column_exists(cur, "STG_QM_AuditPlan", "checklisteId"):
            if config.DB_BACKEND == "mssql":
                cur.execute("ALTER TABLE dbo.STG_QM_AuditPlan ADD checklisteId INT")
            else:
                cur.execute("ALTER TABLE STG_QM_AuditPlan ADD COLUMN checklisteId INTEGER")
            conn.commit()
    finally:
        conn.close()

    # Altbestand nachziehen: Plaene, die schon Proofs mit auditChecklisteID haben, aber noch
    # kein checklisteId am Plan-Eintrag selbst gesetzt bekamen (weil sie vor dieser Migration
    # angelegt wurden).
    rows = query("""
        SELECT pl.id AS plan_id, MIN(pf.auditChecklisteID) AS checkliste_id
        FROM STG_QM_AuditPlan pl
        JOIN STG_QM_AuditProofs pf ON pf.auditPlanId = pl.id
        WHERE pl.checklisteId IS NULL AND pf.auditChecklisteID IS NOT NULL
        GROUP BY pl.id
    """)
    for r in rows:
        execute("UPDATE STG_QM_AuditPlan SET checklisteId=? WHERE id=?", (r["checkliste_id"], r["plan_id"]))


def _fix_legacy_fachbereich_values():
    """Einmalige Reparatur von Alt-Daten: vor Einfuehrung der Fachbereich-Tabelle
    (Look_QM_Fachbereich) enthielt Look_QM_AuditProzess.fachbereich Freitext
    (z.B. 'Einkauf', 'Entwicklung'). Seither muss dort eine gueltige Fachbereich-ID
    stehen, sonst schlaegt der JOIN in list_prozesse() auf SQL Server mit einem
    Konvertierungsfehler fehl (SQLite faellt das nicht auf, da dort Typen nicht
    strikt geprueft werden). Ungueltige Werte werden hier auf NULL gesetzt -
    der Fachbereich kann danach ueber die GUI neu zugeordnet werden."""
    rows = query("SELECT id, fachbereich FROM Look_QM_AuditProzess")
    for r in rows:
        wert = r["fachbereich"]
        if wert is None or str(wert).strip() == "":
            continue
        try:
            int(wert)
        except (ValueError, TypeError):
            execute("UPDATE Look_QM_AuditProzess SET fachbereich = NULL WHERE id = ?", (r["id"],))


def _init_schema_mssql():
    conn = get_connection()
    try:
        cur = conn.cursor()
        for table_name, body in SCHEMA_STATEMENTS_MSSQL:
            ddl = f"""
            IF OBJECT_ID(N'dbo.{table_name}', N'U') IS NULL
            BEGIN
                CREATE TABLE dbo.{table_name} ({body})
            END
            """
            cur.execute(ddl)
        conn.commit()
    finally:
        conn.close()


def _init_schema_sqlite():
    conn = get_connection()
    try:
        cur = conn.cursor()
        for stmt in SCHEMA_STATEMENTS:
            cur.execute(stmt)
        conn.commit()
    finally:
        conn.close()


def _seed_default_settings():
    """Standardwerte fuer app_settings, falls noch nicht vorhanden. Authentifizierung ist per Default AUS."""
    defaults = {
        "auth_enabled": "0",
    }
    conn = get_connection()
    try:
        cur = conn.cursor()
        for key, value in defaults.items():
            cur.execute("SELECT 1 FROM app_settings WHERE [key] = ?", (key,))
            if cur.fetchone() is None:
                cur.execute("INSERT INTO app_settings ([key], value) VALUES (?, ?)", (key, value))
        conn.commit()
    finally:
        conn.close()


def get_setting(key, default=None):
    row = query("SELECT value FROM app_settings WHERE [key] = ?", (key,), fetchone=True)
    return row["value"] if row else default


def set_setting(key, value):
    """Legt einen Einstellungswert an oder aktualisiert ihn (Upsert).
    SQLite und SQL Server verwenden dafuer unterschiedliche Syntax, daher hier
    unabhaengig vom SQL-Dialekt per einfachem Exists-Check geloest."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        if config.DB_BACKEND == "mssql":
            cur.execute("SELECT 1 FROM app_settings WHERE [key] = ?", (key,))
            if cur.fetchone():
                cur.execute("UPDATE app_settings SET value = ? WHERE [key] = ?", (value, key))
            else:
                cur.execute("INSERT INTO app_settings ([key], value) VALUES (?, ?)", (key, value))
        else:
            cur.execute(
                "INSERT INTO app_settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
        conn.commit()
    finally:
        conn.close()


def _table_count(cur, table, where_sql="", params=()):
    cur.execute(f"SELECT COUNT(*) FROM {table} {where_sql}", params)
    return cur.fetchone()[0]


def _identity_insert(cur, table, on):
    """Nur fuer SQL Server relevant: erlaubt/verbietet das Einfuegen expliziter
    Werte in eine IDENTITY-Spalte (fuer die Lookup-Seeds mit festen IDs 1..n)."""
    if config.DB_BACKEND == "mssql":
        cur.execute(f"SET IDENTITY_INSERT dbo.{table} {'ON' if on else 'OFF'}")


def _seed_lookups():
    conn = get_connection()
    try:
        cur = conn.cursor()

        if _table_count(cur, "Look_QM_AuditTyp") == 0:
            _identity_insert(cur, "Look_QM_AuditTyp", True)
            cur.executemany(
                "INSERT INTO Look_QM_AuditTyp (id, auditTyp, info) VALUES (?, ?, ?)",
                [
                    (1, "internes Audit", ""),
                    (2, "Ueberwachungsaudit", ""),
                    (3, "(Re)Zertifizierungsaudit", ""),
                    (4, "Lieferantenaudit", ""),
                    (5, "automatisiertes internes Audit", ""),
                ],
            )
            _identity_insert(cur, "Look_QM_AuditTyp", False)

        if _table_count(cur, "Look_QM_AuditStatus") == 0:
            _identity_insert(cur, "Look_QM_AuditStatus", True)
            cur.executemany(
                "INSERT INTO Look_QM_AuditStatus (id, auditStatus, info) VALUES (?, ?, ?)",
                [
                    (1, "Erfasst", "Audit ist erfasst aber die Durchfuehrung ist noch nicht geplant"),
                    (2, "Geplant", "Durchfuehrung ist geplant. Checklisten sind fertig erstellt"),
                    (3, "In Arbeit", "Audit wird durchgefuehrt, Checklisten werden abgearbeitet, Abweichungen erfasst usw."),
                    (4, "Fertig", "Audit ist abgeschlossen; Abweichungen sind behoben"),
                    (5, "Wirksam", "Massnahmen zu Abweichungen sind behoben"),
                ],
            )
            _identity_insert(cur, "Look_QM_AuditStatus", False)

        if _table_count(cur, "Look_QM_AuditBewertung") == 0:
            _identity_insert(cur, "Look_QM_AuditBewertung", True)
            cur.executemany(
                "INSERT INTO Look_QM_AuditBewertung (id, auditResult, info) VALUES (?, ?, ?)",
                [
                    (1, "Normkonform", "Der Prozess entspricht der Anforderung der Norm"),
                    (2, "Empfehlung", "Der Prozess ist normkonform. Eine Verbesserung wird aber empfohlen"),
                    (3, "Abweichung", "Es wurde im Prozess eine Abweichung festgestellt"),
                    (4, "Nicht geprueft", "Der Pruefpunkt wurde nicht geprueft"),
                ],
            )
            _identity_insert(cur, "Look_QM_AuditBewertung", False)

        conn.commit()
    finally:
        conn.close()


def _seed_example_prozesse():
    """Hinweis: fachbereich bleibt hier bewusst NULL. Seit der Fachbereich-Tabelle
    (Look_QM_Fachbereich) muss dieses Feld eine gueltige Fachbereich-ID enthalten,
    nicht mehr Freitext - die Beispielprozesse werden dem Fachbereich spaeter ueber
    die GUI (Audit governance > Prozesse erfassen) zugeordnet."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        if _table_count(cur, "Look_QM_AuditProzess") == 0:
            cur.executemany(
                """INSERT INTO Look_QM_AuditProzess
                   (processName, processNumber, processOwner, fachbereich, link, normKapitel, info)
                   VALUES (?, ?, ?, NULL, ?, ?, ?)""",
                [
                    ("Produktentwicklung", "P-01", "M. Muster", "", "8.3", "Beispielprozess"),
                    ("Beschaffung", "P-02", "A. Beispiel", "", "8.4", "Beispielprozess"),
                    ("Kundenreklamation", "P-03", "S. Sample", "", "8.7 / 10.2", "Beispielprozess"),
                ],
            )
            conn.commit()
    finally:
        conn.close()


def _seed_example_mitarbeiter():
    """Beispiel-Mitarbeiter fuer die Auditor-Auswahl, solange kein AD angebunden ist.
    Koennen jederzeit unter Konfiguration > Mitarbeiter geloescht/ergaenzt werden."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        if _table_count(cur, "Look_QM_Mitarbeiter") == 0:
            cur.executemany(
                """INSERT INTO Look_QM_Mitarbeiter (name, username, email, abteilung, quelle, aktiv)
                   VALUES (?, ?, ?, ?, 'manuell', 1)""",
                [
                    ("Manfred Brunner", "brunnma", "manfred.brunner@ekey.net", "QM"),
                    ("Holger Methe", "metheho", "", "QM"),
                    ("Christoph Madl", "madlch", "", "Entwicklung"),
                ],
            )
            conn.commit()
    finally:
        conn.close()


def _seed_admin_user():
    conn = get_connection()
    try:
        cur = conn.cursor()
        if _table_count(cur, "users", "WHERE username = ?", ("admin",)) == 0:
            cur.execute(
                "INSERT INTO users (username, password_hash, rolle, aktiv) VALUES (?, ?, ?, 1)",
                ("admin", generate_password_hash("ekey2026"), "Admin"),
            )
            conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Lookup-Helfer
# --------------------------------------------------------------------------

def get_lookup(table):
    return query(f"SELECT * FROM {table} ORDER BY id")


def get_lookup_map(table, key_field, value_field):
    rows = get_lookup(table)
    return {r[key_field]: r[value_field] for r in rows}


def list_prozesse(fachbereich_id=None):
    """Prozessliste (Look_QM_AuditProzess) inkl. Fachbereichsbezeichnung (per FK aufgeloest).
    Sortiert nach Fachbereich (Prozesse ohne Fachbereich zuletzt), dann nach Prozessname,
    damit die GUI die Liste gruppiert nach Fachbereich anzeigen kann. Optional auf einen
    Fachbereich einschraenkbar (Filter in der GUI)."""
    sql = """
        SELECT p.*,
               COALESCE(fb.fachbereich, '(ohne Fachbereich)') AS fachbereichName
        FROM Look_QM_AuditProzess p
        LEFT JOIN Look_QM_Fachbereich fb ON fb.id = p.fachbereich
    """
    params = ()
    if fachbereich_id:
        sql += " WHERE p.fachbereich = ?"
        params = (fachbereich_id,)
    sql += " ORDER BY CASE WHEN fb.fachbereich IS NULL THEN 1 ELSE 0 END, fachbereichName, p.processName"
    return query(sql, params)


def get_prozess(prozess_id):
    return query("SELECT * FROM Look_QM_AuditProzess WHERE id = ?", (prozess_id,), fetchone=True)


def list_prozess_owner_namen():
    """Distinkte, bereits erfasste Werte aus Look_QM_AuditProzess.processOwner - fuer die
    Auswahl-Combobox im Feld 'Prozessverantwortlicher' (nur tatsaechlich schon eingegebene Namen)."""
    rows = query("""
        SELECT DISTINCT processOwner FROM Look_QM_AuditProzess
        WHERE processOwner IS NOT NULL AND processOwner <> ''
        ORDER BY processOwner
    """)
    return [r["processOwner"] for r in rows]


def lookup_is_referenced(table, id_value):
    """Prueft, ob ein Lookup-Eintrag bereits von Arbeitsdaten referenziert wird (fuer Loeschwarnung)."""
    checks = {
        "Look_QM_AuditStatus": [
            ("STG_QM_AuditProgramm", "auditStatus"),
            ("STG_QM_AuditPlan", "auditStatus"),
            ("STG_QM_AuditAbweichung", "abweichungStatus"),
            ("STG_QM_StatusMassnahme", "status"),
            ("STG_QM_StatusMassnahme", "statusNeu"),
        ],
        "Look_QM_AuditTyp": [("STG_QM_AuditProgramm", "auditTyp")],
        "Look_QM_AuditBewertung": [("STG_QM_AuditResult", "auditBewertungID")],
        "Look_QM_AuditProzess": [
            ("STG_QM_AuditPlan", "auditProzess"),
            ("STG_QM_AuditCheckliste", "prozessId"),
        ],
        "Look_QM_Fachbereich": [
            ("STG_QM_AuditPlan", "fachbereich"),
            ("Look_QM_AuditProzess", "fachbereich"),
        ],
    }
    for tbl, field in checks.get(table, []):
        row = query(f"SELECT COUNT(*) AS c FROM {tbl} WHERE {field} = ?", (id_value,), fetchone=True)
        if row and row["c"] > 0:
            return True
    return False


# --------------------------------------------------------------------------
# AuditProgramm / AuditZiele
# --------------------------------------------------------------------------

def list_audit_programme():
    return query("""
        SELECT p.*, s.auditStatus AS statusName
        FROM STG_QM_AuditProgramm p
        LEFT JOIN Look_QM_AuditStatus s ON s.id = p.auditStatus
        ORDER BY p.auditJahr DESC, p.id DESC
    """)


def get_audit_programm(programm_id):
    return query("SELECT * FROM STG_QM_AuditProgramm WHERE id = ?", (programm_id,), fetchone=True)


def create_audit_programm(data):
    return execute("""
        INSERT INTO STG_QM_AuditProgramm
        (auditTyp, auditJahr, norm, auditor, auditStatus, unternehmen, standort,
         startDatum, endDatum, beauftragt, beauftragtAm, beauftragtInfo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("auditTyp"), data.get("auditJahr"), data.get("norm"), data.get("auditor"),
        data.get("auditStatus"), data.get("unternehmen"), data.get("standort"),
        data.get("startDatum"), data.get("endDatum"), data.get("beauftragt"),
        data.get("beauftragtAm"), data.get("beauftragtInfo"),
    ))


def update_audit_programm(programm_id, data):
    execute("""
        UPDATE STG_QM_AuditProgramm SET
        auditTyp=?, auditJahr=?, norm=?, auditor=?, auditStatus=?, unternehmen=?, standort=?,
        startDatum=?, endDatum=?, beauftragt=?, beauftragtAm=?, beauftragtInfo=?
        WHERE id=?
    """, (
        data.get("auditTyp"), data.get("auditJahr"), data.get("norm"), data.get("auditor"),
        data.get("auditStatus"), data.get("unternehmen"), data.get("standort"),
        data.get("startDatum"), data.get("endDatum"), data.get("beauftragt"),
        data.get("beauftragtAm"), data.get("beauftragtInfo"), programm_id,
    ))


def list_audit_ziele(programm_id):
    return query("SELECT * FROM STG_QM_AuditZiele WHERE auditProgramId = ? ORDER BY id", (programm_id,))


def add_audit_ziel(programm_id, ziel_text):
    return execute("INSERT INTO STG_QM_AuditZiele (auditProgramId, auditZiel) VALUES (?, ?)",
                   (programm_id, ziel_text))


def delete_audit_ziel(ziel_id):
    execute("DELETE FROM STG_QM_AuditZiele WHERE id = ?", (ziel_id,))


# --------------------------------------------------------------------------
# AuditPlan
# --------------------------------------------------------------------------

def list_audit_plaene(programm_id=None):
    sql = """
        SELECT pl.*, pr.processName AS prozessName, s.auditStatus AS statusName,
               prog.startDatum AS progStart, prog.endDatum AS progEnde, prog.auditJahr,
               fb.fachbereich AS fachbereichName, fb.leitung AS fachbereichLeitung
        FROM STG_QM_AuditPlan pl
        LEFT JOIN Look_QM_AuditProzess pr ON pr.id = pl.auditProzess
        LEFT JOIN Look_QM_AuditStatus s ON s.id = pl.auditStatus
        LEFT JOIN STG_QM_AuditProgramm prog ON prog.id = pl.auditProgrammId
        LEFT JOIN Look_QM_Fachbereich fb ON fb.id = pl.fachbereich
    """
    params = ()
    if programm_id:
        sql += " WHERE pl.auditProgrammId = ?"
        params = (programm_id,)
    sql += " ORDER BY pl.id DESC"
    return query(sql, params)


def get_audit_plan(plan_id):
    return query("SELECT * FROM STG_QM_AuditPlan WHERE id = ?", (plan_id,), fetchone=True)


def delete_audit_plan(plan_id):
    """Loescht einen Audit-Plan-Eintrag vollstaendig - inkl. aller abhaengigen
    Datenbereiche (Proofs, Ergebnisse, Abweichungen, Massnahmen, Status-Historie
    der Massnahmen, Interviews, Links, Anhaenge). Reihenfolge: von den Blaettern
    der Abhaengigkeitskette nach oben, damit keine Fremdschluessel verwaisen."""
    execute("""
        DELETE FROM STG_QM_StatusMassnahme WHERE auditMassnahmeID IN (
            SELECT m.id FROM STG_QM_AuditMassnahme m
            JOIN STG_QM_AuditAbweichung a ON a.id = m.auditAbweichungID
            JOIN STG_QM_AuditResult r ON r.id = a.auditResultID
            JOIN STG_QM_AuditProofs pf ON pf.id = r.auditProofsId
            WHERE pf.auditPlanId = ?
        )
    """, (plan_id,))
    execute("""
        DELETE FROM STG_QM_AuditMassnahme WHERE auditAbweichungID IN (
            SELECT a.id FROM STG_QM_AuditAbweichung a
            JOIN STG_QM_AuditResult r ON r.id = a.auditResultID
            JOIN STG_QM_AuditProofs pf ON pf.id = r.auditProofsId
            WHERE pf.auditPlanId = ?
        )
    """, (plan_id,))
    execute("""
        DELETE FROM STG_QM_AuditAbweichung WHERE auditResultID IN (
            SELECT r.id FROM STG_QM_AuditResult r
            JOIN STG_QM_AuditProofs pf ON pf.id = r.auditProofsId
            WHERE pf.auditPlanId = ?
        )
    """, (plan_id,))
    execute("""
        DELETE FROM STG_QM_AuditResult WHERE auditProofsId IN (
            SELECT id FROM STG_QM_AuditProofs WHERE auditPlanId = ?
        )
    """, (plan_id,))
    execute("""
        DELETE FROM STG_QM_AuditInterview WHERE auditProofsId IN (
            SELECT id FROM STG_QM_AuditProofs WHERE auditPlanId = ?
        )
    """, (plan_id,))
    execute("""
        DELETE FROM STG_QM_AuditAnhang WHERE auditProofsId IN (
            SELECT id FROM STG_QM_AuditProofs WHERE auditPlanId = ?
        )
    """, (plan_id,))
    execute("""
        DELETE FROM STG_QM_AuditLink WHERE auditProofsId IN (
            SELECT id FROM STG_QM_AuditProofs WHERE auditPlanId = ?
        )
    """, (plan_id,))
    execute("DELETE FROM STG_QM_AuditProofs WHERE auditPlanId = ?", (plan_id,))
    execute("DELETE FROM STG_QM_AuditPlan WHERE id = ?", (plan_id,))


def create_audit_plan(data):
    """Legt einen neuen Audit-Plan-Eintrag an und liefert zuverlaessig dessen neue id zurueck.

    Wichtig: die zurueckgelieferte id wird im Aufrufer (routes.py) sofort weiterverwendet, um
    ggf. eine Checkliste (samt Proofs) in genau diesen Plan zu uebernehmen - ist die id falsch
    bzw. None, schlaegt der nachfolgende INSERT in STG_QM_AuditProofs mit einem NOT-NULL-Fehler
    fehl. Fuer SQL Server wird deshalb bewusst die OUTPUT-Klausel statt SCOPE_IDENTITY() (siehe
    _get_last_insert_id) verwendet: OUTPUT INSERTED.id liest die id direkt aus der INSERT-
    Anweisung selbst und ist damit unabhaengig von Sitzungs-/Gueltigkeitsbereichs-Eigenheiten,
    die SCOPE_IDENTITY() in der Praxis (produktive SQL-Server-Umgebung) NULL liefern liessen."""
    params = (
        data.get("auditProgrammId"), data.get("fachbereich"), data.get("auditProzess"),
        data.get("verantwortlich"), data.get("datumAuditEnde"), data.get("datumInterview"),
        data.get("info"), data.get("auditStatus"),
    )
    conn = get_connection()
    try:
        cur = conn.cursor()
        if config.DB_BACKEND == "mssql":
            cur.execute("""
                INSERT INTO STG_QM_AuditPlan
                (auditProgrammId, fachbereich, auditProzess, verantwortlich, datumAuditEnde,
                 datumInterview, info, auditStatus)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, params)
            row = cur.fetchone()
            new_id = row[0] if row else None
        else:
            cur.execute("""
                INSERT INTO STG_QM_AuditPlan
                (auditProgrammId, fachbereich, auditProzess, verantwortlich, datumAuditEnde,
                 datumInterview, info, auditStatus)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, params)
            new_id = cur.lastrowid
        conn.commit()
        return new_id
    finally:
        conn.close()


def update_audit_plan_status(plan_id, status_id):
    execute("UPDATE STG_QM_AuditPlan SET auditStatus=? WHERE id=?", (status_id, plan_id))


def update_audit_plan(plan_id, data):
    execute("""
        UPDATE STG_QM_AuditPlan SET
        auditProgrammId=?, fachbereich=?, auditProzess=?, verantwortlich=?,
        datumAuditEnde=?, datumInterview=?, info=?, auditStatus=?
        WHERE id=?
    """, (
        data.get("auditProgrammId"), data.get("fachbereich"), data.get("auditProzess"),
        data.get("verantwortlich"), data.get("datumAuditEnde"), data.get("datumInterview"),
        data.get("info"), data.get("auditStatus"), plan_id,
    ))


def update_proof(proof_id, data):
    """Aktualisiert einen Proof im Audit-Plan vollstaendig: sowohl die aus der Checklisten-
    Vorlage uebernommene (oder manuell erfasste) Frage/Norm-Kapitel als auch die im Audit-Plan
    angereicherten Felder Punkte/Auditor/Bewertung/Beispiel - unabhaengig vom eigentlichen
    Ergebnis-/Abweichungsworkflow unter 'Audit durchfuehren'."""
    execute("""
        UPDATE STG_QM_AuditProofs SET
        auditFrage=?, normKapitel=?, punkte=?, auditor=?, bewertung=?, beispiel=?
        WHERE id=?
    """, (
        data.get("auditFrage"), data.get("normKapitel"), data.get("punkte"),
        data.get("auditor"), data.get("bewertung"), data.get("beispiel"), proof_id,
    ))


def add_manual_proof_to_plan(plan_id, data):
    """Fuegt einen Proof manuell direkt in einen Audit-Plan-Eintrag ein (nicht aus einer
    Checklisten-Vorlage uebernommen). auditChecklisteID bleibt dabei NULL - so bleibt
    nachvollziehbar, dass dieser Proof nicht aus einer Vorlage stammt."""
    return execute("""
        INSERT INTO STG_QM_AuditProofs
        (auditPlanId, auditChecklisteID, auditFrage, normKapitel, auditResultInfo,
         punkte, auditor, bewertung, beispiel)
        VALUES (?, NULL, ?, ?, '', ?, ?, ?, ?)
    """, (
        plan_id, data.get("auditFrage"), data.get("normKapitel"),
        data.get("punkte"), data.get("auditor"), data.get("bewertung"), data.get("beispiel"),
    ))


def delete_proof(proof_id):
    """Loescht einen einzelnen Proof aus einem Audit-Plan (z.B. um einen versehentlich
    manuell angelegten Proof wieder zu entfernen) inkl. aller davon abhaengigen Ergebnisse,
    Abweichungen, Massnahmen, Interviews, Anhaenge und Links."""
    execute("""
        DELETE FROM STG_QM_StatusMassnahme WHERE auditMassnahmeID IN (
            SELECT m.id FROM STG_QM_AuditMassnahme m
            JOIN STG_QM_AuditAbweichung a ON a.id = m.auditAbweichungID
            JOIN STG_QM_AuditResult r ON r.id = a.auditResultID
            WHERE r.auditProofsId = ?
        )
    """, (proof_id,))
    execute("""
        DELETE FROM STG_QM_AuditMassnahme WHERE auditAbweichungID IN (
            SELECT a.id FROM STG_QM_AuditAbweichung a
            JOIN STG_QM_AuditResult r ON r.id = a.auditResultID
            WHERE r.auditProofsId = ?
        )
    """, (proof_id,))
    execute("""
        DELETE FROM STG_QM_AuditAbweichung WHERE auditResultID IN (
            SELECT id FROM STG_QM_AuditResult WHERE auditProofsId = ?
        )
    """, (proof_id,))
    execute("DELETE FROM STG_QM_AuditResult WHERE auditProofsId = ?", (proof_id,))
    execute("DELETE FROM STG_QM_AuditInterview WHERE auditProofsId = ?", (proof_id,))
    execute("DELETE FROM STG_QM_AuditAnhang WHERE auditProofsId = ?", (proof_id,))
    execute("DELETE FROM STG_QM_AuditLink WHERE auditProofsId = ?", (proof_id,))
    execute("DELETE FROM STG_QM_AuditProofs WHERE id = ?", (proof_id,))


# --------------------------------------------------------------------------
# Checklisten (Vorlagen)
# --------------------------------------------------------------------------

def list_checklisten():
    return query("""
        SELECT c.*, p.processName AS prozessName
        FROM STG_QM_AuditCheckliste c
        LEFT JOIN Look_QM_AuditProzess p ON p.id = c.prozessId
        ORDER BY c.id DESC
    """)


def get_checkliste(checkliste_id):
    return query("SELECT * FROM STG_QM_AuditCheckliste WHERE id = ?", (checkliste_id,), fetchone=True)


def create_checkliste(data):
    return execute("""
        INSERT INTO STG_QM_AuditCheckliste (prozessId, bezeichnung, link, eigner)
        VALUES (?, ?, ?, ?)
    """, (data.get("prozessId"), data.get("bezeichnung"), data.get("link"), data.get("eigner")))


def update_checkliste(checkliste_id, data):
    execute("""
        UPDATE STG_QM_AuditCheckliste SET prozessId=?, bezeichnung=?, link=?, eigner=?
        WHERE id=?
    """, (data.get("prozessId"), data.get("bezeichnung"), data.get("link"), data.get("eigner"), checkliste_id))


def delete_checkliste(checkliste_id):
    execute("DELETE FROM STG_QM_AuditCheckliste WHERE id = ?", (checkliste_id,))


def list_checkliste_proofs(checkliste_id):
    return query("SELECT * FROM STG_QM_AuditChecklisteProofs WHERE auditChecklisteID = ? ORDER BY id",
                 (checkliste_id,))


def add_checkliste_proof(checkliste_id, frage, norm_kapitel, info=""):
    return execute("""
        INSERT INTO STG_QM_AuditChecklisteProofs (auditChecklisteID, auditFrage, normKapitel, auditResultInfo)
        VALUES (?, ?, ?, ?)
    """, (checkliste_id, frage, norm_kapitel, info))


def update_checkliste_proof(proof_id, frage, norm_kapitel, info=""):
    execute("""
        UPDATE STG_QM_AuditChecklisteProofs SET auditFrage=?, normKapitel=?, auditResultInfo=?
        WHERE id=?
    """, (frage, norm_kapitel, info, proof_id))


def delete_checkliste_proof(proof_id):
    execute("DELETE FROM STG_QM_AuditChecklisteProofs WHERE id = ?", (proof_id,))


# --------------------------------------------------------------------------
# Audit durchfuehren: AuditProofs / AuditResult / Interview
# --------------------------------------------------------------------------

def audit_proofs_exist_for_plan(plan_id):
    row = query("SELECT COUNT(*) AS c FROM STG_QM_AuditProofs WHERE auditPlanId = ?", (plan_id,), fetchone=True)
    return row["c"] > 0


def copy_checkliste_to_proofs(plan_id, checkliste_id):
    """Kopiert die Fragen einer Checkliste-Vorlage in STG_QM_AuditProofs fuer einen konkreten Plan
    (1x pro Plan) und speichert die Zuordnung zusaetzlich direkt am Plan-Eintrag
    (STG_QM_AuditPlan.checklisteId) - auch dann, wenn die Checkliste selbst (noch) keine
    Proofs/Pruefpunkte enthaelt. Ohne das direkte Speichern am Plan waere eine Checkliste ohne
    Proofs nach dem Uebernehmen nicht mehr von 'keine Checkliste zugeordnet' zu unterscheiden.

    Rueckgabe: None, wenn diesem Plan bereits eine Checkliste zugeordnet ist (keine Aktion) -
    oder wenn plan_id/checkliste_id fehlen (z.B. weil der Plan-Eintrag nicht angelegt werden
    konnte); sonst die Anzahl der in diesem Aufruf kopierten Proofs (kann 0 sein)."""
    if not plan_id or not checkliste_id:
        return None
    plan = get_audit_plan(plan_id)
    if plan and plan.get("checklisteId"):
        return None
    if audit_proofs_exist_for_plan(plan_id):
        # Altbestand: Proofs existieren schon (z.B. Datenbank vor Einfuehrung von
        # checklisteId), aber die Zuordnung am Plan fehlt noch - nur nachtragen, nichts
        # erneut kopieren.
        execute("UPDATE STG_QM_AuditPlan SET checklisteId=? WHERE id=?", (checkliste_id, plan_id))
        return 0
    proofs = list_checkliste_proofs(checkliste_id)
    for p in proofs:
        execute("""
            INSERT INTO STG_QM_AuditProofs
            (auditPlanId, auditChecklisteID, auditFrage, normKapitel, auditResultInfo)
            VALUES (?, ?, ?, ?, ?)
        """, (plan_id, checkliste_id, p["auditFrage"], p["normKapitel"], p["auditResultInfo"]))
    execute("UPDATE STG_QM_AuditPlan SET checklisteId=? WHERE id=?", (checkliste_id, plan_id))
    return len(proofs)


def list_proofs_for_plan(plan_id):
    # Hinweis: "neuestes Ergebnis je Proof" wird portabel (SQLite + SQL Server) ueber
    # eine Korrelation auf die hoechste id ermittelt statt ueber ORDER BY ... LIMIT 1
    # (LIMIT ist T-SQL unbekannt, dort waere TOP noetig).
    return query("""
        SELECT pf.*,
               (SELECT r.auditBewertungID FROM STG_QM_AuditResult r
                    WHERE r.auditProofsId = pf.id
                      AND r.id = (SELECT MAX(r2.id) FROM STG_QM_AuditResult r2 WHERE r2.auditProofsId = pf.id)
               ) AS letzteBewertungId,
               (SELECT b.auditResult FROM STG_QM_AuditResult r
                    LEFT JOIN Look_QM_AuditBewertung b ON b.id = r.auditBewertungID
                    WHERE r.auditProofsId = pf.id
                      AND r.id = (SELECT MAX(r2.id) FROM STG_QM_AuditResult r2 WHERE r2.auditProofsId = pf.id)
               ) AS letzteBewertung
        FROM STG_QM_AuditProofs pf
        WHERE pf.auditPlanId = ?
        ORDER BY pf.id
    """, (plan_id,))


def get_proof(proof_id):
    return query("SELECT * FROM STG_QM_AuditProofs WHERE id = ?", (proof_id,), fetchone=True)


def list_results_for_proof(proof_id):
    return query("""
        SELECT r.*, b.auditResult AS bewertungName
        FROM STG_QM_AuditResult r
        LEFT JOIN Look_QM_AuditBewertung b ON b.id = r.auditBewertungID
        WHERE r.auditProofsId = ? ORDER BY r.id DESC
    """, (proof_id,))


def add_audit_result(proof_id, name_auditor, bewertung_id, datum, antwort, info=""):
    return execute("""
        INSERT INTO STG_QM_AuditResult
        (auditProofsId, nameAuditor, auditBewertungID, datumerfasst, antwort, auditResultInfo)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (proof_id, name_auditor, bewertung_id, datum, antwort, info))


def add_anhang(proof_id, checkliste_id, anhang):
    return execute("INSERT INTO STG_QM_AuditAnhang (auditProofsId, auditChecklisteID, anhang) VALUES (?, ?, ?)",
                   (proof_id, checkliste_id, anhang))


def add_link(proof_id, checkliste_id, link):
    return execute("INSERT INTO STG_QM_AuditLink (auditProofsId, auditChecklisteID, link) VALUES (?, ?, ?)",
                   (proof_id, checkliste_id, link))


def list_anhaenge(proof_id):
    return query("SELECT * FROM STG_QM_AuditAnhang WHERE auditProofsId = ? ORDER BY id", (proof_id,))


def list_links(proof_id):
    return query("SELECT * FROM STG_QM_AuditLink WHERE auditProofsId = ? ORDER BY id", (proof_id,))


def add_interview(proof_id, name_auditor, inhalt):
    return execute("INSERT INTO STG_QM_AuditInterview (auditProofsId, nameAuditor, inhalt) VALUES (?, ?, ?)",
                   (proof_id, name_auditor, inhalt))


def list_interviews_for_plan(plan_id):
    return query("""
        SELECT iv.*, pf.auditFrage, pf.normKapitel
        FROM STG_QM_AuditInterview iv
        JOIN STG_QM_AuditProofs pf ON pf.id = iv.auditProofsId
        WHERE pf.auditPlanId = ?
        ORDER BY iv.id DESC
    """, (plan_id,))


def list_all_interviews():
    return query("""
        SELECT iv.*, pf.auditFrage, pl.id AS planId, prog.id AS programmId, prog.auditJahr
        FROM STG_QM_AuditInterview iv
        JOIN STG_QM_AuditProofs pf ON pf.id = iv.auditProofsId
        JOIN STG_QM_AuditPlan pl ON pl.id = pf.auditPlanId
        JOIN STG_QM_AuditProgramm prog ON prog.id = pl.auditProgrammId
        ORDER BY iv.id DESC
    """)


# --------------------------------------------------------------------------
# Abweichungen / Massnahmen / StatusMassnahme
# --------------------------------------------------------------------------

def add_abweichung(result_id, abweichung, status_id, name_auditor, datum, name_eigner):
    return execute("""
        INSERT INTO STG_QM_AuditAbweichung
        (auditResultID, abweichung, abweichungStatus, nameAuditor, datumErfasst, nameEigner)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (result_id, abweichung, status_id, name_auditor, datum, name_eigner))


def list_abweichungen(status_filter=None):
    sql = """
        SELECT a.*, s.auditStatus AS statusName,
               r.antwort AS ergebnisAntwort, pf.auditFrage, pf.normKapitel,
               pl.id AS planId, prog.id AS programmId, prog.auditJahr, prog.unternehmen
        FROM STG_QM_AuditAbweichung a
        LEFT JOIN Look_QM_AuditStatus s ON s.id = a.abweichungStatus
        LEFT JOIN STG_QM_AuditResult r ON r.id = a.auditResultID
        LEFT JOIN STG_QM_AuditProofs pf ON pf.id = r.auditProofsId
        LEFT JOIN STG_QM_AuditPlan pl ON pl.id = pf.auditPlanId
        LEFT JOIN STG_QM_AuditProgramm prog ON prog.id = pl.auditProgrammId
    """
    params = ()
    if status_filter:
        sql += " WHERE a.abweichungStatus = ?"
        params = (status_filter,)
    sql += " ORDER BY a.id DESC"
    return query(sql, params)


def get_abweichung(abweichung_id):
    return query("SELECT * FROM STG_QM_AuditAbweichung WHERE id = ?", (abweichung_id,), fetchone=True)


def add_massnahme(abweichung_id, massnahme, datum, name_eigner):
    m_id = execute("""
        INSERT INTO STG_QM_AuditMassnahme (auditAbweichungID, massnahme, datumMassnahme, nameEigner)
        VALUES (?, ?, ?, ?)
    """, (abweichung_id, massnahme, datum, name_eigner))
    # Initialer Status-Eintrag "Erfasst" (id 1)
    execute("""
        INSERT INTO STG_QM_StatusMassnahme (auditMassnahmeID, statusDatum, status, statusNeu, statusName, infoStatus)
        VALUES (?, ?, NULL, 1, ?, 'Massnahme erfasst')
    """, (m_id, datum, name_eigner))
    return m_id


def list_massnahmen(status_filter=None):
    rows = query("""
        SELECT m.*, a.abweichung, a.id AS abweichungId
        FROM STG_QM_AuditMassnahme m
        LEFT JOIN STG_QM_AuditAbweichung a ON a.id = m.auditAbweichungID
        ORDER BY m.id DESC
    """)
    for m in rows:
        last = query("""
            SELECT sm.*, s.auditStatus AS statusNeuName
            FROM STG_QM_StatusMassnahme sm
            LEFT JOIN Look_QM_AuditStatus s ON s.id = sm.statusNeu
            WHERE sm.auditMassnahmeID = ? ORDER BY sm.id DESC
        """, (m["id"],), fetchone=True)
        m["aktuellerStatusId"] = last["statusNeu"] if last else 1
        m["aktuellerStatusName"] = last["statusNeuName"] if last else "Erfasst"
    if status_filter:
        rows = [r for r in rows if str(r["aktuellerStatusId"]) == str(status_filter)]
    return rows


def get_massnahme(massnahme_id):
    return query("SELECT * FROM STG_QM_AuditMassnahme WHERE id = ?", (massnahme_id,), fetchone=True)


def list_status_massnahme(massnahme_id):
    return query("""
        SELECT sm.*, s1.auditStatus AS statusAltName, s2.auditStatus AS statusNeuName
        FROM STG_QM_StatusMassnahme sm
        LEFT JOIN Look_QM_AuditStatus s1 ON s1.id = sm.status
        LEFT JOIN Look_QM_AuditStatus s2 ON s2.id = sm.statusNeu
        WHERE sm.auditMassnahmeID = ? ORDER BY sm.id
    """, (massnahme_id,))


def add_status_massnahme(massnahme_id, status_alt, status_neu, datum, name, info):
    return execute("""
        INSERT INTO STG_QM_StatusMassnahme (auditMassnahmeID, statusDatum, status, statusNeu, statusName, infoStatus)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (massnahme_id, datum, status_alt, status_neu, name, info))


# --------------------------------------------------------------------------
# Konfiguration: Lookup CRUD
# --------------------------------------------------------------------------

def add_lookup_row(table, fields: dict):
    cols = ", ".join(fields.keys())
    placeholders = ", ".join(["?"] * len(fields))
    return execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", tuple(fields.values()))


def update_lookup_row(table, row_id, fields: dict):
    set_clause = ", ".join([f"{k}=?" for k in fields.keys()])
    execute(f"UPDATE {table} SET {set_clause} WHERE id=?", tuple(fields.values()) + (row_id,))


def delete_lookup_row(table, row_id):
    execute(f"DELETE FROM {table} WHERE id=?", (row_id,))


# --------------------------------------------------------------------------
# Mitarbeiter (manuell gepflegt und/oder per AD/LDAP-Sync befuellt)
# --------------------------------------------------------------------------

def list_mitarbeiter(nur_aktive=True):
    if nur_aktive:
        return query("SELECT * FROM Look_QM_Mitarbeiter WHERE aktiv = 1 ORDER BY name")
    return query("SELECT * FROM Look_QM_Mitarbeiter ORDER BY name")


def upsert_mitarbeiter_from_ad(username, name, email, abteilung, sync_zeitpunkt):
    """Legt einen per AD/LDAP gefundenen Mitarbeiter an oder aktualisiert ihn (Abgleich ueber username).
    Manuell angelegte Eintraege ohne username bleiben davon unberuehrt."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM Look_QM_Mitarbeiter WHERE username = ?", (username,))
        row = cur.fetchone()
        if row:
            cur.execute(
                """UPDATE Look_QM_Mitarbeiter
                   SET name=?, email=?, abteilung=?, quelle='AD', aktiv=1, letzterSync=?
                   WHERE id=?""",
                (name, email, abteilung, sync_zeitpunkt, row[0]),
            )
            action = "updated"
        else:
            cur.execute(
                """INSERT INTO Look_QM_Mitarbeiter (name, username, email, abteilung, quelle, aktiv, letzterSync)
                   VALUES (?, ?, ?, ?, 'AD', 1, ?)""",
                (name, username, email, abteilung, sync_zeitpunkt),
            )
            action = "inserted"
        conn.commit()
        return action
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Users (Nutzerverwaltung)
# --------------------------------------------------------------------------

def list_users():
    return query("SELECT id, username, rolle, aktiv FROM users ORDER BY id")


def get_user_by_username(username):
    return query("SELECT * FROM users WHERE username = ?", (username,), fetchone=True)


def create_user(username, password_hash, rolle):
    return execute("INSERT INTO users (username, password_hash, rolle, aktiv) VALUES (?, ?, ?, 1)",
                   (username, password_hash, rolle))


def update_user(user_id, rolle, aktiv, password_hash=None):
    if password_hash:
        execute("UPDATE users SET rolle=?, aktiv=?, password_hash=? WHERE id=?",
                (rolle, aktiv, password_hash, user_id))
    else:
        execute("UPDATE users SET rolle=?, aktiv=? WHERE id=?", (rolle, aktiv, user_id))
