// ekeyAudit - app.js
// Kleines JS fuer Sidebar-Toggle (einklappbar), kein Framework.

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

function ekeyAddAuditorRow() {
    var container = document.getElementById("auditorRows");
    if (!container) return;
    var row = document.createElement("div");
    row.className = "ekey-auditor-row";
    row.innerHTML =
        '<input type="text" name="auditor_liste" list="mitarbeiter_liste" autocomplete="off" ' +
        'placeholder="Namen eingeben zum Suchen...">' +
        '<button type="button" class="ekey-btn ekey-btn-small" onclick="ekeyRemoveAuditorRow(this)">Entfernen</button>';
    container.appendChild(row);
}

function ekeyRemoveAuditorRow(btn) {
    var container = document.getElementById("auditorRows");
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
// Startseite (AuditHome): ausgewaehltes Auditprogramm oeffnen
// ---------------------------------------------------------------------

function ekeyOpenAuditprogramm() {
    var form = document.getElementById("homeAuditprogrammForm");
    var select = document.getElementById("homeAuditprogrammSelect");
    if (!form || !select || !select.value) return;
    window.location.href = form.getAttribute("data-base-url") + "?edit=" + encodeURIComponent(select.value);
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
