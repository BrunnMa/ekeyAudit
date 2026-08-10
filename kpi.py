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


def massnahmen_nach_status():
    """Anzahl Massnahmen je Status (Look_QM_MassnahmenStatus: offen/geplant/fertig/wirksam,
    siehe STG_QM_AuditMassnahme.statusMassnahmeID) - fuer Dashboard und AuditHome."""
    return db.query("""
        SELECT s.statusName AS statusName, COUNT(m.id) AS anzahl
        FROM Look_QM_MassnahmenStatus s
        LEFT JOIN STG_QM_AuditMassnahme m ON m.statusMassnahmeID = s.id
        GROUP BY s.id, s.statusName
        ORDER BY s.id
    """)


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
        HAVING COUNT(DISTINCT CASE WHEN r.auditBewertungID IS NOT NULL THEN pf.id END) > 0
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


def offene_audit_programme_gesamt():
    """Anzahl AuditProgramme, deren Status nicht 'Fertig' (4) oder 'Wirksam' (5) ist."""
    row = db.query("""
        SELECT COUNT(*) AS c FROM STG_QM_AuditProgramm
        WHERE auditStatus IS NULL OR auditStatus NOT IN (4, 5)
    """, fetchone=True)
    return row["c"] if row else 0


def anzahl_abweichungen_gesamt():
    row = db.query("SELECT COUNT(*) AS c FROM STG_QM_AuditAbweichung", fetchone=True)
    return row["c"] if row else 0


def anzahl_auditproofs_gesamt():
    row = db.query("SELECT COUNT(*) AS c FROM STG_QM_AuditProofs", fetchone=True)
    return row["c"] if row else 0


def mittelwert_punkte():
    """Mittelwert Punkte = Summe aller erfassten Punktbewertungen (STG_QM_AuditResult.punkte,
    Skala 1-4) / Anzahl aller Punktbewertungen - Kennzahl 'AuditProofs' auf der Startseite."""
    row = db.query(
        "SELECT SUM(punkte) AS summe, COUNT(punkte) AS anzahl FROM STG_QM_AuditResult WHERE punkte IS NOT NULL",
        fetchone=True
    )
    if not row or not row["anzahl"]:
        return 0.0
    return row["summe"] / row["anzahl"]


def erfuellungsgrad():
    """Erfuellungsgrad in Prozent = 100 * Mittelwert Punkte / 4 (Punkteskala 1-4)."""
    return round(100 * mittelwert_punkte() / 4, 1)


def anzahl_massnahmen_gesamt():
    row = db.query("SELECT COUNT(*) AS c FROM STG_QM_AuditMassnahme", fetchone=True)
    return row["c"] if row else 0


def anzahl_massnahmen_nach_status(status_id):
    """Anzahl Massnahmen mit einem bestimmten Status (Look_QM_MassnahmenStatus:
    1=offen, 2=geplant, 3=fertig, 4=wirksam)."""
    row = db.query(
        "SELECT COUNT(*) AS c FROM STG_QM_AuditMassnahme WHERE statusMassnahmeID = ?",
        (status_id,), fetchone=True
    )
    return row["c"] if row else 0


def erfuellungsgrad_massnahmen():
    """Erfuellungsgrad Massnahmen in Prozent: Anteil der Massnahmen mit Status 'wirksam' (4,
    siehe Look_QM_MassnahmenStatus) an allen erfassten Massnahmen - Kennzahl auf der Seite
    'Auditabweichungen'."""
    gesamt = anzahl_massnahmen_gesamt()
    if not gesamt:
        return 0.0
    wirksam = anzahl_massnahmen_nach_status(4)
    return round(100 * wirksam / gesamt, 1)


def audithome_kpis():
    """Kennzahlen fuer die Startseite AuditHome (Auditprogramme / AuditProofs /
    Auditabweichungen / Massnahmen)."""
    return {
        "programme_gesamt": anzahl_audit_programme(),
        "programme_offen": offene_audit_programme_gesamt(),
        "proofs_gesamt": anzahl_auditproofs_gesamt(),
        "mittelwert_punkte": round(mittelwert_punkte(), 2),
        "erfuellungsgrad": erfuellungsgrad(),
        "abweichungen_gesamt": anzahl_abweichungen_gesamt(),
        "abweichungen_offen": offene_abweichungen_gesamt(),
        "massnahmen_gesamt": anzahl_massnahmen_gesamt(),
        "massnahmen_offen": anzahl_massnahmen_nach_status(1),
        "massnahmen_geplant": anzahl_massnahmen_nach_status(2),
        "massnahmen_fertig": anzahl_massnahmen_nach_status(3),
        "massnahmen_wirksam": anzahl_massnahmen_nach_status(4),
    }


