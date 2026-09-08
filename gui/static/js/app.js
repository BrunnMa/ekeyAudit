// ekeyAudit - app.js
// Kleines JS fuer Sidebar-Toggle (einklappbar), kein Framework.

// ---------------------------------------------------------------------
// Ladeanzeige fuer Seiten, deren Aufruf spuerbar dauert (z.B. "Audit
// durchfuehren - Plan", da dort je Proof mehrere Datenbankabfragen noetig
// sind). Wird vor dem eigentlichen Seitenwechsel per onclick eingeblendet
// und bleibt bis zum Laden der naechsten Seite sichtbar.
// ---------------------------------------------------------------------

function ekeyShowLoadingOverlay() {
    var overlay = document.getElementById("ekeyLoadingOverlay");
    if (overlay) overlay.classList.add("ekey-loading-visible");
}

// Automatisch bei JEDEM Speichervorgang (Formular-Absenden) die Ladeanzeige
// einblenden - unabhaengig davon, um welches Formular/welche Seite es sich
// handelt. Der eigentliche Seitenwechsel (Redirect nach dem Speichern) laedt
// danach ganz normal eine neue Seite, wodurch die Anzeige automatisch wieder
// verschwindet.
document.addEventListener("submit", function (e) {
    if (e.target && e.target.tagName === "FORM") {
        ekeyShowLoadingOverlay();
    }
});

// Automatisch bei JEDEM Ladevorgang (Klick auf einen Link, der auf eine
// andere/dieselbe Seite dieser Anwendung navigiert) die Ladeanzeige
// einblenden. Links, die in einem neuen Tab oeffnen (target="_blank") oder
// keine echte Seitennavigation ausloesen (mailto:/tel:), werden bewusst
// ausgenommen.
document.addEventListener("click", function (e) {
    var link = e.target.closest("a[href]");
    if (!link || link.target === "_blank") return;
    var href = link.getAttribute("href") || "";
    if (href.indexOf("mailto:") === 0 || href.indexOf("tel:") === 0 || href.indexOf("#") === 0) return;
    ekeyShowLoadingOverlay();
});

document.addEventListener("DOMContentLoaded", function () {
    var toggleBtn = document.getElementById("sidebarToggle");
    var sidebar = document.getElementById("ekeySidebar");

    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener("click", function () {
            sidebar.classList.toggle("collapsed");
        });
    }
});

// ---------------------------------------------------------------------
// Auditor(en)-Liste auf der Seite "Audit programm": Zeilen hinzufuegen/entfernen
// ---------------------------------------------------------------------

function ekeyAddAuditorRow(containerId) {
    var container = document.getElementById(containerId || "auditorRows");
    if (!container) return;
    var row = document.createElement("div");
    row.className = "ekey-auditor-row";
    row.innerHTML =
        '<input type="text" name="auditor_liste" list="mitarbeiter_liste" autocomplete="off" ' +
        'placeholder="Namen eingeben zum Suchen...">' +
        '<button type="button" class="ekey-btn ekey-btn-small" onclick="ekeyRemoveAuditorRow(this, \'' + (containerId || "auditorRows") + '\')">Entfernen</button>';
    container.appendChild(row);
}

function ekeyRemoveAuditorRow(btn, containerId) {
    var container = document.getElementById(containerId || "auditorRows");
    if (!container) return;
    if (container.children.length > 1) {
        btn.parentElement.remove();
    } else {
        var input = btn.parentElement.querySelector("input");
        if (input) input.value = "";
    }
}

// ---------------------------------------------------------------------
// Generische Pop-up/Modal-Steuerung (z.B. "Neues Auditprogramm anlegen",
// "Neuer Auditplan-Eintrag erstellen")
// ---------------------------------------------------------------------

function ekeyOpenModal(id) {
    var overlay = document.getElementById(id);
    if (overlay) overlay.classList.add("ekey-modal-open");
    // Beim Oeffnen neu berechnen: solange ein PopUp "display:none" war, liefert
    // getBoundingClientRect() dort ueberall 0 - die Sticky-Bereiche im PopUp-Inhalt koennen
    // also erst korrekt vermessen werden, NACHDEM es sichtbar wurde.
    ekeyUpdateStickyLayout();
}

function ekeyCloseModal(id) {
    var overlay = document.getElementById(id);
    if (overlay) overlay.classList.remove("ekey-modal-open");
}

document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
        document.querySelectorAll(".ekey-modal-overlay.ekey-modal-open").forEach(function (o) {
            o.classList.remove("ekey-modal-open");
        });
    }
});

