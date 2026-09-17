const CHART_COLORS = [
  "#0ea5e9", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6",
  "#ec4899", "#14b8a6", "#f97316", "#6366f1", "#84cc16",
];

function openSidebar() {
  document.getElementById("sidebar").classList.add("open");
  document.getElementById("sidebarBackdrop").classList.add("show");
}

function closeSidebar() {
  document.getElementById("sidebar").classList.remove("open");
  document.getElementById("sidebarBackdrop").classList.remove("show");
}

const MAX_IMAGE_SIZE = 2 * 1024 * 1024;
const MAX_IMAGES_PER_NOTE = 3;
const ALLOWED_IMAGE_EXTS = [".jpg", ".jpeg", ".png", ".webp", ".gif"];

function showClientAlert(message, target) {
  let container;
  if (target && typeof target.querySelector === "function") {
    container = target;
  } else {
    const modal = document.querySelector(".modal.show");
    container = (modal && modal.querySelector(".modal-body")) || document.querySelector(".content") || document.body;
  }
  container.querySelectorAll(".alert").forEach(el => el.remove());
  const div = document.createElement("div");
  div.className = "alert alert-danger alert-dismissible fade show";
  div.setAttribute("role", "alert");
  div.textContent = message;
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "btn-close";
  btn.dataset.bsDismiss = "alert";
  btn.setAttribute("aria-label", "Cerrar");
  div.appendChild(btn);
  if (container.prepend) container.prepend(div);
  else container.insertBefore(div, container.firstChild);
  setTimeout(() => div.classList.add("d-none"), 10000);
  if (div.scrollIntoView) div.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function validateImageFile(file) {
  const ext = "." + (file.name.split(".").pop() || "").toLowerCase();
  if (!ALLOWED_IMAGE_EXTS.includes(ext)) {
    return `Formato no permitido en '${file.name}'. Usá JPG, PNG, WEBP o GIF.`;
  }
  if (file.size > MAX_IMAGE_SIZE) {
    return `La imagen '${file.name}' supera el tamaño máximo de 2 MB.`;
  }
  return null;
}

function validateNoteImages(form) {
  for (const input of form.querySelectorAll('input[type="file"][name="images"]')) {
    for (const file of input.files) {
      const err = validateImageFile(file);
      if (err) {
        showClientAlert(err, form.closest(".modal"));
        return false;
      }
    }
  }
  return true;
}

function bindRemoveImageButtons() {
  document.querySelectorAll(".note-remove-img").forEach(wrap => {
    const btn = wrap.querySelector(".note-remove-img-x");
    const hidden = wrap.querySelector('input[name="remove_images"]');
    if (!btn || !hidden) return;
    btn.addEventListener("click", () => {
      if (wrap.dataset.removed) return;
      wrap.dataset.removed = "1";
      hidden.checked = true;
      wrap.style.setProperty("display", "none", "important");
      const modal = wrap.closest(".modal");
      const picker = modal && modal.querySelector(".note-img-picker");
      if (picker) updateNoteImageCounter(picker);
    });
  });
}

function countPickerImages(picker) {
  return picker.querySelectorAll(".note-img-file").length
       + picker.querySelectorAll(".note-remove-img:not([data-removed])").length;
}

function updateNoteImageCounter(picker) {
  const used = countPickerImages(picker);
  const counter = picker.querySelector(".note-img-counter");
  const fresh = picker.querySelector(".note-img-input");
  if (fresh) fresh.disabled = used >= MAX_IMAGES_PER_NOTE;
  if (counter) {
    const rest = Math.max(0, MAX_IMAGES_PER_NOTE - used);
    counter.textContent = rest === 0
      ? "Se alcanzó el máximo de imágenes permitidas."
      : `Podés agregar hasta ${rest} imagen${rest === 1 ? "" : "es"} más.`;
  }
}

function initNoteImagePickers(root) {
  const pickers = root.querySelectorAll(".note-img-picker");
  if (!pickers.length) return;
  pickers.forEach(picker => {
    if (picker.dataset.ready) return;
    picker.dataset.ready = "1";
    updateNoteImageCounter(picker);
    picker.addEventListener("change", e => {
      const input = e.target;
      if (!(input instanceof HTMLInputElement)) return;
      if (input.type !== "file" || !input.classList.contains("note-img-input")) return;
      const file = input.files && input.files[0];
      if (!file) return;
      if (countPickerImages(picker) >= MAX_IMAGES_PER_NOTE) {
        input.value = "";
        showClientAlert(`Máximo ${MAX_IMAGES_PER_NOTE} imágenes por nota.`, picker.closest(".modal"));
        return;
      }
      const err = validateImageFile(file);
      if (err) {
        input.value = "";
        showClientAlert(err, picker.closest(".modal"));
        return;
      }
      const name = file.name;
      const reader = new FileReader();
      reader.onload = ev => {
        const wrap = document.createElement("div");
        wrap.className = "note-img-file position-relative d-inline-block";
        const img = document.createElement("img");
        img.src = ev.target.result;
        img.alt = name;
        img.className = "img-thumbnail";
        img.style.width = "96px";
        img.style.height = "96px";
        img.style.objectFit = "cover";
        const x = document.createElement("button");
        x.type = "button";
        x.className = "btn btn-danger position-absolute";
        x.style.top = "4px";
        x.style.right = "4px";
        x.style.width = "22px";
        x.style.height = "22px";
        x.style.padding = "0";
        x.style.lineHeight = "1";
        x.style.borderRadius = "50%";
        x.style.display = "flex";
        x.style.alignItems = "center";
        x.style.justifyContent = "center";
        x.title = "Quitar imagen";
        x.setAttribute("aria-label", "Quitar imagen");
        x.innerHTML = '<i class="bi bi-x-lg"></i>';
        x.addEventListener("click", () => {
          wrap.remove();
          updateNoteImageCounter(picker);
        });
        wrap.appendChild(img);
        input.hidden = true;
        input.classList.remove("note-img-input");
        input.classList.add("note-img-file-input");
        wrap.appendChild(input);
        wrap.appendChild(x);
        const fresh = document.createElement("input");
        fresh.type = "file";
        fresh.className = "form-control note-img-input";
        fresh.name = "images";
        fresh.accept = ".jpg,.jpeg,.png,.webp,.gif";
        picker.querySelector(".note-img-select").appendChild(fresh);
        picker.querySelector(".note-img-previews").appendChild(wrap);
        updateNoteImageCounter(picker);
      };
      reader.readAsDataURL(file);
    });
  });
}

function bindConfirmDialogs() {
  const modalEl = document.getElementById("confirmModal");
  if (!modalEl) return;
  const modal = new bootstrap.Modal(modalEl);
  const body = document.getElementById("confirmBody");
  const okBtn = document.getElementById("confirmOk");
  let pendingForm = null;

  document.addEventListener("submit", function (e) {
    const form = e.target;
    if (!(form instanceof HTMLFormElement)) return;
    if (!form.hasAttribute("data-confirm")) return;
    e.preventDefault();
    pendingForm = form;
    body.textContent = form.getAttribute("data-confirm");
    modal.show();
  });

  okBtn.addEventListener("click", function () {
    modal.hide();
    if (pendingForm) {
      const f = pendingForm;
      pendingForm = null;
      f.submit();
    }
  });
}

function bindModalReset() {
  document.querySelectorAll(".modal").forEach(modalEl => {
    modalEl.addEventListener("hidden.bs.modal", () => {
      modalEl.querySelectorAll(".note-remove-img").forEach(wrap => {
        delete wrap.dataset.removed;
        const hidden = wrap.querySelector('input[name="remove_images"]');
        if (hidden) hidden.checked = false;
        wrap.style.removeProperty("display");
      });
      modalEl.querySelectorAll(".note-img-file").forEach(wrap => wrap.remove());
      const picker = modalEl.querySelector(".note-img-picker");
      if (picker) {
        updateNoteImageCounter(picker);
      }
    });
  });
}

document.addEventListener("DOMContentLoaded", function () {
  const toggle = document.getElementById("sidebarToggle");
  const backdrop = document.getElementById("sidebarBackdrop");
  if (toggle) toggle.addEventListener("click", openSidebar);
  if (backdrop) backdrop.addEventListener("click", closeSidebar);
  document.querySelectorAll(".sidebar nav a").forEach(a =>
    a.addEventListener("click", closeSidebar)
  );
  bindConfirmDialogs();
  initNoteImagePickers(document);
  bindRemoveImageButtons();
  bindModalReset();
  bindChartResize();

  document.addEventListener("submit", function (e) {
    if (e.target instanceof HTMLFormElement && e.target.querySelector('input[type="file"][name="images"]')) {
      if (!validateNoteImages(e.target)) e.preventDefault();
    }
  });
});

function addSensorRow(containerId) {
  const c = document.getElementById(containerId);
  if (!c) return;
  const row = document.createElement("div");
  row.className = "row g-2 align-items-center sensor-row mb-2";
  row.innerHTML = `
    <div class="col-md-4">
      <input type="text" class="form-control form-control-sm" name="sensor_name" placeholder="nombre (ej: temperature)" required>
    </div>
    <div class="col-md-3">
      <input type="text" class="form-control form-control-sm" name="sensor_unit" placeholder="unidad (ej: °C)">
    </div>
    <div class="col-md-3">
      <select class="form-select form-select-sm" name="sensor_type">
        <option value="float">float</option>
        <option value="bool">bool</option>
      </select>
    </div>
    <div class="col-md-2">
      <button type="button" class="btn btn-sm btn-outline-danger" onclick="this.closest('.sensor-row').remove()" title="Quitar">
        <i class="bi bi-x-lg"></i>
      </button>
    </div>`;
  c.appendChild(row);
}

function fmtTime(ms) {
  return new Date(ms).toLocaleString("es-AR", {
    day: "2-digit", month: "2-digit", year: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
    timeZone: window.LM_TZ || "Etc/GMT+3",
  });
}

function isSmallScreen() {
  return window.innerWidth < 768;
}

function xTickRotation() {
  return isSmallScreen() ? 90 : 0;
}

function buildAlertRangeDatasets(series, opts) {
  if (!opts || opts.alertRanges !== true) return [];
  if (series.length !== 1) return [];
  const s = series[0];
  if (s.min_value === null && s.max_value === null) return [];
  const xs = s.points.map(p => p[0]);
  if (xs.length < 2) return [];
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const make = (label, value) => ({
    label,
    data: [{ x: minX, y: value }, { x: maxX, y: value }],
    borderColor: "#8a8a8a",
    borderWidth: 1.5,
    borderDash: [6, 4],
    pointRadius: 0,
    pointHoverRadius: 0,
    fill: false,
    tension: 0,
  });
  const out = [];
  if (s.min_value !== null) out.push(make("Mín. alerta", s.min_value));
  if (s.max_value !== null) out.push(make("Máx. alerta", s.max_value));
  return out;
}

function buildLineChart(canvasId, series, emptyId, opts = {}) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const empty = document.getElementById(emptyId);
  window.__lmSeries = {};
  window.__lmRangeDatasets = null;
  if (window.__lmChart) { window.__lmChart.destroy(); window.__lmChart = null; }
  if (!series || series.length === 0 || series.every(s => s.points.length === 0)) {
    if (empty) empty.classList.remove("d-none");
    return;
  }
  if (empty) empty.classList.add("d-none");
  const datasets = series.map((s, i) => {
    const dataset = {
      label: s.label,
      data: s.points.map(p => ({ x: p[0], y: p[1] })),
      borderColor: CHART_COLORS[i % CHART_COLORS.length],
      backgroundColor: CHART_COLORS[i % CHART_COLORS.length] + "22",
      borderWidth: 2,
      pointRadius: 1,
      pointHoverRadius: 4,
      tension: 0.2,
    };
    window.__lmSeries[s.sensor_id] = {
      label: s.label,
      unit: s.unit,
      type: s.type,
      min_value: s.min_value,
      max_value: s.max_value,
      points: s.points,
      dataset,
    };
    return dataset;
  });
  const rangeDatasets = buildAlertRangeDatasets(series, opts);
  if (rangeDatasets.length) window.__lmRangeDatasets = rangeDatasets;
  window.__lmChart = new Chart(canvas, {
    type: "line",
    data: { datasets: datasets.concat(rangeDatasets) },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: {
          type: "linear",
          ticks: {
            maxTicksLimit: isSmallScreen() ? 4 : 8,
            maxRotation: xTickRotation(),
            minRotation: xTickRotation(),
            autoSkip: true,
            callback: v => new Date(v).toLocaleString("es-AR", {
              day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
timeZone: window.LM_TZ || "Etc/GMT+3",
            }),
          },
        },
        y: { beginAtZero: false },
      },
      plugins: {
        legend: { position: "bottom" },
        tooltip: {
          callbacks: {
            title: items => items.length ? fmtTime(items[0].parsed.x) : "",
            label: item => ` ${item.dataset.label}: ${item.parsed.y}`,
          },
        },
      },
    },
  });
}

async function apiData(params) {
  const res = await fetch("/api/data?" + new URLSearchParams(params));
  if (!res.ok) throw new Error("Error al consultar los datos");
  return res.json();
}

let _resizeHandler = null;
function bindChartResize() {
  if (_resizeHandler) return;
  _resizeHandler = debounce(() => {
    const chart = window.__lmChart;
    const scale = chart && chart.options && chart.options.scales && chart.options.scales.x;
    if (!scale) return;
    const rot = xTickRotation();
    scale.ticks.maxTicksLimit = isSmallScreen() ? 4 : 8;
    scale.ticks.maxRotation = rot;
    scale.ticks.minRotation = rot;
    chart.update("none");
  }, 150);
  window.addEventListener("resize", _resizeHandler);
}

function debounce(fn, ms) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}
