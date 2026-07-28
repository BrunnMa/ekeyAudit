"""
gui/routes.py - Alle Flask-Routen der ekeyAudit-Anwendung (ein Blueprint 'gui').
"""

import itertools
import os
import threading
import time
from datetime import datetime

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    session, send_file, abort
)

import database as db
import security
import kpi
import reports
import com

gui = Blueprint("gui", __name__, template_folder="templates", static_folder="static")


# --------------------------------------------------------------------------
# Login / Logout
# --------------------------------------------------------------------------

@gui.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if security.login_user(username, password):
            flash("Erfolgreich angemeldet.", "success")
            next_url = request.args.get("next") or url_for("gui.index")
            return redirect(next_url)
        flash("Benutzername oder Passwort falsch.", "error")
    return render_template("login.html")


@gui.route("/logout")
def logout():
    security.logout_user()
    flash("Abgemeldet.", "success")
    return redirect(url_for("gui.login"))


# --------------------------------------------------------------------------
# Startseite / Dashboard
# --------------------------------------------------------------------------

@gui.route("/")
@security.login_required
def index():
    return render_template(
        "index.html",
        user=security.current_user(),
        kpis=kpi.audithome_kpis(),
        programme=db.list_audit_programme(),
    )


@gui.route("/dashboard")
@security.login_required
def dashboard():
    data = kpi.get_dashboard_kpis()
    status_lookup = db.get_lookup("Look_QM_AuditStatus")
    return render_template("dashboard.html", kpis=data, status_lookup=status_lookup)


# --------------------------------------------------------------------------
# Audit programm
# --------------------------------------------------------------------------

@gui.route("/audit-programm", methods=["GET", "POST"])
@security.login_required
def audit_programm():
    if request.method == "POST":
        auditoren = [a.strip() for a in request.form.getlist("auditor_liste") if a.strip()]
        data = {
            "auditTyp": request.form.get("auditTyp"),
            "auditJahr": request.form.get("auditJahr") or None,
            "norm": request.form.get("norm"),
            "auditor": "; ".join(auditoren),
            "auditStatus": request.form.get("auditStatus") or 1,
            "unternehmen": request.form.get("unternehmen"),
            "standort": request.form.get("standort"),
            "startDatum": request.form.get("startDatum"),
            "endDatum": request.form.get("endDatum"),
            "beauftragt": request.form.get("beauftragt"),
            "beauftragtAm": request.form.get("beauftragtAm"),
            "beauftragtInfo": request.form.get("beauftragtInfo"),
        }
        programm_id = request.form.get("programm_id")
        if programm_id:
            db.update_audit_programm(programm_id, data)
            flash("Auditprogramm aktualisiert.", "success")
        else:
            db.create_audit_programm(data)
            flash("Auditprogramm angelegt.", "success")
        return redirect(url_for("gui.audit_programm"))

    programme = db.list_audit_programme()
    edit_id = request.args.get("edit")
    edit_programm = db.get_audit_programm(edit_id) if edit_id else None
    ziele_open_id = request.args.get("ziele")
    ziele_by_programm = {p["id"]: db.list_audit_ziele(p["id"]) for p in programme}

    return render_template(
        "audit_programm.html",
        programme=programme,
        audit_typen=db.get_lookup("Look_QM_AuditTyp"),
        audit_status=db.get_lookup("Look_QM_AuditStatus"),
        mitarbeiter=db.list_mitarbeiter(),
        edit_programm=edit_programm,
        ziele_by_programm=ziele_by_programm,
        ziele_open_id=ziele_open_id,
    )


@gui.route("/audit-programm/<int:programm_id>/ziel/add", methods=["POST"])
@security.login_required
def audit_programm_ziel_add(programm_id):
    ziel_text = request.form.get("auditZiel", "").strip()
    if ziel_text:
        db.add_audit_ziel(programm_id, ziel_text)
        flash("Auditziel hinzugefuegt.", "success")
    return redirect(url_for("gui.audit_programm", ziele=programm_id))


@gui.route("/audit-programm/ziel/<int:ziel_id>/delete", methods=["POST"])
@security.login_required
def audit_programm_ziel_delete(ziel_id):
    programm_id = request.form.get("programm_id")
    db.delete_audit_ziel(ziel_id)
    flash("Auditziel geloescht.", "success")
    return redirect(url_for("gui.audit_programm", ziele=programm_id))


# --------------------------------------------------------------------------
# Audit planen
# --------------------------------------------------------------------------

