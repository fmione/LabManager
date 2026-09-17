(function () {
  "use strict";

  function initTables() {
    var tables = document.querySelectorAll("table[data-dt]");
    if (!tables.length || typeof DataTable === "undefined") return;

    Array.prototype.forEach.call(tables, function (table) {
      var srcRows = table.tBodies.length
        ? Array.prototype.slice.call(table.tBodies[0].rows)
        : [];
      var columnDefs = [];
      var header = table.tHead && table.tHead.rows.length ? table.tHead.rows[0] : null;

      if (header) {
        Array.prototype.forEach.call(header.cells, function (th, i) {
          if (th.className && (/(^|\s)no-sort(\s|$)/).test(th.className)) {
            columnDefs.push({ targets: i, orderable: false, searchable: false });
          }
        });
      }

      new DataTable(table, {
        language: { url: "/static/js/i18n/es-ES.json" },
        pageLength: 10,
        lengthMenu: [
          [10, 25, 50, -1],
          [10, 25, 50, "Todos"]
        ],
        order: [],
        columnDefs: columnDefs,
        createdRow: function (row, data, dataIndex) {
          var src = srcRows[dataIndex];
          if (!src) return;
          var dstCells = row.cells;
          for (var c = 0; c < src.cells.length && c < dstCells.length; c++) {
            var label = src.cells[c].getAttribute("data-label");
            if (label) dstCells[c].setAttribute("data-label", label);
            if (src.cells[c].className) dstCells[c].className = src.cells[c].className;
          }
        }
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initTables);
  } else {
    initTables();
  }
})();