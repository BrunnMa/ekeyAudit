"""
kpi.py - Kennzahlen-Berechnung fuer das ekeyAudit Dashboard.
"""

import database as db


def audits_je_status():
    """Anzahl AuditProgramme je Status (fuer Dashboard-Kacheln/Balken)."""
    rows = db.query("""
        SELECT s.auditStatus AS statusName, COUNT(p.id) AS anzahl
        FROM Look_QM_AuditStatus s
        LEFT JOIN STG_QM_AuditProgramm p ON p.auditStatus = s.id
        GROUP BY s.id, s.auditStatus
        ORDER BY s.id
    """)
    return rows


def offene_abweichungen_gesamt():
    """Anzahl Abweichungen, deren Status nicht 'Fertig' (4) oder 'Wirksam' (5) ist."""
    row = db.query("""
        SELECT COUNT(*) AS c FROM STG_QM_AuditAbweichung
        WHERE abweichungStatus IS NULL OR abweichungStatus NOT IN (4, 5)
    """, fetchone=True)
    return row["c"] if row else 0


def offene_massnahmen_nach_status():
    """Offene Massnahmen (aktueller Status ungleich 'Fertig'/'Wirksam') gruppiert nach Status."""
    massnahmen = db.list_massnahmen()
    result = {}
    for m in massnahmen:
        if m["aktuellerStatusId"] not in (4, 5):
            name = m["aktuellerStatusName"] or "Erfasst"
            result[name] = result.get(name, 0) + 1
    return result


def abweichungsquote_je_prozess():
    """
    Abweichungsquote je Prozess: Anteil der Proofs mit Bewertung 'Abweichung' (3)
    an allen bewerteten Proofs, gruppiert nach Prozess (ueber AuditPlan.auditProzess).
    """
    rows = db.query("""
        SELECT pr.processName AS prozessName,
               COUNT(DISTINCT CASE WHEN r.auditBewertungID = 3 THEN pf.id END) AS abweichungen,
               COUNT(DISTINCT CASE WHEN r.auditBewertungID IS NOT NULL THEN pf.id END) AS bewertet
        FROM STG_QM_AuditPlan pl
        LEFT JOIN Look_QM_AuditProzess pr ON pr.id = pl.auditProzess
        LEFT JOIN STG_QM_AuditProofs pf ON pf.auditPlanId = pl.id
        LEFT JOIN STG_QM_AuditResult r ON r.auditProofsId = pf.id
        GROUP BY pr.id, pr.processName
        HAVING bewertet > 0
        ORDER BY prozessName
    """)
    result = []
    for r in rows:
        quote = round((r["abweichungen"] / r["bewertet"]) * 100, 1) if r["bewertet"] else 0.0
        result.append({
            "prozess": r["prozessName"] or "(ohne Prozess)",
            "abweichungen": r["abweichungen"],
            "bewertet": r["bewertet"],
            "quote": quote,
        })
    return result


def anzahl_audit_plaene():
    row = db.query("SELECT COUNT(*) AS c FROM STG_QM_AuditPlan", fetchone=True)
    return row["c"] if row else 0


def anzahl_audit_programme():
    row = db.query("SELECT COUNT(*) AS c FROM STG_QM_AuditProgramm", fetchone=True)
    return row["c"] if row else 0


def get_dashboard_kpis():
    return {
        "audits_je_status": audits_je_status(),
        "offene_abweichungen": offene_abweichungen_gesamt(),
        "offene_massnahmen_je_status": offene_massnahmen_nach_status(),
        "abweichungsquote_je_prozess": abweichungsquote_je_prozess(),
        "anzahl_programme": anzahl_audit_programme(),
        "anzahl_plaene": anzahl_audit_plaene(),
    }
