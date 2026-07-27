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