@gui.route("/audit-plan", methods=["GET", "POST"])
@security.login_required
def audit_plan():
    warnung = None
    if request.method == "POST":
        plan_id = request.form.get("plan_id")
        data = {
            "auditProgrammId": request.form.get("auditProgrammId"),
            "fachbereich": request.form.get("fachbereich"),
            "auditProzess": request.form.get("auditProzess") or None,
            "verantwortlich": request.form.get("verantwortlich"),
            "datumAuditEnde": request.form.get("datumAuditEnde"),
            "datumInterview": request.form.get("datumInterview"),
            "info": request.form.get("info"),
            "auditStatus": request.form.get("auditStatus") or 1,
        }
        programm = db.get_audit_programm(data["auditProgrammId"])
        if programm:
            start = programm.get("startDatum")
            ende = programm.get("endDatum")
            for feld in ("datumAuditEnde", "datumInterview"):
                wert = data.get(feld)
                if wert and start and ende and not (start <= wert <= ende):
                    warnung = (
                        f"Warnung: Das Datum bei '{feld}' ({wert}) liegt ausserhalb des "
                        f"Programmzeitraums ({start} bis {ende}). Der Eintrag wurde trotzdem gespeichert."
                    )

        if plan_id:
            db.update_audit_plan(plan_id, data)
            aktueller_plan_id = int(plan_id)
            erfolg_text = "Audit-Plan aktualisiert."
        else:
            aktueller_plan_id = db.create_audit_plan(data)
            erfolg_text = "Audit-Plan angelegt."

        if not aktueller_plan_id:
            # Sollte nach dem Anlegen praktisch nie vorkommen (siehe create_audit_plan) -
            # ohne diese Absicherung wuerde ein spaeterer Checkliste-Transfer mit einem
            # rohen Datenbankfehler abbrechen, statt einer verstaendlichen Meldung.
            flash("Der Audit-Plan-Eintrag konnte nicht angelegt/ermittelt werden. Bitte erneut versuchen.", "error")
            return redirect(url_for("gui.audit_plan", programmFilter=data["auditProgrammId"]))

        # Checkliste (Vorlage aus Audit Governance) einmalig als konkrete Proofs
        # in diesen Audit-Plan-Eintrag uebernehmen - inkl. der Proofs der Vorlage.
        # Die Zuordnung selbst wird IMMER am Plan-Eintrag gespeichert (auch wenn die
        # Checkliste keine Proofs enthaelt), siehe copy_checkliste_to_proofs().
        checkliste_id = request.form.get("checkliste_id") or None
        checkliste_uebernommen = False
        if checkliste_id:
            anzahl_kopiert = db.copy_checkliste_to_proofs(aktueller_plan_id, checkliste_id)
            if anzahl_kopiert is not None:
                checkliste_uebernommen = True
                if anzahl_kopiert > 0:
                    erfolg_text += f" Checkliste wurde uebernommen ({anzahl_kopiert} Proof(s))."
                else:
                    erfolg_text += (
                        " Checkliste wurde zugeordnet - sie enthaelt aktuell allerdings keine "
                        "Proofs/Pruefpunkte (unter Audit Governance > Checklisten ergaenzbar)."
                    )

        if warnung:
            flash(warnung, "warning")
        else:
            flash(erfolg_text, "success")

        if checkliste_uebernommen:
            # Direkt im Bearbeiten-Modus weiter zu den uebernommenen Proofs, damit sie
            # gleich angereichert (Punkte/Auditor/Bewertung/Beispiel) werden koennen.
            return redirect(url_for(
                "gui.audit_plan", edit=aktueller_plan_id, programmFilter=data["auditProgrammId"]
            ))
        return redirect(url_for("gui.audit_plan", programmFilter=data["auditProgrammId"]))

    programm_filter = request.args.get("programmFilter") or None
    plaene = db.list_audit_plaene(programm_filter) if programm_filter else []

    edit_id = request.args.get("edit")
    edit_plan = db.get_audit_plan(edit_id) if edit_id else None
    edit_plan_proofs = db.list_proofs_for_plan(edit_id) if edit_id else []
    assigned_checkliste_id = edit_plan.get("checklisteId") if edit_plan else None
    assigned_checkliste_name = _checkliste_name(assigned_checkliste_id)

    # Fuer den direkten [Checkliste]-Button in der Liste: Proofs + Checklisten-Name
    # je Audit-Plan-Eintrag vorab laden (kein zusaetzlicher Klick ueber "Bearbeiten" noetig).
    checkliste_plan_open_id = request.args.get("checklistePlan")
    proofs_by_plan = {}
    checkliste_name_by_plan = {}
    for pl in plaene:
        proofs_by_plan[pl["id"]] = db.list_proofs_for_plan(pl["id"])
        checkliste_name_by_plan[pl["id"]] = _checkliste_name(pl.get("checklisteId"))

    return render_template(
        "audit_plan.html",
        plaene=plaene,
        programm_filter=programm_filter,
        programme=db.list_audit_programme(),
        prozesse=db.get_lookup("Look_QM_AuditProzess"),
        fachbereiche=db.get_lookup("Look_QM_Fachbereich"),
        audit_status=db.get_lookup("Look_QM_AuditStatus"),
        checklisten=db.list_checklisten(),
        edit_plan=edit_plan,
        edit_plan_proofs=edit_plan_proofs,
        assigned_checkliste_id=assigned_checkliste_id,
        assigned_checkliste_name=assigned_checkliste_name,
        proofs_by_plan=proofs_by_plan,
        checkliste_name_by_plan=checkliste_name_by_plan,
        checkliste_plan_open_id=checkliste_plan_open_id,
    )


