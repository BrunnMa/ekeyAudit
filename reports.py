"""
reports.py - PDF-Berichtserstellung aus Auditdaten fuer ekeyAudit.

Nutzt reportlab, um aus einem AuditProgramm (inkl. Ziele, Plaenen,
Proofs, Ergebnissen, Abweichungen und Massnahmen) einen PDF-Bericht
zu erzeugen.
"""

import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)

import config
import database as db

PRIMARY_COLOR = colors.HexColor("#04457A")  # ekey-Blau (aus dem ekey-Logo), ersetzt vormaliges Violett
BORDER_COLOR = colors.HexColor("#BBBBBB")
HEADER_BG = colors.HexColor("#EFF3F6")
ROW_ALT = colors.HexColor("#F9FAFC")


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="EkeyTitle", fontSize=16, textColor=PRIMARY_COLOR,
                               spaceAfter=10, fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle(name="EkeyHeading", fontSize=12, textColor=PRIMARY_COLOR,
                               spaceBefore=12, spaceAfter=6, fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle(name="EkeyNormal", fontSize=9, textColor=colors.HexColor("#333333")))
    styles.add(ParagraphStyle(name="EkeySmall", fontSize=8, textColor=colors.HexColor("#666666")))
    return styles


def _std_table(data, col_widths=None):
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), PRIMARY_COLOR),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_ALT]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def generate_audit_report_pdf(programm_id):
    """Erzeugt einen PDF-Bericht fuer ein AuditProgramm und gibt den Dateipfad zurueck."""
    programm = db.get_audit_programm(programm_id)
    if not programm:
        raise ValueError(f"AuditProgramm {programm_id} nicht gefunden.")

    ziele = db.list_audit_ziele(programm_id)
    plaene = db.list_audit_plaene(programm_id)

    filename = f"Audit_Bericht_{programm_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(config.REPORT_DIR, filename)

    doc = SimpleDocTemplate(filepath, pagesize=A4,
                             topMargin=15 * mm, bottomMargin=15 * mm,
                             leftMargin=15 * mm, rightMargin=15 * mm)
    styles = _styles()
    story = []

    story.append(Paragraph("ekeyAudit - Auditbericht (ISO 9001)", styles["EkeyTitle"]))
    story.append(Paragraph(f"Erstellt am: {datetime.now().strftime('%d.%m.%Y %H:%M')}", styles["EkeySmall"]))
    story.append(Spacer(1, 8))

    # Programmdaten
    story.append(Paragraph("Auditprogramm", styles["EkeyHeading"]))
    prog_data = [
        ["Feld", "Wert"],
        ["Audit-Typ", programm.get("auditTyp") or ""],
        ["Jahr", str(programm.get("auditJahr") or "")],
        ["Norm", programm.get("norm") or ""],
        ["Auditor", programm.get("auditor") or ""],
        ["Unternehmen", programm.get("unternehmen") or ""],
        ["Standort", programm.get("standort") or ""],
        ["Start", programm.get("startDatum") or ""],
        ["Ende", programm.get("endDatum") or ""],
        ["Beauftragt durch", programm.get("beauftragt") or ""],
        ["Beauftragt am", programm.get("beauftragtAm") or ""],
    ]
    story.append(_std_table(prog_data, col_widths=[45 * mm, 120 * mm]))
    story.append(Spacer(1, 10))

    # Ziele
    story.append(Paragraph("Auditziele", styles["EkeyHeading"]))
    if ziele:
        ziel_data = [["#", "Ziel"]] + [[str(i + 1), z["auditZiel"] or ""] for i, z in enumerate(ziele)]
        story.append(_std_table(ziel_data, col_widths=[15 * mm, 150 * mm]))
    else:
        story.append(Paragraph("Keine Auditziele erfasst.", styles["EkeyNormal"]))
    story.append(Spacer(1, 10))

    # Plaene + Proofs + Ergebnisse + Abweichungen + Massnahmen
    story.append(Paragraph("Auditplaene", styles["EkeyHeading"]))
    if not plaene:
        story.append(Paragraph("Keine Audit-Plaene erfasst.", styles["EkeyNormal"]))
    for plan in plaene:
        story.append(Paragraph(
            f"Plan #{plan['id']} - Fachbereich: {plan.get('fachbereich') or ''} - "
            f"Prozess: {plan.get('prozessName') or ''} - Verantwortlich: {plan.get('verantwortlich') or ''} - "
            f"Status: {plan.get('statusName') or ''}",
            styles["EkeyNormal"]
        ))
        proofs = db.list_proofs_for_plan(plan["id"])
        if proofs:
            proof_rows = [["Frage", "Norm-Kap.", "Bewertung"]]
            for pf in proofs:
                proof_rows.append([
                    (pf.get("auditFrage") or "")[:120],
                    pf.get("normKapitel") or "",
                    pf.get("letzteBewertung") or "-",
                ])
            story.append(_std_table(proof_rows, col_widths=[110 * mm, 30 * mm, 30 * mm]))
        else:
            story.append(Paragraph("Keine Proofs zu diesem Plan.", styles["EkeySmall"]))
        story.append(Spacer(1, 6))

    # Abweichungen des Programms
    story.append(Paragraph("Abweichungen und Massnahmen", styles["EkeyHeading"]))
    alle_abweichungen = [a for a in db.list_abweichungen() if a.get("programmId") == programm_id]
    if alle_abweichungen:
        for ab in alle_abweichungen:
            story.append(Paragraph(
                f"Abweichung #{ab['id']}: {ab.get('abweichung') or ''} (Status: {ab.get('statusName') or ''}, "
                f"Eigner: {ab.get('nameEigner') or ''})",
                styles["EkeyNormal"]
            ))
            massnahmen = db.query(
                "SELECT * FROM STG_QM_AuditMassnahme WHERE auditAbweichungID = ?", (ab["id"],)
            )
            if massnahmen:
                m_rows = [["Massnahme", "Termin", "Eigner"]]
                for m in massnahmen:
                    m_rows.append([m.get("massnahme") or "", m.get("datumMassnahme") or "", m.get("nameEigner") or ""])
                story.append(_std_table(m_rows, col_widths=[100 * mm, 30 * mm, 40 * mm]))
            story.append(Spacer(1, 4))
    else:
        story.append(Paragraph("Keine Abweichungen erfasst.", styles["EkeyNormal"]))

    doc.build(story)
    return filepath