document.addEventListener("click", function (e) {
    if (e.target && e.target.classList && e.target.classList.contains("ekey-modal-overlay")) {
        e.target.classList.remove("ekey-modal-open");
    }
});

// ---------------------------------------------------------------------
// Fixierte Seitenueberschrift/Listennamen/Buttons ueber Listen (Tabellen), auf normalen
// Seiten UND in PopUps: alles, was VOR der ersten Tabelle eines Bereichs steht (Seiten-
// ueberschrift + darueber platzierte Buttons in .ekey-content; Listenname + Buttons/Filter
// vor der Tabelle in jedem .ekey-panel), wird einmalig in einen Sticky-Wrapper
// (.ekey-sticky-band) verschoben. Die "top"-Position wird dynamisch aus der tatsaechlich
// gerenderten Hoehe der jeweils darueberliegenden fixierten Bereiche berechnet (nicht fest
// verdrahtet), damit es unabhaengig von Schriftgroesse/Zeilenumbruch/Anzahl Buttons je Seite
// korrekt bleibt. Nur Listenzeilen (tbody) scrollen dann noch normal.
// ---------------------------------------------------------------------

function ekeyMakeStickyBand(container, stopSelector, baseTop) {
    var stopEl = container.querySelector(":scope > " + stopSelector);
    if (!stopEl) return null;

    var band = container.querySelector(":scope > .ekey-sticky-band");
    if (!band) {
        band = document.createElement("div");
        band.className = "ekey-sticky-band";
        container.insertBefore(band, container.firstChild);
        var node = band.nextSibling;
        while (node && node !== stopEl) {
            var next = node.nextSibling;
            band.appendChild(node);
            node = next;
        }
    }

    if (!band.firstChild) {
        // Nichts zu fixieren (Tabelle stand schon ganz am Anfang) - Wrapper wieder entfernen.
        band.parentNode.removeChild(band);
        return baseTop;
    }

    band.style.top = baseTop + "px";
    return baseTop + band.getBoundingClientRect().height;
}

function ekeyLayoutStickyPanels(scopeEl, baseTop) {
    // In manchen PopUps (z.B. [Abweichung], [Massnahmen], Checkliste-PopUp) steht die Tabelle
    // ohne umschliessenden .ekey-panel direkt im PopUp-Koerper, mit einer Ueberschrift (h4/h2)
    // und/oder einem Formular bzw. einer Button-Zeile davor. Damit auch dieser Bereich fixiert
    // wird (wie bei den .ekey-panel-Listen auf den normalen Seiten), wird zuerst - genau wie auf
    // Seitenebene bei .ekey-content - der Inhalt vor der ersten Tabelle bzw. dem ersten Panel
    // innerhalb von scopeEl selbst in einen Sticky-Wrapper verschoben.
    var leadingTop = ekeyMakeStickyBand(scopeEl, ".ekey-panel, :scope > table.ekey-table", baseTop);
    var top = leadingTop === null ? baseTop : leadingTop;

    scopeEl.querySelectorAll(".ekey-panel").forEach(function (panel) {
        var theadTop = ekeyMakeStickyBand(panel, "table.ekey-table", top);
        if (theadTop === null) return;
        var table = panel.querySelector(":scope > table.ekey-table");
        table.querySelectorAll("thead th").forEach(function (th) {
            th.style.top = theadTop + "px";
        });
    });

    // "Nackte" Tabelle direkt in scopeEl (nicht in einem .ekey-panel) - deren eigene Ueberschrift/
    // Buttons wurden oben bereits per Sticky-Band fixiert, jetzt noch die Tabellenkopfzeile selbst
    // auf die passende "top"-Position setzen (analog zur .ekey-table-th-Regel in style.css, hier
    // aber mit dem dynamisch berechneten Offset statt nur "top: 0").
    var bareTable = scopeEl.querySelector(":scope > table.ekey-table");
    if (bareTable) {
        bareTable.querySelectorAll("thead th").forEach(function (th) {
            th.style.top = top + "px";
        });
    }
}

function ekeyUpdateStickyLayout() {
    document.querySelectorAll(".ekey-content").forEach(function (content) {
        ekeyLayoutStickyPanels(content, 0);
    });
    document.querySelectorAll(".ekey-modal-overlay.ekey-modal-open .ekey-modal-body").forEach(function (body) {
        ekeyLayoutStickyPanels(body, 0);
    });
}

document.addEventListener("DOMContentLoaded", ekeyUpdateStickyLayout);

(function () {
    var resizeTimer = null;
    window.addEventListener("resize", function () {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(ekeyUpdateStickyLayout, 150);
    });
})();