def _checkliste_name(checkliste_id):
    """Liefert die Bezeichnung einer Checkliste zu einer id, oder None.
    Die Zuordnung selbst liegt direkt an STG_QM_AuditPlan.checklisteId (siehe
    db.copy_checkliste_to_proofs) und ist damit unabhaengig davon erkennbar, ob die
    Checkliste (noch) Proofs/Pruefpunkte enthaelt."""
    if not checkliste_id:
        return None
    checkliste = db.get_checkliste(checkliste_id)
    return checkliste["bezeichnung"] if checkliste else None


@gui.route("/audit-plan/<int:plan_id>/delete", methods=["POST"])
@security.login_required
def audit_plan_delete(plan_id):
    db.delete_audit_plan(plan_id)
    flash("Audit-Plan-Eintrag vollstaendig geloescht.", "success")
    programm_filter = request.form.get("programmFilter") or None
    if programm_filter:
        return redirect(url_for("gui.audit_plan", programmFilter=programm_filter))
    return redirect(url_for("gui.audit_plan"))


@gui.route("/audit-plan/proof/<int:proof_id>/update", methods=["POST"])
@security.login_required
def audit_plan_proof_update(proof_id):
    proof = db.get_proof(proof_id)
    if not proof:
        abort(404)
    punkte_raw = request.form.get("punkte")
    try:
        punkte = int(punkte_raw) if punkte_raw not in (None, "") else None
    except ValueError:
        punkte = None
    data = {
        "auditFrage": request.form.get("auditFrage"),
        "normKapitel": request.form.get("normKapitel"),
        "punkte": punkte,
        "auditor": request.form.get("auditor") or None,
        "bewertung": request.form.get("bewertung") or None,
        "beispiel": request.form.get("beispiel") or None,
    }
    db.update_proof(proof_id, data)
    flash("Proof gespeichert.", "success")
    programm_filter = request.form.get("programmFilter") or None
    plan_id = proof["auditPlanId"]

    # Je nachdem, ob die Aenderung ueber das "Bearbeiten"-Pop-up oder direkt ueber den
    # [Checkliste]-Button in der Liste erfolgt ist, wird danach das passende Pop-up
    # wieder geoeffnet (statt immer den Bearbeiten-Dialog aufzureissen).
    source = request.form.get("source")
    if source == "list":
        return redirect(url_for(
            "gui.audit_plan", programmFilter=programm_filter, checklistePlan=plan_id
        ))
    return redirect(url_for(
        "gui.audit_plan", edit=plan_id, programmFilter=programm_filter
    ))


@gui.route("/audit-plan/<int:plan_id>/proof/add", methods=["POST"])
@security.login_required
def audit_plan_proof_add(plan_id):
    if not db.get_audit_plan(plan_id):
        abort(404)
    punkte_raw = request.form.get("punkte")
    try:
        punkte = int(punkte_raw) if punkte_raw not in (None, "") else None
    except ValueError:
        punkte = None
    data = {
        "auditFrage": request.form.get("auditFrage", "").strip(),
        "normKapitel": request.form.get("normKapitel"),
        "punkte": punkte,
        "auditor": request.form.get("auditor") or None,
        "bewertung": request.form.get("bewertung") or None,
        "beispiel": request.form.get("beispiel") or None,
    }
    if not data["auditFrage"]:
        flash("Bitte eine Frage/einen Pruefpunkt-Text angeben.", "error")
    else:
        db.add_manual_proof_to_plan(plan_id, data)
        flash("Proof manuell hinzugefuegt.", "success")

    programm_filter = request.form.get("programmFilter") or None
    source = request.form.get("source")
    if source == "list":
        return redirect(url_for(
            "gui.audit_plan", programmFilter=programm_filter, checklistePlan=plan_id
        ))
    return redirect(url_for(
        "gui.audit_plan", edit=plan_id, programmFilter=programm_filter
    ))


