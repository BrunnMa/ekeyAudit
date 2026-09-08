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
    // Falls der Inhalt dieses PopUps erst jetzt zum ersten Mal sichtbar wird, sicherheitshalber
    // erneut pruefen, ob alle Tabellen bereits in ihre Scrollbox gewrappt sind (siehe unten).
    ekeyWrapTablesForScroll();
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
// Begrenzte Listenhoehe (eigene Scrollbox je Liste), auf normalen Seiten UND in PopUps:
// jede Tabelle (.ekey-table) wird zur Laufzeit in einen Wrapper .ekey-table-scroll gelegt
// (feste, kompakte max-height + overflow-y:auto, siehe style.css). Dadurch scrollt nur die
// Liste selbst (ihre Zeilen) innerhalb dieser Box - Seitenueberschrift, Buttons und
// Listenname stehen ausserhalb der Box und muessen nicht mitgescrollt werden. Die
// Tabellenkopfzeile bleibt dank position:sticky (siehe .ekey-table th in style.css) oben in
// dieser Box fixiert, die Zeilen (tbody) verschwinden beim Scrollen darunter.
// ---------------------------------------------------------------------

function ekeyWrapTablesForScroll() {
    document.querySelectorAll("table.ekey-table").forEach(function (table) {
        var parent = table.parentNode;
        if (parent && parent.classList && parent.classList.contains("ekey-table-scroll")) {
            return; // bereits gewrappt
        }
        var wrapper = document.createElement("div");
        wrapper.className = "ekey-table-scroll";
        parent.insertBefore(wrapper, table);
        wrapper.appendChild(table);
    });
}

document.addEventListener("DOMContentLoaded", ekeyWrapTablesForScroll);

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