// ---------------------------------------------------------------------
// In allen Pop-up-Formularen (Dateneingabe) darf [Enter] das Pop-up nicht
// schliessen/absenden, sondern springt nur zum naechsten Datenfeld. Schliessen
// bzw. Speichern erfolgt ausschliesslich ueber die Buttons.
// ---------------------------------------------------------------------

function ekeyFocusableFields(container) {
    var nodes = container.querySelectorAll(
        'input:not([type="hidden"]):not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled])'
    );
    return Array.prototype.filter.call(nodes, function (el) {
        return el.offsetParent !== null; // nur sichtbare/aktive Felder beruecksichtigen
    });
}

document.addEventListener("keydown", function (e) {
    if (e.key !== "Enter") return;

    var target = e.target;
    if (!target || !target.closest) return;

    var modal = target.closest(".ekey-modal");
    if (!modal) return; // ausserhalb von Pop-ups: normales Verhalten

    // In Textareas soll [Enter] weiterhin einen Zeilenumbruch einfuegen.
    if (target.tagName === "TEXTAREA") return;

    // In Richtext-Editoren (contenteditable) soll [Enter] ebenfalls normal
    // einen Zeilenumbruch einfuegen statt zum naechsten Feld zu springen.
    if (target.isContentEditable) return;

    // Auf Buttons (z.B. "Speichern", "Schliessen") soll [Enter] wie ein Klick wirken -
    // das Schliessen/Absenden per Button ist ausdruecklich erlaubt.
    if (target.tagName === "BUTTON") return;

    e.preventDefault();

    var fields = ekeyFocusableFields(modal);
    var idx = fields.indexOf(target);
    if (idx > -1 && idx + 1 < fields.length) {
        fields[idx + 1].focus();
        if (typeof fields[idx + 1].select === "function") {
            fields[idx + 1].select();
        }
    }
});

// ---------------------------------------------------------------------
// Seite "Audit planen", PopUp "Auditplan importieren": nach Auswahl der
// Excel-Datei werden deren Tabellenblaetter per AJAX ermittelt und als
// Checkbox-Liste angezeigt (alle zunaechst markiert). Beim eigentlichen
// Import (Formular-Absenden) werden dann nur die markierten Blaetter
// beruecksichtigt (siehe routes.py: audit_plan_import).
// ---------------------------------------------------------------------

function ekeyLoadImportSheets(input) {
    var row = document.getElementById("importSheetsRow");
    var list = document.getElementById("importSheetsList");
    var erkanntFeld = document.getElementById("importSheetsErkannt");
    if (!row || !list || !erkanntFeld) return;

    list.innerHTML = "";
    erkanntFeld.value = "0";
    row.style.display = "none";

    if (!input.files || !input.files[0]) return;

    var formData = new FormData();
    formData.append("importFile", input.files[0]);

    list.innerHTML = "<span class=\"ekey-hint\">Tabellenblaetter werden ermittelt...</span>";
    row.style.display = "";

    fetch(input.form.getAttribute("data-sheets-url") || "/audit-plan/import/tabellenblaetter", {
        method: "POST",
        body: formData
    })
        .then(function (resp) { return resp.json(); })
        .then(function (data) {
            list.innerHTML = "";
            if (data.error) {
                list.innerHTML = "<span class=\"ekey-hint\">" + data.error + "</span>";
                row.style.display = "";
                return;
            }
            if (!data.sheets || data.sheets.length === 0) {
                list.innerHTML = "<span class=\"ekey-hint\">Keine passenden Tabellenblaetter (mit Fragekopfzeile) gefunden.</span>";
                erkanntFeld.value = "1";
                row.style.display = "";
                return;
            }
            data.sheets.forEach(function (name) {
                var label = document.createElement("label");
                label.className = "ekey-checkbox-item";
                var cb = document.createElement("input");
                cb.type = "checkbox";
                cb.name = "selectedSheets";
                cb.value = name;
                cb.checked = true;
                label.appendChild(cb);
                label.appendChild(document.createTextNode(" " + name));
                list.appendChild(label);
            });
            erkanntFeld.value = "1";
            row.style.display = "";
        })
        .catch(function () {
            list.innerHTML = "<span class=\"ekey-hint\">Tabellenblaetter konnten nicht ermittelt werden.</span>";
            row.style.display = "";
        });
}

// ---------------------------------------------------------------------
// Startseite (AuditHome): ausgewaehltes Auditprogramm oeffnen
// ---------------------------------------------------------------------