@gui.route("/audit-plan/proof/<int:proof_id>/delete", methods=["POST"])
@security.login_required
def audit_plan_proof_delete(proof_id):
    proof = db.get_proof(proof_id)
    if not proof:
        abort(404)
    plan_id = proof["auditPlanId"]
    db.delete_proof(proof_id)
    flash("Proof geloescht.", "success")

    programm_filter = request.form.get("programmFilter") or None
    source = request.form.get("source")
    if source == "list":
        return redirect(url_for(
            "gui.audit_plan", programmFilter=programm_filter, checklistePlan=plan_id
        ))
    return redirect(url_for(
        "gui.audit_plan", edit=plan_id, programmFilter=programm_filter
    ))


# --------------------------------------------------------------------------
# Audit durchfuehren
# --------------------------------------------------------------------------

@gui.route("/audit-durchfuehren")
@security.login_required
def audit_durchfuehren():
    plaene = db.list_audit_plaene()
    laufende = [p for p in plaene if p.get("auditStatus") in (2, 3)]
    return render_template("audit_durchfuehren.html", plaene=laufende, alle_plaene=plaene,
                            checklisten=db.list_checklisten())


@gui.route("/audit-durchfuehren/<int:plan_id>/start", methods=["POST"])
@security.login_required
def audit_durchfuehren_start(plan_id):
    checkliste_id = request.form.get("checkliste_id")
    if not checkliste_id:
        flash("Bitte eine Checkliste auswaehlen.", "error")
        return redirect(url_for("gui.audit_durchfuehren"))
    anzahl_kopiert = db.copy_checkliste_to_proofs(plan_id, checkliste_id)
    db.update_audit_plan_status(plan_id, 3)  # In Arbeit
    if anzahl_kopiert is not None and anzahl_kopiert > 0:
        flash(f"Checkliste wurde als {anzahl_kopiert} Proof(s) uebernommen. Audit ist jetzt 'In Arbeit'.", "success")
    elif anzahl_kopiert == 0:
        flash("Checkliste wurde zugeordnet, enthaelt aktuell aber keine Proofs. Audit ist jetzt 'In Arbeit'.", "warning")
    else:
        flash("Fuer diesen Plan ist bereits eine Checkliste zugeordnet.", "warning")
    return redirect(url_for("gui.audit_durchfuehren_detail", plan_id=plan_id))


@gui.route("/audit-durchfuehren/<int:plan_id>")
@security.login_required
def audit_durchfuehren_detail(plan_id):
    plan = db.get_audit_plan(plan_id)
    if not plan:
        abort(404)
    proofs = db.list_proofs_for_plan(plan_id)
    bewertungen = db.get_lookup("Look_QM_AuditBewertung")
    return render_template(
        "audit_durchfuehren.html",
        plan=plan,
        proofs=proofs,
        bewertungen=bewertungen,
        detail_mode=True,
        plaene=[], alle_plaene=db.list_audit_plaene(), checklisten=db.list_checklisten(),
    )


