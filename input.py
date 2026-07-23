"""
input.py - Einlesen externer Dateien fuer ekeyAudit.

Grundgerueste fuer zukuenftige Datenimportfunktionen (z.B. Import von
Checklisten-Vorlagen aus Word/Excel). Der bisherige CSV-Import fuer die
Prozessliste wurde entfernt, da Prozesse direkt ueber die GUI
(Audit governance > Prozesse erfassen) inklusive Fachbereich-Auswahl
und Namenssuche fuer den Prozessverantwortlichen gepflegt werden.
"""

import logging

logger = logging.getLogger("ekeyAudit.input")
