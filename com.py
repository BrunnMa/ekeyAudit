"""
com.py - Kommunikation zu anderen Anwendungen fuer ekeyAudit.

Enthaelt:
 - E-Mail-Erinnerungen (aktuell nur Logging-Dummy, siehe send_reminder_email)
 - Mitarbeiter-Abgleich mit dem Active Directory der Organisation per LDAP
   (sync_mitarbeiter_from_ad), damit das Auditor-Feld auf der Seite
   "Audit programm" aus echten AD-Benutzernamen ausgewaehlt/gesucht werden kann.

Der LDAP-Zugriff ist rein optional: ist config.AD_SERVER nicht gesetzt, wird
kein Verbindungsversuch unternommen und die Mitarbeiterliste bleibt manuell
gepflegt (siehe Konfiguration -> Mitarbeiter in der GUI).
"""

import logging
from datetime import datetime

import config
import database as db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ekeyAudit.com")


def send_reminder_email(empfaenger, betreff, inhalt):
    """
    Dummy-Funktion fuer den Versand einer Erinnerungs-E-Mail.

    In dieser Version wird keine echte E-Mail verschickt, sondern der
    Vorgang protokolliert. Ein spaeterer Ausbau (z.B. via smtplib oder
    einem Mailserver-Relay) kann diese Funktion ersetzen, ohne dass
    Aufrufer angepasst werden muessen.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(
        "[DUMMY-MAIL] %s | An: %s | Betreff: %s | Inhalt: %s",
        timestamp, empfaenger, betreff, inhalt,
    )
    return {
        "status": "logged_only",
        "empfaenger": empfaenger,
        "betreff": betreff,
        "timestamp": timestamp,
    }


def send_audit_termin_erinnerung(auditor_name, email, plan_info, termin_datum):
    """Beispiel-Wrapper fuer eine konkrete Erinnerung zu einem Audit-Termin."""
    betreff = f"Erinnerung: Audit-Termin am {termin_datum}"
    inhalt = f"Hallo {auditor_name},\n\nAm {termin_datum} steht folgendes Audit an:\n{plan_info}\n\nBitte vorbereiten."
    return send_reminder_email(email, betreff, inhalt)


def send_massnahme_faellig_erinnerung(eigner_name, email, massnahme_text, faellig_am):
    """Beispiel-Wrapper fuer eine Erinnerung zu einer faelligen Massnahme."""
    betreff = f"Erinnerung: Massnahme faellig am {faellig_am}"
    inhalt = f"Hallo {eigner_name},\n\nFolgende Massnahme ist faellig:\n{massnahme_text}\n\nBitte Status aktualisieren."
    return send_reminder_email(email, betreff, inhalt)


# --------------------------------------------------------------------------
# Active Directory / LDAP - Mitarbeiter-Abgleich fuer die Auditor-Auswahl
# --------------------------------------------------------------------------

def ad_is_configured():
    return bool(config.AD_SERVER and config.AD_BASE_DN)


def sync_mitarbeiter_from_ad():
    """Fragt Mitarbeiternamen aus dem konfigurierten Active Directory per LDAP ab
    und gleicht sie mit der lokalen Tabelle Look_QM_Mitarbeiter ab (upsert ueber
    sAMAccountName). Gibt ein Ergebnis-Dict mit Status/Anzahl/Fehlermeldung zurueck.

    Voraussetzung: Paket 'ldap3' installiert und in config.py hinterlegt:
      EKEY_AD_SERVER, EKEY_AD_BASE_DN, EKEY_AD_BIND_USER, EKEY_AD_BIND_PASSWORD
    (z.B. als Umgebungsvariablen). Ohne AD_SERVER/AD_BASE_DN wird gar nicht erst
    versucht, eine Verbindung aufzubauen.
    """
    if not ad_is_configured():
        return {
            "status": "not_configured",
            "message": (
                "Kein Active Directory konfiguriert (EKEY_AD_SERVER / EKEY_AD_BASE_DN fehlen). "
                "Mitarbeiterliste bleibt manuell gepflegt."
            ),
            "count": 0,
        }

    try:
        import ldap3
    except ImportError:
        return {
            "status": "error",
            "message": "Paket 'ldap3' ist nicht installiert. Bitte 'pip install ldap3' ausfuehren.",
            "count": 0,
        }

    try:
        server = ldap3.Server(config.AD_SERVER, use_ssl=config.AD_USE_SSL, get_info=ldap3.ALL)
        conn = ldap3.Connection(
            server,
            user=config.AD_BIND_USER or None,
            password=config.AD_BIND_PASSWORD or None,
            auto_bind=True,
        )
    except Exception as exc:  # noqa: BLE001 - jede Verbindungsstoerung soll als Ergebnis zurueckkommen
        logger.warning("AD-Verbindung fehlgeschlagen: %s", exc)
        return {
            "status": "error",
            "message": f"Verbindung zum Active Directory fehlgeschlagen: {exc}",
            "count": 0,
        }

    try:
        attrs = [config.AD_ATTR_NAME, config.AD_ATTR_USERNAME, config.AD_ATTR_EMAIL, config.AD_ATTR_DEPARTMENT]
        conn.search(
            search_base=config.AD_BASE_DN,
            search_filter=config.AD_USER_FILTER,
            attributes=attrs,
        )
        sync_zeitpunkt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        anzahl = 0
        for entry in conn.entries:
            username = str(getattr(entry, config.AD_ATTR_USERNAME, "")) or None
            name = str(getattr(entry, config.AD_ATTR_NAME, "")) or username
            email = str(getattr(entry, config.AD_ATTR_EMAIL, "")) or None
            abteilung = str(getattr(entry, config.AD_ATTR_DEPARTMENT, "")) or None
            if not username or not name:
                continue
            db.upsert_mitarbeiter_from_ad(username, name, email, abteilung, sync_zeitpunkt)
            anzahl += 1

        logger.info("AD-Sync abgeschlossen: %s Mitarbeiter uebernommen.", anzahl)
        return {
            "status": "ok",
            "message": f"{anzahl} Mitarbeiter aus dem Active Directory uebernommen.",
            "count": anzahl,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("AD-Suche fehlgeschlagen: %s", exc)
        return {
            "status": "error",
            "message": f"Abfrage des Active Directory fehlgeschlagen: {exc}",
            "count": 0,
        }
    finally:
        conn.unbind()