@gui.route("/audit-durchfuehren/proof/<int:proof_id>", methods=["GET", "POST"])
@security.login_required
def audit_proof_detail(proof_id):
    proof = db.get_proof(proof_id)
    if not proof:
        abort(404)
    plan_id = proof["auditPlanId"]

    if request.method == "POST":
        form_type = request.form.get("form_type")

        if form_type == "result":
            bewertung_id = int(request.form.get("auditBewertungID"))
            antwort = request.form.get("antwort", "")
            name_auditor = request.form.get("nameAuditor", "")
            info = request.form.get("auditResultInfo", "")
            datum = request.form.get("datumerfasst") or datetime.now().strftime("%Y-%m-%d")
            result_id = db.add_audit_result(proof_id, name_auditor, bewertung_id, datum, antwort, info)

            if bewertung_id in (2, 3):  # Empfehlung oder Abweichung
                abweichung_text = request.form.get("abweichung", "")
                eigner = request.form.get("nameEigner", "")
                if abweichung_text and eigner:
                    ab_id = db.add_abweichung(result_id, abweichung_text, 1, name_auditor, datum, eigner)
                    massnahme_text = request.form.get("massnahme", "")
                    datum_massnahme = request.form.get("datumMassnahme") or datum
                    massnahme_eigner = request.form.get("massnahmeEigner", eigner)
                    if massnahme_text:
                        db.add_massnahme(ab_id, massnahme_text, datum_massnahme, massnahme_eigner)
                    flash("Ergebnis, Abweichung und Massnahme wurden erfasst.", "success")
                else:
                    flash("Ergebnis erfasst. Achtung: Bei Empfehlung/Abweichung sollten Abweichungstext "
                          "und Eigner ausgefuellt werden.", "warning")
            else:
                flash("Ergebnis erfasst.", "success")

        elif form_type == "link":
            link = request.form.get("link", "").strip()
            if link:
                db.add_link(proof_id, proof.get("auditChecklisteID"), link)
                flash("Link hinzugefuegt.", "success")

        elif form_type == "anhang":
            anhang = request.form.get("anhang", "").strip()
            if anhang:
                db.add_anhang(proof_id, proof.get("auditChecklisteID"), anhang)
                flash("Anhang-Referenz hinzugefuegt.", "success")

        elif form_type == "interview":
            name_auditor = request.form.get("nameAuditor", "")
            inhalt = request.form.get("inhalt", "")
            if inhalt:
                db.add_interview(proof_id, name_auditor, inhalt)
                flash("Interview erfasst.", "success")

        return redirect(url_for("gui.audit_proof_detail", proof_id=proof_id))

    results = db.list_results_for_proof(proof_id)
    links = db.list_links(proof_id)
    anhaenge = db.list_anhaenge(proof_id)
    interviews = db.query(
        "SELECT * FROM STG_QM_AuditInterview WHERE auditProofsId = ? ORDER BY id DESC", (proof_id,)
    )
    abweichungen = db.query("""
        SELECT a.* FROM STG_QM_AuditAbweichung a
        JOIN STG_QM_AuditResult r ON r.id = a.auditResultID
        WHERE r.auditProofsId = ? ORDER BY a.id DESC
    """, (proof_id,))

    return render_template(
        "audit_durchfuehren.html",
        proof_mode=True,
        proof=proof,
        plan=db.get_audit_plan(plan_id),
        results=results,
        links=links,
        anhaenge=anhaenge,
        interviews=interviews,
        abweichungen=abweichungen,
        bewertungen=db.get_lookup("Look_QM_AuditBewertung"),
        plaene=[], alle_plaene=db.list_audit_plaene(), checklisten=db.list_checklisten(),
    )


@gui.route("/audit-durchfuehren/interviews")
@security.login_required
def audit_interviews():
    interviews = db.list_all_interviews()
    return render_template("audit_interview.html", interviews=interviews)


# --------------------------------------------------------------------------
# Governance
# --------------------------------------------------------------------------

@gui.route("/governance/prozesse", methods=["GET", "POST"])
@security.login_required
def governance_prozesse():
    if request.method == "POST":
        action = request.form.get("action")
        prozess_id = request.form.get("prozess_id")

        if action == "delete":
            if db.lookup_is_referenced("Look_QM_AuditProzess", prozess_id):
                flash("Prozess wird bereits verwendet (Audit-Plan/Checkliste) und kann nicht geloescht werden.", "warning")
            else:
                db.delete_lookup_row("Look_QM_AuditProzess", prozess_id)
                flash("Prozess geloescht.", "success")
        else:
            fields = {
                "processName": request.form.get("processName"),
                "processNumber": request.form.get("processNumber"),
                "processOwner": request.form.get("processOwner"),
                "fachbereich": request.form.get("fachbereich") or None,
                "link": request.form.get("link"),
                "normKapitel": request.form.get("normKapitel"),
                "info": request.form.get("info"),
            }
            if prozess_id:
                db.update_lookup_row("Look_QM_AuditProzess", prozess_id, fields)
                flash("Prozess aktualisiert.", "success")
            else:
                db.add_lookup_row("Look_QM_AuditProzess", fields)
                flash("Prozess angelegt.", "success")
        # Ein aktiver Fachbereich-Filter bleibt beim Anlegen/Bearbeiten/Loeschen erhalten -
        # er wird nur zurueckgesetzt, wenn die Seite komplett neu (ohne Query-Parameter) aufgerufen wird.
        fachbereich_filter = request.form.get("fachbereichFilter") or None
        return redirect(url_for("gui.governance_prozesse", fachbereichFilter=fachbereich_filter))

    edit_id = request.args.get("edit")
    fachbereich_filter = request.args.get("fachbereichFilter") or None
    prozesse = db.list_prozesse(fachbereich_filter)
    # Bereits per SQL nach Fachbereich sortiert (ohne Fachbereich zuletzt) - hier nur noch
    # in aufeinanderfolgende Gruppen zusammenfassen, ohne die Reihenfolge neu zu sortieren
    # (das wuerde z.B. "(ohne Fachbereich)" per Jinja-groupby faelschlich nach vorne holen).
    prozesse_gruppiert = [
        (name, list(rows))
        for name, rows in itertools.groupby(prozesse, key=lambda p: p["fachbereichName"])
    ]
    return render_template(
        "governance_prozesse.html",
        prozesse=prozesse,
        prozesse_gruppiert=prozesse_gruppiert,
        fachbereiche=db.get_lookup("Look_QM_Fachbereich"),
        prozess_owner_namen=db.list_prozess_owner_namen(),
        fachbereich_filter=fachbereich_filter,
        edit_prozess=db.get_prozess(edit_id) if edit_id else None,
    )