function ekeyOpenAuditprogramm() {
    var form = document.getElementById("homeAuditprogrammForm");
    var select = document.getElementById("homeAuditprogrammSelect");
    if (!form || !select || !select.value) return;
    // Bewusst OHNE "?edit=..." navigieren: von der Startseite aus soll nur die Seite
    // "Auditprogramm erstellen" geoeffnet werden, nicht automatisch das PopUp zum Aendern
    // (das PopUp oeffnet weiterhin gezielt ueber den Button [Bearbeiten] in der Programmliste).
    window.location.href = form.getAttribute("data-base-url");
}

// ---------------------------------------------------------------------
// Generisches Ein-/Ausblenden (z.B. "+ Neues Ziel"-Formular in einem Pop-up)
// ---------------------------------------------------------------------

function ekeyToggle(id) {
    var el = document.getElementById(id);
    if (!el) return;
    if (el.style.display === "none") {
        el.style.display = "";
    } else {
        el.style.display = "none";
    }
}

// ---------------------------------------------------------------------
// Einfache Richtext-Eingabe (Fett/Kursiv/Unterstrichen/Listen), z.B. fuer die
// Proof-Felder "Frage" und "Info". Kein Framework: contenteditable-Div +
// document.execCommand. Der aktuelle Inhalt (HTML) wird bei jeder Aenderung
// sowie zusaetzlich beim Absenden des Formulars in ein verstecktes
// Input-Feld uebertragen, damit er ganz normal mit dem Formular gespeichert
// wird.
// ---------------------------------------------------------------------

function ekeyRichTextSync(editor) {
    var wrapper = editor.closest(".ekey-richtext");
    if (!wrapper) return;
    var hidden = wrapper.querySelector("input.ekey-richtext-value");
    if (hidden) hidden.value = editor.innerHTML;
}

// Merkt sich die aktuelle Textmarkierung im Editor, damit sie beim Klick auf
// ein Toolbar-Element (Button oder Farbwaehler) - was den Fokus kurzzeitig
// aus dem Editor herausnimmt - vor dem Ausfuehren des Formatbefehls wieder
// hergestellt werden kann.
function ekeyRichTextSaveSelection(editor) {
    var sel = window.getSelection();
    if (sel.rangeCount > 0) {
        var range = sel.getRangeAt(0);
        if (editor.contains(range.commonAncestorContainer)) {
            editor._ekeySavedRange = range.cloneRange();
        }
    }
}

function ekeyRichTextRestoreSelection(editor) {
    if (editor._ekeySavedRange) {
        var sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(editor._ekeySavedRange);
    }
}

function ekeyRichTextApplyCommand(wrapper, command, value) {
    var editor = wrapper.querySelector(".ekey-richtext-editor");
    if (!editor) return;
    editor.focus();
    ekeyRichTextRestoreSelection(editor);
    document.execCommand(command, false, value || null);
    ekeyRichTextSaveSelection(editor);
    ekeyRichTextSync(editor);
}

document.addEventListener("mousedown", function (e) {
    // Verhindert, dass ein Klick auf einen Toolbar-Button die Textmarkierung
    // im Editor verwirft, bevor der Formatbefehl ausgefuehrt wird.
    if (e.target.closest(".ekey-rt-btn")) {
        e.preventDefault();
    }
});

document.addEventListener("click", function (e) {
    var resetBtn = e.target.closest(".ekey-rt-color-reset");
    if (resetBtn) {
        e.preventDefault();
        var resetWrapper = resetBtn.closest(".ekey-richtext");
        if (resetWrapper) ekeyRichTextApplyCommand(resetWrapper, "foreColor", "#333333");
        return;
    }
    var btn = e.target.closest(".ekey-rt-btn");
    if (!btn) return;
    e.preventDefault();
    var wrapper = btn.closest(".ekey-richtext");
    if (!wrapper) return;
    ekeyRichTextApplyCommand(wrapper, btn.getAttribute("data-command"));
});

document.addEventListener("input", function (e) {
    var colorInput = e.target.closest(".ekey-rt-color");
    if (!colorInput) return;
    var wrapper = colorInput.closest(".ekey-richtext");
    if (!wrapper) return;
    ekeyRichTextApplyCommand(wrapper, "foreColor", colorInput.value);
});

document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".ekey-richtext-editor").forEach(function (editor) {
        editor.addEventListener("input", function () { ekeyRichTextSync(editor); });
        editor.addEventListener("blur", function () { ekeyRichTextSync(editor); });
        editor.addEventListener("mouseup", function () { ekeyRichTextSaveSelection(editor); });
        editor.addEventListener("keyup", function () { ekeyRichTextSaveSelection(editor); });
    });
    document.querySelectorAll("form").forEach(function (form) {
        form.addEventListener("submit", function () {
            form.querySelectorAll(".ekey-richtext-editor").forEach(function (editor) {
                ekeyRichTextSync(editor);
            });
        });
    });
});