def audit_programme_je_status_gruppe():
    """Auditprogramme gruppiert in 3 Buckets (fuer die Dashboard-Hauptkachel 'Auditprogramme'):
    offen (Erfasst/Geplant, Status 1/2), in Arbeit (Status 3), fertig (Fertig/Wirksam, 4/5)."""
    row = db.query("""
        SELECT
            SUM(CASE WHEN auditStatus IS NULL OR auditStatus IN (1, 2) THEN 1 ELSE 0 END) AS offen,
            SUM(CASE WHEN auditStatus = 3 THEN 1 ELSE 0 END) AS in_arbeit,
            SUM(CASE WHEN auditStatus IN (4, 5) THEN 1 ELSE 0 END) AS fertig
        FROM STG_QM_AuditProgramm
    """, fetchone=True)
    if not row:
        return {"offen": 0, "in_arbeit": 0, "fertig": 0}
    return {
        "offen": row["offen"] or 0,
        "in_arbeit": row["in_arbeit"] or 0,
        "fertig": row["fertig"] or 0,
    }


def abweichungen_je_status_gruppe():
    """Abweichungen gruppiert in 3 Buckets (Dashboard 'Ergebnisse'): offen (Erfasst/Geplant,
    Status 1/2), in Arbeit (Status 3), erledigt (Fertig/Wirksam, 4/5)."""
    row = db.query("""
        SELECT
            SUM(CASE WHEN abweichungStatus IS NULL OR abweichungStatus IN (1, 2) THEN 1 ELSE 0 END) AS offen,
            SUM(CASE WHEN abweichungStatus = 3 THEN 1 ELSE 0 END) AS in_arbeit,
            SUM(CASE WHEN abweichungStatus IN (4, 5) THEN 1 ELSE 0 END) AS erledigt
        FROM STG_QM_AuditAbweichung
    """, fetchone=True)
    if not row:
        return {"offen": 0, "in_arbeit": 0, "erledigt": 0}
    return {
        "offen": row["offen"] or 0,
        "in_arbeit": row["in_arbeit"] or 0,
        "erledigt": row["erledigt"] or 0,
    }


def massnahmen_je_status_gruppe():
    """Massnahmen gruppiert in 3 Buckets (Dashboard 'Ergebnisse'): offen (Look_QM_MassnahmenStatus
    'offen', id 1), in Arbeit ('geplant', id 2), erledigt ('fertig'/'wirksam', id 3/4)."""
    row = db.query("""
        SELECT
            SUM(CASE WHEN statusMassnahmeID = 1 THEN 1 ELSE 0 END) AS offen,
            SUM(CASE WHEN statusMassnahmeID = 2 THEN 1 ELSE 0 END) AS in_arbeit,
            SUM(CASE WHEN statusMassnahmeID IN (3, 4) THEN 1 ELSE 0 END) AS erledigt
        FROM STG_QM_AuditMassnahme
    """, fetchone=True)
    if not row:
        return {"offen": 0, "in_arbeit": 0, "erledigt": 0}
    return {
        "offen": row["offen"] or 0,
        "in_arbeit": row["in_arbeit"] or 0,
        "erledigt": row["erledigt"] or 0,
    }


def auditproofs_kennzahlen():
    """AuditProofs-Aufschluesselung fuer die Dashboard-Hauptkachel 'AuditProofs': offen (noch
    kein Ergebnis erfasst), Punkte 0 (Ergebnis erfasst, aber noch nicht bewertet - punkte NULL),
    Punkte 1-4 (Anzahl je Punktwert) und erledigt (Summe Punkte 1-4, d.h. bewertet)."""
    row = db.query("""
        SELECT
            SUM(CASE WHEN r.id IS NULL THEN 1 ELSE 0 END) AS offen,
            SUM(CASE WHEN r.id IS NOT NULL AND r.punkte IS NULL THEN 1 ELSE 0 END) AS punkte_0,
            SUM(CASE WHEN r.punkte = 1 THEN 1 ELSE 0 END) AS punkte_1,
            SUM(CASE WHEN r.punkte = 2 THEN 1 ELSE 0 END) AS punkte_2,
            SUM(CASE WHEN r.punkte = 3 THEN 1 ELSE 0 END) AS punkte_3,
            SUM(CASE WHEN r.punkte = 4 THEN 1 ELSE 0 END) AS punkte_4,
            SUM(CASE WHEN r.punkte IS NOT NULL THEN 1 ELSE 0 END) AS erledigt
        FROM STG_QM_AuditProofs pf
        LEFT JOIN STG_QM_AuditResult r ON r.auditProofsId = pf.id
    """, fetchone=True)
    if not row:
        return {"offen": 0, "punkte_0": 0, "punkte_1": 0, "punkte_2": 0, "punkte_3": 0, "punkte_4": 0, "erledigt": 0}
    return {
        "offen": row["offen"] or 0,
        "punkte_0": row["punkte_0"] or 0,
        "punkte_1": row["punkte_1"] or 0,
        "punkte_2": row["punkte_2"] or 0,
        "punkte_3": row["punkte_3"] or 0,
        "punkte_4": row["punkte_4"] or 0,
        "erledigt": row["erledigt"] or 0,
    }