@gui.route("/governance/fachbereiche", methods=["GET", "POST"])
@security.login_required
def governance_fachbereiche():
    if request.method == "POST":
        fields = {
            "fachbereich": request.form.get("fachbereich"),
            "leitung": request.form.get("leitung"),
            "info": request.form.get("info"),
        }
        fachbereich_id = request.form.get("fachbereich_id")
        action = request.form.get("action")
        if action == "delete":
            if db.lookup_is_referenced("Look_QM_Fachbereich", fachbereich_id):
                flash("Fachbereich wird bereits in einem Audit-Plan verwendet und kann nicht geloescht werden.", "warning")
            else:
                db.delete_lookup_row("Look_QM_Fachbereich", fachbereich_id)
                flash("Fachbereich geloescht.", "success")
        elif fachbereich_id:
            db.update_lookup_row("Look_QM_Fachbereich", fachbereich_id, fields)
            flash("Fachbereich aktualisiert.", "success")
        else:
            db.add_lookup_row("Look_QM_Fachbereich", fields)
            flash("Fachbereich angelegt.", "success")
        return redirect(url_for("gui.governance_fachbereiche"))

    edit_id = request.args.get("edit")
    edit_fachbereich = None
    if edit_id:
        edit_fachbereich = db.query(
            "SELECT * FROM Look_QM_Fachbereich WHERE id = ?", (edit_id,), fetchone=True
        )
    return render_template(
        "governance_fachbereiche.html",
        fachbereiche=db.get_lookup("Look_QM_Fachbereich"),
        mitarbeiter=db.list_mitarbeiter(),
        edit_fachbereich=edit_fachbereich,
    )


@gui.route("/governance/checklisten", methods=["GET", "POST"])
@security.login_required
def governance_checklisten():
    if request.method == "POST":
        fields = {
            "prozessId": request.form.get("prozessId") or None,
            "bezeichnung": request.form.get("bezeichnung"),
            "link": request.form.get("link"),
            "eigner": request.form.get("eigner"),
        }
        checkliste_id = request.form.get("checkliste_id")
        if checkliste_id:
            db.update_checkliste(checkliste_id, fields)
            flash("Checkliste aktualisiert.", "success")
        else:
            db.create_checkliste(fields)
            flash("Checkliste angelegt.", "success")
        return redirect(url_for("gui.governance_checklisten"))

    edit_id = request.args.get("edit")
    return render_template(
        "governance_checklisten.html",
        checklisten=db.list_checklisten(),
        prozesse=db.get_lookup("Look_QM_AuditProzess"),
        edit_checkliste=db.get_checkliste(edit_id) if edit_id else None,
    )


@gui.route("/governance/checklisten/<int:checkliste_id>/delete", methods=["POST"])
@security.login_required
def governance_checkliste_delete(checkliste_id):
    db.delete_checkliste(checkliste_id)
    flash("Checkliste geloescht.", "success")
    return redirect(url_for("gui.governance_checklisten"))


@gui.route("/governance/proofs", methods=["GET", "POST"])
@security.login_required
def governance_proofs():
    checkliste_id = request.args.get("checkliste_id") or request.form.get("checkliste_id")

    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            db.add_checkliste_proof(
                checkliste_id,
                request.form.get("auditFrage"),
                request.form.get("normKapitel"),
                request.form.get("auditResultInfo", ""),
            )
            flash("Proof (Pruepunkt) hinzugefuegt.", "success")
        elif action == "edit":
            db.update_checkliste_proof(
                request.form.get("proof_id"),
                request.form.get("auditFrage"),
                request.form.get("normKapitel"),
                request.form.get("auditResultInfo", ""),
            )
            flash("Proof aktualisiert.", "success")
        elif action == "delete":
            db.delete_checkliste_proof(request.form.get("proof_id"))
            flash("Proof geloescht.", "success")
        return redirect(url_for("gui.governance_proofs", checkliste_id=checkliste_id))

    proofs = db.list_checkliste_proofs(checkliste_id) if checkliste_id else []
    return render_template(
        "governance_proofs.html",
        checklisten=db.list_checklisten(),
        checkliste_id=checkliste_id,
        proofs=proofs,
    )


