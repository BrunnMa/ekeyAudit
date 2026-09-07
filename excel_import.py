"""
excel_import.py - Einlesen von Auditplan-Eintraegen aus einer MS-Excel-Vorlage
("Audit planen" - Button [Auditplan importieren]).

Erwartetes Format der Excel-Datei (wie von Manfred Brunner vorgegeben):
- Jedes Tabellenblatt entspricht einem Auditplan-Eintrag (Fachbereich = Name des
  Tabellenblattes). Ein Blatt namens "Settings" (Konfiguration der Vorlage selbst) wird
  uebersprungen.
- Je Blatt gibt es eine Kopfzeile mit "Frage" in Spalte A; darunter folgen die Fragen:
    Spalte A = laufende Nummer (wird als Reihenfolge des Proofs verwendet)
    Spalte B = Frage (Fragetext, inkl. Norm-Kapitel-Bezug als Teil des Textes)
    Spalte E = Bemerkung (wird als Info-Feld des Proofs uebernommen)
  Alle anderen Spalten (Antwort, Punkte, ...) sind Auditergebnis-Felder der Vorlage selbst
  und werden beim Import bewusst NICHT uebernommen.
- Das Norm-Kapitel wird beim Import nicht separat befuellt (es steckt bereits als Text in
  der Frage selbst).

Unterstuetzt sowohl das alte Binaerformat .xls (ueber xlrd) als auch .xlsx/.xlsm (ueber
openpyxl), da in der Praxis beide Formate vorkommen koennen.
"""

import os

SETTINGS_SHEET_NAMEN = {"settings"}


def _ist_nummer(value):
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return False
        try:
            float(text.replace(",", "."))
            return True
        except ValueError:
            return False
    return False


def _als_text(value):
    if value is None:
        return ""
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value).strip()


def _sheets_xls(file_path):
    import xlrd

    wb = xlrd.open_workbook(file_path)
    for sheet in wb.sheets():
        nrows = sheet.nrows

        def get_cell(r, c, _sheet=sheet):
            if r >= _sheet.nrows or c >= _sheet.ncols:
                return None
            wert = _sheet.cell_value(r, c)
            return wert if wert != "" else None

        yield sheet.name, nrows, get_cell


def _sheets_xlsx(file_path):
    import openpyxl

    wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
    for ws in wb.worksheets:
        nrows = ws.max_row or 0

        def get_cell(r, c, _ws=ws):
            return _ws.cell(row=r + 1, column=c + 1).value

        yield ws.title, nrows, get_cell


def _iter_sheets(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".xls":
        yield from _sheets_xls(file_path)
    else:
        yield from _sheets_xlsx(file_path)


def _find_header_row(nrows, get_cell):
    for r in range(min(nrows, 15)):
        wert = get_cell(r, 0)
        if isinstance(wert, str) and wert.strip() == "Frage":
            return r
    return None


def list_sheet_names(file_path):
    """Liefert die Namen aller Tabellenblaetter, die beim Import beruecksichtigt wuerden
    (also eine erkennbare Fragekopfzeile besitzen und mindestens einen Proof enthalten
    wuerden) - in Dateireihenfolge. Wird verwendet, um dem Anwender im PopUp
    'Auditplan importieren' eine Checkbox-Liste der Tabellenblaetter anzuzeigen, BEVOR
    tatsaechlich importiert wird."""
    namen = []
    for sheet_name, nrows, get_cell in _iter_sheets(file_path):
        if sheet_name.strip().lower() in SETTINGS_SHEET_NAMEN:
            continue
        header_row = _find_header_row(nrows, get_cell)
        if header_row is None:
            continue
        namen.append(sheet_name.strip())
    return namen


def parse_auditplan_excel(file_path, nur_blaetter=None):
    """Liest die Excel-Vorlage ein und liefert eine Liste von Auditplan-Eintraegen:
    [{"fachbereich": "<Tabellenblattname>", "proofs": [{"reihenfolge": 1, "frage": "...",
    "info": "..."}, ...]}, ...]. Blaetter ohne erkennbare Fragekopfzeile (z.B. "Settings")
    werden uebersprungen. Ist 'nur_blaetter' angegeben (Liste von Blattnamen), werden nur
    diese Blaetter beruecksichtigt (z.B. die im PopUp markierten Tabellenblaetter)."""
    erlaubte_blaetter = None
    if nur_blaetter is not None:
        erlaubte_blaetter = {name.strip() for name in nur_blaetter}

    ergebnisse = []
    for sheet_name, nrows, get_cell in _iter_sheets(file_path):
        sheet_name = sheet_name.strip()
        if sheet_name.lower() in SETTINGS_SHEET_NAMEN:
            continue
        if erlaubte_blaetter is not None and sheet_name not in erlaubte_blaetter:
            continue

        header_row = _find_header_row(nrows, get_cell)
        if header_row is None:
            continue

        proofs = []
        reihenfolge = 1
        r = header_row + 1
        while r < nrows:
            nummer = get_cell(r, 0)
            if not _ist_nummer(nummer):
                break
            frage = _als_text(get_cell(r, 1))
            info = _als_text(get_cell(r, 4))
            if frage:
                proofs.append({"reihenfolge": reihenfolge, "frage": frage, "info": info})
                reihenfolge += 1
            r += 1

        if proofs:
            ergebnisse.append({"fachbereich": sheet_name, "proofs": proofs})

    return ergebnisse
