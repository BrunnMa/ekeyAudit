"""
main.py - Startpunkt der ekeyAudit Flask-Anwendung.

Start: python main.py
Danach im Browser: http://localhost:8080
Login: admin / ekey2026 (nur falls Authentifizierung unter Einstellungen aktiviert wurde)
"""

import os
import threading
import webbrowser

from flask import Flask, render_template

import config
import database as db
import security
from gui.routes import gui


def create_app():
    app = Flask(
        __name__,
        template_folder="gui/templates",
        static_folder="gui/static",
        static_url_path="/static",
    )
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.register_blueprint(gui)

    @app.context_processor
    def inject_globals():
        # is_auth_enabled() liest aus der Datenbank - das dient hier gleichzeitig als
        # Verbindungstest fuer die Kopfzeilen-Statusanzeige. Falls die Verbindung zu
        # SATURN gerade nicht steht, soll das nicht schon das Rendern JEDER Seite
        # (inkl. der Fehlerseite selbst) zum Absturz bringen, sondern defensiv
        # auf "nicht verbunden" fallen.
        try:
            auth_enabled = security.is_auth_enabled()
            db_connected = True
            db_error_message = None
        except db.DatabaseConnectionError as exc:
            auth_enabled = False
            db_connected = False
            db_error_message = str(exc)
        return {
            "app_title": config.APP_TITLE,
            "auth_enabled": auth_enabled,
            "db_connected": db_connected,
            "db_error_message": db_error_message,
            "db_backend": config.DB_BACKEND,
        }

    @app.errorhandler(db.DatabaseConnectionError)
    def handle_db_connection_error(error):
        return render_template(
            "db_error.html",
            error=str(error),
            server=config.MSSQL_SERVER,
            database=config.MSSQL_DATABASE,
            driver=config.MSSQL_DRIVER,
            backend=config.DB_BACKEND,
        ), 503

    return app


app = create_app()


def _open_browser():
    try:
        webbrowser.open(f"http://{config.HOST}:{config.PORT}/")
    except Exception as exc:  # noqa: BLE001 - Browserstart darf den Server nicht stoeren
        print(f"Hinweis: Browser konnte nicht automatisch geoeffnet werden ({exc}).")


def _maybe_autostart_browser():
    """Oeffnet den Standardbrowser automatisch, sobald der Server laeuft.

    Im Debug-Modus startet Werkzeug einen Reloader-Elternprozess, der das
    eigentliche Serverprozess-Kind neu startet. Nur das Kind (erkennbar an
    WERKZEUG_RUN_MAIN=true) soll den Browser oeffnen, damit das Fenster
    nicht doppelt aufgeht.
    """
    if config.DEBUG and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return
    threading.Timer(1.0, _open_browser).start()


if __name__ == "__main__":
    try:
        db.init_db()
        print(f"Datenbank-Backend: {config.DB_BACKEND}"
              + (f" (Server: {config.MSSQL_SERVER}, Datenbank: {config.MSSQL_DATABASE})"
                 if config.DB_BACKEND == "mssql" else f" ({config.DB_PATH})"))
    except db.DatabaseConnectionError as exc:
        print(f"WARNUNG - Datenbank nicht erreichbar: {exc}")
        print("Die Anwendung startet trotzdem und zeigt auf jeder Seite eine Fehlermeldung an, "
              "bis die Verbindung wiederhergestellt ist (kein stiller Fallback auf eine lokale Datei).")

    print(f"ekeyAudit startet auf http://{config.HOST}:{config.PORT}")
    print("Login: admin / ekey2026 (nur falls Authentifizierung in den Einstellungen aktiviert ist)")
    _maybe_autostart_browser()
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)

###########################################################################################
## EOF  
###########################################################################################