# --------------------------------------------------------------------------
# Abweichungen
# --------------------------------------------------------------------------

@gui.route("/abweichungen")
@security.login_required
def abweichungen():
    status_filter = request.args.get("status")
    liste = db.list_abweichungen(status_filter)
    return render_template(
        "abweichungen.html",
        abweichungen=liste,
        audit_status=db.get_lookup("Look_QM_AuditStatus"),
        status_filter=status_filter,
    )


@gui.route("/abweichungen/<int:abweichung_id>/massnahme/add", methods=["POST"])
@security.login_required
def abweichung_massnahme_add(abweichung_id):
    massnahme = request.form.get("massnahme", "")
    datum = request.form.get("datumMassnahme") or datetime.now().strftime("%Y-%m-%d")
    eigner = request.form.get("nameEigner", "")
    if massnahme and eigner:
        db.add_massnahme(abweichung_id, massnahme, datum, eigner)
        flash("Massnahme hinzugefuegt.", "success")
    else:
        flash("Massnahme und Eigner sind Pflichtfelder.", "error")
    return redirect(url_for("gui.abweichungen"))


# --------------------------------------------------------------------------
# Massnahmen
# --------------------------------------------------------------------------

@gui.route("/massnahmen")
@security.login_required
def massnahmen():
    status_filter = request.args.get("status")
    liste = db.list_massnahmen(status_filter)
    return render_template(
        "massnahmen.html",
        massnahmen=liste,
        audit_status=db.get_lookup("Look_QM_AuditStatus"),
        status_filter=status_filter,
    )


@gui.route("/massnahmen/<int:massnahme_id>")
@security.login_required
def massnahme_detail(massnahme_id):
    massnahme = db.get_massnahme(massnahme_id)
    if not massnahme:
        abort(404)
    verlauf = db.list_status_massnahme(massnahme_id)
    return render_template(
        "massnahmen.html",
        detail_mode=True,
        massnahme=massnahme,
        verlauf=verlauf,
        audit_status=db.get_lookup("Look_QM_AuditStatus"),
        massnahmen=[],
    )


@gui.route("/massnahmen/<int:massnahme_id>/status/add", methods=["POST"])
@security.login_required
def massnahme_status_add(massnahme_id):
    status_alt = request.form.get("status") or None
    status_neu = request.form.get("statusNeu")
    name = request.form.get("statusName", "")
    info = request.form.get("infoStatus", "")
    datum = request.form.get("statusDatum") or datetime.now().strftime("%Y-%m-%d")
    db.add_status_massnahme(massnahme_id, status_alt, status_neu, datum, name, info)
    flash("Status aktualisiert.", "success")
    return redirect(url_for("gui.massnahme_detail", massnahme_id=massnahme_id))


# --------------------------------------------------------------------------
# Konfiguration
# --------------------------------------------------------------------------

CONFIG_TABLES = {
    "audittyp": ("Look_QM_AuditTyp", ["auditTyp", "info"]),
    "auditstatus": ("Look_QM_AuditStatus", ["auditStatus", "info"]),
    "auditbewertung": ("Look_QM_AuditBewertung", ["auditResult", "info"]),
    "mitarbeiter": ("Look_QM_Mitarbeiter", ["name", "username", "email", "abteilung"]),
}
# Hinweis: Look_QM_AuditProzess (Prozesse) und Look_QM_Fachbereich (Fachbereiche) werden
# NICHT hier verwaltet, sondern ueber die eigenen Seiten unter "Audit governance"
# (Prozesse erfassen / Fachbereiche erfassen), da dort Fachbereich-Dropdown und
# Namenssuche fuer Verantwortliche/Leitung benoetigt werden.