INTERNE_AUDIT_TYPEN = ("internes Audit", "automatisiertes internes Audit")


def erfuellungsgrad_nach_audittyp(intern):
    """Erfuellungsgrad (siehe erfuellungsgrad()) eingeschraenkt auf interne bzw. externe
    Audits (STG_QM_AuditProgramm.auditTyp: 'internes Audit'/'automatisiertes internes Audit'
    gelten als intern, alle anderen belegten Typen als extern)."""
    if intern:
        bedingung = "prog.auditTyp IN (?, ?)"
        params = list(INTERNE_AUDIT_TYPEN)
    else:
        bedingung = "prog.auditTyp IS NOT NULL AND prog.auditTyp NOT IN (?, ?)"
        params = list(INTERNE_AUDIT_TYPEN)
    row = db.query(f"""
        SELECT SUM(r.punkte) AS summe, COUNT(r.punkte) AS anzahl
        FROM STG_QM_AuditResult r
        JOIN STG_QM_AuditProofs pf ON pf.id = r.auditProofsId
        JOIN STG_QM_AuditPlan pl ON pl.id = pf.auditPlanId
        JOIN STG_QM_AuditProgramm prog ON prog.id = pl.auditProgrammId
        WHERE r.punkte IS NOT NULL AND {bedingung}
    """, tuple(params), fetchone=True)
    if not row or not row["anzahl"]:
        return 0.0
    mittelwert = row["summe"] / row["anzahl"]
    return round(100 * mittelwert / 4, 1)


def proofs_pro_audit():
    """Mittelwert: Anzahl AuditProofs je Auditprogramm."""
    programme = anzahl_audit_programme()
    if not programme:
        return 0.0
    return round(anzahl_auditproofs_gesamt() / programme, 1)


def proofs_pro_plan():
    """Mittelwert: Anzahl AuditProofs je Audit-Plan-Eintrag."""
    plaene = anzahl_audit_plaene()
    if not plaene:
        return 0.0
    return round(anzahl_auditproofs_gesamt() / plaene, 1)


def massnahmen_pro_programm():
    """Mittelwert: Anzahl Massnahmen je Auditprogramm."""
    programme = anzahl_audit_programme()
    if not programme:
        return 0.0
    return round(anzahl_massnahmen_gesamt() / programme, 1)


def get_dashboard_kpis():
    """Kennzahlen fuer die Seite 'Dashboard/KPIs' - enthaelt zusaetzlich dieselben Kennzahlen
    wie die Startseite AuditHome (siehe audithome_kpis), damit beide Seiten konsistent sind.
    Hinweis: audits_je_status()/massnahmen_nach_status()/abweichungsquote_je_prozess() werden
    hier bewusst NICHT mehr eingebunden, da die zugehoerigen Listen-Panels unterhalb der
    KPI-Kacheln entfernt wurden - die Funktionen selbst bleiben fuer eine etwaige spaetere
    Verwendung erhalten."""
    data = {
        "offene_abweichungen": offene_abweichungen_gesamt(),
        "anzahl_programme": anzahl_audit_programme(),
        "anzahl_plaene": anzahl_audit_plaene(),
        "programme_gruppe": audit_programme_je_status_gruppe(),
        "proofs_kennzahlen": auditproofs_kennzahlen(),
        "abweichungen_gruppe": abweichungen_je_status_gruppe(),
        "massnahmen_gruppe": massnahmen_je_status_gruppe(),
        "erfuellungsgrad_intern": erfuellungsgrad_nach_audittyp(intern=True),
        "erfuellungsgrad_extern": erfuellungsgrad_nach_audittyp(intern=False),
        "proofs_pro_audit": proofs_pro_audit(),
        "proofs_pro_plan": proofs_pro_plan(),
        "massnahmen_pro_programm": massnahmen_pro_programm(),
    }
    data.update(audithome_kpis())
    return data
