/* ============================================================
   Toyota Picking — Frontend Logic
   Target: Samsung Galaxy Tab Active5 (Android, Chrome WebView)
   ============================================================ */

(() => {
  "use strict";

  // ----------------------------------------------------------
  // Config
  // ----------------------------------------------------------
  const CLOCK_TICK_MS = 1000;
  const LOCALE = "pt-BR";
  const TIMEZONE = "America/Sao_Paulo";

  // Scanner payload regex — DATA_STANDARDS §2.5.
  // Accepts any single non-alphanumeric separator (not just '|') to
  // handle ABNT keyboard mis-mapping (e.g. scanner emits '}' instead
  // of '|'). See §2.7.
  const SCAN_PAYLOAD_RE =
    /^([A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{2})[^A-Z0-9](\d{16})$/;

  // Read once at boot
  const wrapper = document.querySelector(".picking-wrapper");
  const ORDER_NUMBER = wrapper ? wrapper.dataset.orderNumber : null;

  // ----------------------------------------------------------
  // Utilities
  // ----------------------------------------------------------
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const log = (...a) => console.log("[picking]", ...a);
  const warn = (...a) => console.warn("[picking]", ...a);

  async function postJSON(path, body = null) {
    const opts = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    };
    if (body !== null) opts.body = JSON.stringify(body);

    const resp = await fetch(path, opts);
    let data = null;
    try { data = await resp.json(); }
    catch { data = { ok: false, error: `HTTP ${resp.status}` }; }
    return { status: resp.status, data };
  }

  // ----------------------------------------------------------
  // Live Clock
  // ----------------------------------------------------------
  const timeFormatter = new Intl.DateTimeFormat(LOCALE, {
    timeZone: TIMEZONE,
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  });
  const dateFormatter = new Intl.DateTimeFormat(LOCALE, {
    timeZone: TIMEZONE,
    day: "2-digit", month: "2-digit", year: "numeric",
  });

  let clockTimeEl = null;
  let clockDateEl = null;

  function updateClock() {
    if (!clockTimeEl || !clockDateEl) return;
    const now = new Date();
    clockTimeEl.textContent = timeFormatter.format(now);
    clockDateEl.textContent = dateFormatter.format(now);
  }

  function startClock() {
    clockTimeEl = $("#clock-time");
    clockDateEl = $("#clock-date");
    if (!clockTimeEl || !clockDateEl) return;
    updateClock();
    setInterval(updateClock, CLOCK_TICK_MS);
    log("Clock started");
  }

  // ----------------------------------------------------------
  // Toast (bottom-of-screen notifications)
  // ----------------------------------------------------------
  const toastEl = () => $("#toast");

  function toast(message, kind = "info", durationMs = 2000) {
    const el = toastEl();
    if (!el) return;
    el.textContent = message;
    el.classList.remove("is-error", "is-success", "is-visible");
    if (kind === "error") el.classList.add("is-error");
    if (kind === "success") el.classList.add("is-success");
    requestAnimationFrame(() => el.classList.add("is-visible"));
    setTimeout(() => el.classList.remove("is-visible"), durationMs);
  }

  // ----------------------------------------------------------
  // Row helpers
  // ----------------------------------------------------------
  function findRow(kanban) {
    return $(`.picking-table tbody tr[data-kanban="${kanban}"]`);
  }

  function applyRowStatus(row, { status, boxes_scanned, boxes_required }) {
    if (!row) return;

    row.dataset.status = status;
    row.dataset.boxesScanned = boxes_scanned;
    row.dataset.boxesRequired = boxes_required;

    row.classList.remove("row-ok", "row-kse", "row-pending", "row-warning");
    if (status === "OK") row.classList.add("row-ok");
    else if (status === "KSE") row.classList.add("row-kse");
    else if (status === "WARNING") row.classList.add("row-warning");
    else row.classList.add("row-pending");

    const cell = row.querySelector(".status-cell");
    if (cell) {
      if (status === "OK") cell.textContent = "OK";
      else if (status === "KSE") cell.textContent = "KSE";
      else if (status === "WARNING") cell.textContent = "WARNING";
      else if (boxes_scanned > 0) {
        cell.innerHTML = `<span class="status-progress">${boxes_scanned}/${boxes_required}</span>`;
      } else {
        cell.innerHTML = "Pending";
      }
    }
  }

  function recomputeRemaining() {
    const rows = $$(".picking-table tbody tr[data-kanban]");
    const remaining = rows.filter(r => r.dataset.status !== "OK").length;
    const el = $("#caixas-restantes");
    if (el) el.textContent = String(remaining);
  }

  // ----------------------------------------------------------
  // Modal
  // ----------------------------------------------------------
  const modal = {
    root: null,
    input: null,
    message: null,
    btnKse: null,
    btnCall: null,
    btnCancel: null,
    btnClose: null,
    currentRow: null,

    init() {
      this.root = $("#status-modal");
      this.input = $("#modal-scan-input");
      this.message = $("#modal-message");
      this.btnKse = $("#btn-kse");
      this.btnCall = $("#btn-call-kanban");
      this.btnCancel = $("#btn-cancel");
      this.btnClose = $(".modal-close", this.root);

      if (!this.root) return;

      this.btnCancel.addEventListener("click", () => this.close());
      this.btnClose.addEventListener("click", () => this.close());
      this.root.addEventListener("click", (e) => {
        if (e.target === this.root) this.close();
      });

      this.btnKse.addEventListener("click", () => this.onKse());
      this.btnCall.addEventListener("click", () => this.onCall());

      this.input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          this.onScan(this.input.value);
        }
      });

      cameraScanner.init((rawPayload) => this.onScan(rawPayload));
    },

    open(row) {
      if (row.dataset.status === "OK") return;

      this.currentRow = row;
      this.clearMessage();

      $("#modal-endereco").textContent = row.dataset.endereco || "—";
      $("#modal-part").textContent = row.dataset.partNumber || "—";
      $("#modal-kanban").textContent = row.dataset.kanban || "—";
      $("#modal-qtd").textContent = row.dataset.qtd || "—";
      $("#modal-scanned").textContent = row.dataset.boxesScanned || "0";
      $("#modal-required").textContent = row.dataset.boxesRequired || "1";

      this.input.value = "";
      this.root.classList.add("is-open");
      this.root.setAttribute("aria-hidden", "false");

      setTimeout(() => this.input.focus(), 50);
    },

    close() {
      cameraScanner.stop();
      this.root.classList.remove("is-open");
      this.root.setAttribute("aria-hidden", "true");
      this.currentRow = null;
      this.clearMessage();
      this.input.value = "";
    },

    showMessage(text, kind = "info") {
      this.message.textContent = text;
      this.message.classList.remove("is-error", "is-success", "is-info");
      this.message.classList.add(`is-${kind}`);
    },

    clearMessage() {
      this.message.textContent = "";
      this.message.classList.remove("is-error", "is-success", "is-info");
    },

    updateProgress(scanned, required) {
      $("#modal-scanned").textContent = scanned;
      $("#modal-required").textContent = required;
    },

    // -------------------- Actions --------------------

    async onScan(rawInput) {
      const payload = (rawInput || "").trim().toUpperCase();
      if (!payload) return;

      const row = this.currentRow;
      if (!row) return;

      // Client-side pre-validation — matches §2.5 (separator-tolerant).
      const match = SCAN_PAYLOAD_RE.exec(payload);
      if (!match) {
        this.showMessage("Formato de QR inválido", "error");
        this.input.value = "";
        this.input.focus();
        return;
      }

      const scannedPart = match[1];
      const expectedPart = row.dataset.partNumber;

      if (scannedPart !== expectedPart) {
        this.showMessage(
          `Peça errada: esperado ${expectedPart}, escaneado ${scannedPart}`,
          "error"
        );
        this.input.value = "";
        this.input.focus();
        return;
      }

      // Optimistic UI — snapshot to roll back on failure
      const prev = { ...row.dataset };
      const newScanned = parseInt(row.dataset.boxesScanned || "0", 10) + 1;
      const required = parseInt(row.dataset.boxesRequired || "1", 10);
      const optimisticStatus = newScanned >= required ? "OK" : "PENDING";

      applyRowStatus(row, {
        status: optimisticStatus,
        boxes_scanned: newScanned,
        boxes_required: required,
      });
      this.updateProgress(newScanned, required);
      recomputeRemaining();

      const kanban = row.dataset.kanban;
      const { status, data } = await postJSON(
        `/api/picking/${ORDER_NUMBER}/${kanban}/scan`,
        { payload }
      );

if (status === 200 && data.ok) {
        applyRowStatus(row, {
          status: data.status,
          boxes_scanned: data.boxes_scanned,
          boxes_required: data.boxes_required,
        });
        this.updateProgress(data.boxes_scanned, data.boxes_required);
        recomputeRemaining();

        if (data.status === "OK") {
          this.showMessage("Kanban completo!", "success");
          setTimeout(() => this.close(), 800);
        } else {
          this.showMessage(
            `Escaneado ${data.boxes_scanned}/${data.boxes_required}`,
            "success"
          );
          this.input.value = "";
          this.input.focus();
        }
      } else {
        // Roll back optimistic update
        applyRowStatus(row, {
          status: prev.status,
          boxes_scanned: parseInt(prev.boxesScanned || "0", 10),
          boxes_required: parseInt(prev.boxesRequired || "1", 10),
        });
        this.updateProgress(
          parseInt(prev.boxesScanned || "0", 10),
          parseInt(prev.boxesRequired || "1", 10)
        );
        recomputeRemaining();

        const errMsg = (data && data.error) || `Erro HTTP ${status}`;
        this.showMessage(errMsg, "error");
        this.input.value = "";
        this.input.focus();
      }
    },

    async onKse() {
      const row = this.currentRow;
      if (!row) return;

      const prev = { ...row.dataset };

      // Optimistic
      applyRowStatus(row, {
        status: "KSE",
        boxes_scanned: parseInt(row.dataset.boxesScanned || "0", 10),
        boxes_required: parseInt(row.dataset.boxesRequired || "1", 10),
      });
      recomputeRemaining();

      const kanban = row.dataset.kanban;
      const { status, data } = await postJSON(
        `/api/picking/${ORDER_NUMBER}/${kanban}/kse`
      );

      if (status === 200 && data.ok) {
        applyRowStatus(row, {
          status: data.status,
          boxes_scanned: data.boxes_scanned,
          boxes_required: data.boxes_required,
        });
        recomputeRemaining();
        toast(`KSE registrado — ${data.parts_lacking} peça(s) faltando`, "success");
        this.close();
      } else {
        // Rollback
        applyRowStatus(row, {
          status: prev.status,
          boxes_scanned: parseInt(prev.boxesScanned || "0", 10),
          boxes_required: parseInt(prev.boxesRequired || "1", 10),
        });
        recomputeRemaining();
        const errMsg = (data && data.error) || `Erro HTTP ${status}`;
        this.showMessage(errMsg, "error");
      }
    },

    async onCall() {
      const row = this.currentRow;
      if (!row) return;

      const kanban = row.dataset.kanban;
      const { status, data } = await postJSON(
        `/api/picking/${ORDER_NUMBER}/${kanban}/call`
      );

      if (status === 200 && data.ok) {
        toast("Supervisor notificado", "success");
      } else {
        const errMsg = (data && data.error) || `Erro HTTP ${status}`;
        toast(errMsg, "error");
      }
    },
  };

  // ----------------------------------------------------------
  // Camera Scanner (BarcodeDetector-based)
  //
  // Design decisions:
  //   - Rear camera (facingMode: "environment")
  //   - First detected QR wins, others ignored
  //   - Camera turns off after each successful scan
  //   - Falls back gracefully if BarcodeDetector isn't supported
  // ----------------------------------------------------------
  const cameraScanner = {
    video: null,
    preview: null,
    toggleBtn: null,
    stream: null,
    detector: null,
    rafId: null,
    onDetected: null,
    supported: false,

    async init(onDetected) {
      this.video = $("#camera-video");
      this.preview = $("#camera-preview");
      this.toggleBtn = $("#btn-camera-toggle");
      this.onDetected = onDetected;

      if (typeof window.BarcodeDetector === "undefined") {
        warn("BarcodeDetector not supported; hiding camera button");
        this.toggleBtn.style.display = "none";
        return;
      }

      try {
        const formats = await window.BarcodeDetector.getSupportedFormats();
        if (!formats.includes("qr_code")) {
          warn("QR code format not supported by BarcodeDetector");
          this.toggleBtn.style.display = "none";
          return;
        }
        this.detector = new window.BarcodeDetector({ formats: ["qr_code"] });
        this.supported = true;
      } catch (e) {
        warn("BarcodeDetector init failed:", e);
        this.toggleBtn.style.display = "none";
        return;
      }

      this.toggleBtn.addEventListener("click", () => this.toggle());
    },

    async toggle() {
      if (this.stream) {
        this.stop();
      } else {
        await this.start();
      }
    },

    async start() {
      if (!this.supported) return;

      try {
        this.stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: { ideal: "environment" },
            width: { ideal: 1280 },
            height: { ideal: 720 },
          },
          audio: false,
        });
      } catch (e) {
        warn("getUserMedia failed:", e);
        toast("Câmera indisponível — use scanner externo", "error", 2500);
        return;
      }

      this.video.srcObject = this.stream;
      await this.video.play();
      this.preview.classList.add("is-active");
      this.toggleBtn.textContent = "⏹ Desligar câmera";

      this.scanLoop();
    },

    stop() {
      if (this.rafId) {
        cancelAnimationFrame(this.rafId);
        this.rafId = null;
      }
      if (this.stream) {
        this.stream.getTracks().forEach(t => t.stop());
        this.stream = null;
      }
      if (this.video) {
        this.video.srcObject = null;
      }
      if (this.preview) {
        this.preview.classList.remove("is-active");
      }
      if (this.toggleBtn) {
        this.toggleBtn.textContent = "📷 Ativar câmera";
      }
    },

    async scanLoop() {
      if (!this.stream || !this.detector) return;

      try {
        const codes = await this.detector.detect(this.video);
        if (codes && codes.length > 0) {
          const raw = (codes[0].rawValue || "").trim();
          if (raw) {
            this.stop();
            if (this.onDetected) this.onDetected(raw);
            return;
          }
        }
      } catch (e) {
        warn("Detect frame error:", e);
      }

      this.rafId = requestAnimationFrame(() => this.scanLoop());
    },
  };

  // ----------------------------------------------------------
  // Row click → open modal
  // ----------------------------------------------------------
  function bindRowClicks() {
    const tbody = $("#picking-tbody");
    if (!tbody) return;

    tbody.addEventListener("click", (e) => {
      const row = e.target.closest("tr[data-kanban]");
      if (!row) return;
      modal.open(row);
    });
  }

  // ----------------------------------------------------------
  // Global buttons
  // ----------------------------------------------------------
  function handleExit() {
    if (confirm("Encerrar sessão?")) {
      window.location.href = "/";
    }
  }

  async function handleChamar(e) {
    flashButton(e.currentTarget);
    const { status, data } = await postJSON("/api/chamar", {
      order_number: ORDER_NUMBER,
    });
    if (status === 200 && data && data.ok) {
      toast("Supervisor notificado", "success");
    } else {
      toast((data && data.error) || `Erro HTTP ${status}`, "error");
    }
  }

  async function handleProximo(e) {
    flashButton(e.currentTarget);
    if (!confirm("Avançar para o próximo carrinho?")) return;
    const { status, data } = await postJSON("/api/proximo-carrinho");
    log("proximo-carrinho:", status, data);
    toast("Próximo carrinho (stub)", "info");
  }

  function flashButton(btn) {
    if (!btn) return;
    const original = btn.style.transform;
    btn.style.transform = "scale(0.97)";
    setTimeout(() => { btn.style.transform = original; }, 120);
  }

  function bindGlobalButtons() {
    const exitBtn = $(".btn-exit");
    const chamarBtn = $(".btn-chamar");
    const proximoBtn = $(".btn-proximo");

    if (exitBtn) exitBtn.addEventListener("click", handleExit);
    if (chamarBtn) chamarBtn.addEventListener("click", handleChamar);
    if (proximoBtn) proximoBtn.addEventListener("click", handleProximo);
  }

  // ----------------------------------------------------------
  // Prevent accidental zoom / context menu on tablet
  // ----------------------------------------------------------
  function hardenTouchUX() {
    let lastTouchEnd = 0;
    document.addEventListener("touchend", (e) => {
      const now = Date.now();
      if (now - lastTouchEnd <= 300) e.preventDefault();
      lastTouchEnd = now;
    }, { passive: false });

    document.addEventListener("contextmenu", (e) => e.preventDefault());
    document.addEventListener("gesturestart", (e) => e.preventDefault());
    document.addEventListener("gesturechange", (e) => e.preventDefault());
    document.addEventListener("gestureend", (e) => e.preventDefault());
  }

  // ----------------------------------------------------------
  // Boot
  // ----------------------------------------------------------
  function init() {
    log("Init — order:", ORDER_NUMBER);
    startClock();
    modal.init();
    bindRowClicks();
    bindGlobalButtons();
    hardenTouchUX();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();