@gui.route("/konfiguration", methods=["GET", "POST"])
@security.login_required
def konfiguration():
    if request.method == "POST":
        table_key = request.form.get("table_key")
        if table_key not in CONFIG_TABLES:
            flash("Unbekannte Tabelle.", "error")
            return redirect(url_for("gui.konfiguration"))
        table_name, columns = CONFIG_TABLES[table_key]
        action = request.form.get("action")

        if action == "delete":
            row_id = request.form.get("row_id")
            if db.lookup_is_referenced(table_name, row_id):
                flash("Eintrag wird bereits verwendet und kann nicht geloescht werden.", "warning")
            else:
                db.delete_lookup_row(table_name, row_id)
                flash("Eintrag geloescht.", "success")
        else:
            fields = {col: request.form.get(col, "") for col in columns}
            row_id = request.form.get("row_id")
            if row_id:
                db.update_lookup_row(table_name, row_id, fields)
                flash("Eintrag aktualisiert.", "success")
            else:
                db.add_lookup_row(table_name, fields)
                flash("Eintrag angelegt.", "success")
        return redirect(url_for("gui.konfiguration", tab=table_key))

    data = {key: db.get_lookup(tbl) for key, (tbl, _) in CONFIG_TABLES.items()}
    active_tab = request.args.get("tab", "audittyp")
    return render_template(
        "konfiguration.html",
        data=data,
        active_tab=active_tab,
        users=db.list_users(),
        rollen=["Admin", "Auditor", "ProzessOwner"],
        ad_configured=com.ad_is_configured(),
    )


@gui.route("/konfiguration/mitarbeiter/ad-sync", methods=["POST"])
@security.login_required
def konfiguration_mitarbeiter_ad_sync():
    result = com.sync_mitarbeiter_from_ad()
    kategorie = "success" if result["status"] == "ok" else "warning"
    flash(result["message"], kategorie)
    return redirect(url_for("gui.konfiguration", tab="mitarbeiter"))


@gui.route("/konfiguration/user/add", methods=["POST"])
@security.roles_required("Admin")
def konfiguration_user_add():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    rolle = request.form.get("rolle", "Auditor")
    if username and password:
        ok, msg = security.create_new_user(username, password, rolle)
        flash(msg, "success" if ok else "error")
    else:
        flash("Benutzername und Passwort sind Pflichtfelder.", "error")
    return redirect(url_for("gui.konfiguration", tab="users"))


@gui.route("/konfiguration/user/<int:user_id>/edit", methods=["POST"])
@security.roles_required("Admin")
def konfiguration_user_edit(user_id):
    rolle = request.form.get("rolle", "Auditor")
    aktiv = request.form.get("aktiv") == "on"
    new_password = request.form.get("password") or None
    security.update_existing_user(user_id, rolle, aktiv, new_password)
    flash("Benutzer aktualisiert.", "success")
    return redirect(url_for("gui.konfiguration", tab="users"))


# --------------------------------------------------------------------------
# Einstellungen
# --------------------------------------------------------------------------

@gui.route("/einstellungen", methods=["GET", "POST"])
@security.roles_required("Admin")
def einstellungen():
    if request.method == "POST":
        enabled = request.form.get("auth_enabled") == "on"
        security.set_auth_enabled(enabled)
        flash(
            "Authentifizierung wurde aktiviert." if enabled else "Authentifizierung wurde deaktiviert.",
            "success",
        )
        return redirect(url_for("gui.einstellungen"))

    return render_template("einstellungen.html", auth_enabled=security.is_auth_enabled())


# --------------------------------------------------------------------------
# Berichte
# --------------------------------------------------------------------------

@gui.route("/berichte", methods=["GET", "POST"])
@security.login_required
def berichte():
    if request.method == "POST":
        programm_id = request.form.get("programm_id")
        if not programm_id:
            flash("Bitte ein Auditprogramm auswaehlen.", "error")
            return redirect(url_for("gui.berichte"))
        try:
            filepath = reports.generate_audit_report_pdf(int(programm_id))
        except Exception as exc:  # noqa: BLE001
            flash(f"Fehler bei der PDF-Erstellung: {exc}", "error")
            return redirect(url_for("gui.berichte"))
        return send_file(filepath, as_attachment=True, download_name=os.path.basename(filepath))

    return render_template("berichte.html", programme=db.list_audit_programme())


# --------------------------------------------------------------------------
# Software beenden (Header-Button)
# --------------------------------------------------------------------------

def _delayed_process_exit(delay=0.5):
    """Beendet den kompletten Python-Prozess nach kurzer Verzoegerung, damit die
    Antwort an den Browser noch gesendet werden kann. os._exit(0) sorgt dafuer,
    dass bei aktivem Werkzeug-Debug-Reloader auch der Ueberwachungsprozess
    (und damit der Debug-Modus) mit beendet wird, statt neu zu starten."""
    time.sleep(delay)
    os._exit(0)


@gui.route("/beenden")
def beenden():
    # Bewusst OHNE @security.login_required: Das Beenden der Anwendung darf auch
    # funktionieren, wenn die Datenbank (SATURN) gerade nicht erreichbar ist -
    # sonst wuerde der DB-Fehler sogar das Schliessen der Anwendung blockieren.
    threading.Thread(target=_delayed_process_exit, daemon=True).start()
    return render_template("beenden.html")
