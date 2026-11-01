/**
 * Discord NLP Moderation Dashboard - Client Interactivity
 * Studio Discord Native Edition with Full CRUD Modals & User Grouping
 */

document.addEventListener("DOMContentLoaded", () => {
  initSidebarToggle();
  initRailIcons();
  initTabs();
  initActionHandlers();
  initFilterAndSearch();
  initUserAccordion();
  initDiscordModals();
  initDatasetModal();
  initJumpToUser();
});

// State tracking for active modals
let currentEditMessageId = null;
let currentUserTarget = null;
let currentUserId = null;

/**
 * Sidebar Toggle (Hide / Show 240px Channel Sidebar)
 * Can be triggered from topbar button or rail Direct Messages logo
 */
function initSidebarToggle() {
  const toggleBtn = document.getElementById("sidebar-toggle-btn");
  const dmBtn = document.getElementById("rail-dm-btn");
  const sidebar = document.getElementById("channel-sidebar");
  if (!sidebar) return;

  const doToggle = () => {
    const isCollapsed = sidebar.classList.toggle("collapsed");
    if (toggleBtn) {
      toggleBtn.innerText = isCollapsed ? "▶" : "◀";
      toggleBtn.setAttribute("title", isCollapsed ? "Tampilkan Sidebar" : "Sembunyikan Sidebar");
      toggleBtn.setAttribute("aria-expanded", isCollapsed ? "false" : "true");
    }
  };

  if (toggleBtn) {
    toggleBtn.addEventListener("click", doToggle);
  }

  if (dmBtn) {
    dmBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      doToggle();
    });
  }
}

/**
 * Column 1: Server Rail Icons Click Handling
 */
function initRailIcons() {
  const railItems = document.querySelectorAll(".js-rail-icon:not(#rail-dm-btn)");
  railItems.forEach((item) => {
    item.addEventListener("click", () => {
      railItems.forEach((r) => r.classList.remove("active"));
      item.classList.add("active");
    });
  });
}

/**
 * Switch active viewport tab panel and update sidebar/topbar state
 */
function switchTab(targetTabId) {
  const sidebarItems = document.querySelectorAll(".js-sidebar-nav");
  const tabPanels = document.querySelectorAll(".tab-panel");
  const title = document.getElementById("viewport-title");

  sidebarItems.forEach((b) => {
    if (b.getAttribute("data-tab") === targetTabId) {
      b.classList.add("active");
      if (title) {
        const labelSpan = b.querySelector("span.truncate") || b.querySelector("span:nth-child(2)") || b.querySelector("span");
        if (labelSpan) {
          title.innerText = labelSpan.innerText.toLowerCase().replace(/\s+/g, "-");
        }
      }
    } else {
      b.classList.remove("active");
    }
  });

  tabPanels.forEach((p) => {
    if (p.id === targetTabId) {
      p.classList.remove("hidden");
    } else {
      p.classList.add("hidden");
    }
  });
}

/**
 * Column 2: Channel Sidebar Tab Switching & Dashboard Admin Home Trigger
 */
function initTabs() {
  const sidebarItems = document.querySelectorAll(".js-sidebar-nav");

  sidebarItems.forEach((item) => {
    item.addEventListener("click", () => {
      const target = item.getAttribute("data-tab");
      if (target) {
        switchTab(target);
      }
    });
  });

  function handleReturnToFlaggedQueue() {
    switchTab("tab-flagged");
  }

  // Clicking "Dashboard Admin" in the header bar returns to Antrean Tinjauan with confirmation
  const serverHeader = document.getElementById("server-header-btn") || document.querySelector(".server-header-box");
  if (serverHeader) {
    serverHeader.addEventListener("click", handleReturnToFlaggedQueue);
  }

  // Clicking "Dashboard Admin" icon in the rail returns to Antrean Tinjauan with confirmation
  const railServerBtn = document.getElementById("rail-server-btn");
  if (railServerBtn) {
    railServerBtn.addEventListener("click", handleReturnToFlaggedQueue);
  }
}

/**
 * User-Centric Violations Accordion
 */
function initUserAccordion() {
  document.addEventListener("click", (e) => {
    const header = e.target.closest(".js-toggle-user-accordion");
    if (!header) return;

    // Don't toggle if an action button inside the header was clicked
    if (e.target.closest("button")) return;

    const targetId = header.getAttribute("data-target");
    const body = document.getElementById(targetId);
    const icon = header.querySelector(".accordion-chevron, .accordion-icon");

    if (body) {
      const isOpen = !body.classList.contains("hidden");
      if (isOpen) {
        body.classList.add("hidden");
        if (icon) icon.classList.remove("open");
      } else {
        body.classList.remove("hidden");
        if (icon) icon.classList.add("open");
      }
    }
  });
}

const BAN_DURATIONS = [
  { value: 60, label: "1 Jam" },
  { value: 120, label: "2 Jam" },
  { value: 360, label: "6 Jam" },
  { value: 720, label: "12 Jam" },
  { value: 1440, label: "1 Hari" },
  { value: 10080, label: "7 Hari" },
  { value: 0, label: "Permanen" },
];

// Aksi yang efeknya nyata di Discord & sulit dibatalkan -> wajib lewat kartu konfirmasi
const CONFIRM_ACTIONS = {
  timeout_10m: { title: "Konfirmasi Timeout (10 Menit)", confirmText: "Timeout Pengguna", subtext: "Pengguna tidak bisa mengirim pesan selama 10 menit." },
  timeout_1h: { title: "Konfirmasi Timeout (1 Jam)", confirmText: "Timeout Pengguna", subtext: "Pengguna tidak bisa mengirim pesan selama 1 jam." },
  timeout_24h: { title: "Konfirmasi Timeout (24 Jam)", confirmText: "Timeout Pengguna", subtext: "Pengguna tidak bisa mengirim pesan selama 24 jam." },
  kick: { title: "Konfirmasi Kick", confirmText: "Kick Pengguna", subtext: "Pengguna dikeluarkan dari server, tetapi masih bisa bergabung lagi lewat undangan." },
  ban: { title: "Konfirmasi Ban", confirmText: "Ban Pengguna", subtext: "Pilih durasi ban. Ban sementara akan dicabut otomatis oleh bot saat waktunya habis.", durations: BAN_DURATIONS },
};

function durationLabel(minutes) {
  const found = BAN_DURATIONS.find((d) => d.value === Number(minutes));
  return found ? found.label : "Permanen";
}

function authorOf(btn) {
  const userCard = btn.closest(".user-group-card");
  if (userCard) return userCard.getAttribute("data-author") || "";
  const jump = btn.closest(".flagged-item-card")?.querySelector(".js-jump-to-user");
  return jump ? jump.getAttribute("data-author") || "" : "";
}

/**
 * Submit Quick Review Action to Backend
 */
async function submitReviewAction(actionBtn, messageId, action, label, originalText, durationMinutes) {
  actionBtn.innerText = "Memproses...";
  actionBtn.disabled = true;

  const labelWithDuration = action === "ban" ? `${label} ${durationLabel(durationMinutes)}` : label;

  try {
    const res = await fetch("/api/actions/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message_id: messageId,
        action: action,
        duration_minutes: durationMinutes,
        notes: `Aksi manual [${labelWithDuration}] oleh Administrator`,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(`Gagal: ${err.error || "Terjadi kesalahan"}`);
      actionBtn.innerText = originalText;
      actionBtn.disabled = false;
      return;
    }

    const data = await res.json();

    // Successful review: smoothly remove card from flagged view and refresh count
    const card = document.getElementById(`flagged-card-${messageId}`);
    if (card) {
      card.style.transition = "opacity 0.25s ease, transform 0.25s ease";
      card.style.opacity = "0";
      card.style.transform = "scale(0.98)";
      setTimeout(() => {
        card.remove();
        updateFlaggedCount();
      }, 250);
    }

    showNotice(data.discord_message || `Pesan ${messageId} berhasil diselesaikan (${labelWithDuration}).`, "success");
    reloadAuditLogs();
    reloadUsersSummary();
  } catch (error) {
    console.error("Action error:", error);
    alert("Koneksi gagal saat memproses aksi review.");
    actionBtn.innerText = originalText;
    actionBtn.disabled = false;
  }
}

/**
 * Quick Review Action Buttons in Flagged Message Queue
 */
function initActionHandlers() {
  document.addEventListener("click", async (e) => {
    const actionBtn = e.target.closest(".js-review-action");
    if (!actionBtn) return;

    const messageId = actionBtn.getAttribute("data-message-id");
    const action = actionBtn.getAttribute("data-action");
    const label = actionBtn.innerText.trim();
    const originalText = actionBtn.innerText;

    const cfg = CONFIRM_ACTIONS[action];
    if (cfg) {
      const author = authorOf(actionBtn);
      openConfirmModal({
        title: cfg.title,
        message: `Terapkan "${label}" untuk ${author || "pengguna ini"}?`,
        quote: author ? `${author} — ${messageId}` : `ID Pesan: ${messageId}`,
        subtext: cfg.subtext,
        confirmText: cfg.confirmText,
        confirmClass: "btn-dc-danger",
        durations: cfg.durations || null,
        onConfirm: async (durationMinutes) => {
          await submitReviewAction(actionBtn, messageId, action, label, originalText, durationMinutes);
        },
      });
      return;
    }

    await submitReviewAction(actionBtn, messageId, action, label, originalText);
  });
}

function updateFlaggedCount() {
  const remaining = document.querySelectorAll(".flagged-item-card").length;
  const countBadge = document.getElementById("flagged-badge-count");
  const kpiCount = document.getElementById("kpi-flagged-count");
  if (countBadge) countBadge.innerText = remaining;
  if (kpiCount) kpiCount.innerText = `${remaining} Pesan`;

  if (remaining === 0) {
    const listContainer = document.getElementById("flagged-list-container");
    if (listContainer) {
      listContainer.innerHTML = `
        <div class="py-12 text-center text-slate-500 text-xs">
          Semua pesan telah selesai ditinjau. Tidak ada antrean baru saat ini.
        </div>
      `;
    }
  }
}

/**
 * Filter and Search in Audit Logs
 */
function initFilterAndSearch() {
  const searchInput = document.getElementById("search-logs-input");
  const labelSelect = document.getElementById("filter-label-select");
  const statusSelect = document.getElementById("filter-status-select");

  if (!searchInput || !labelSelect || !statusSelect) return;

  let debounceTimer;
  searchInput.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(reloadAuditLogs, 250);
  });

  labelSelect.addEventListener("change", reloadAuditLogs);
  statusSelect.addEventListener("change", reloadAuditLogs);
}

/**
 * Reload and Re-render Audit Logs Table
 */
async function reloadAuditLogs() {
  const searchInput = document.getElementById("search-logs-input");
  const labelSelect = document.getElementById("filter-label-select");
  const statusSelect = document.getElementById("filter-status-select");
  const tbody = document.getElementById("audit-logs-tbody");

  if (!tbody) return;

  const queryParams = new URLSearchParams();
  if (searchInput && searchInput.value) queryParams.set("search", searchInput.value);
  if (labelSelect && labelSelect.value !== "all") queryParams.set("label_filter", labelSelect.value);
  if (statusSelect && statusSelect.value !== "all") queryParams.set("status_filter", statusSelect.value);

  try {
    const res = await fetch(`/api/audit-logs?${queryParams.toString()}`);
    if (!res.ok) return;

    const data = await res.json();
    if (data.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6" class="py-8 text-center text-slate-500 text-xs font-code">
            Tidak ada catatan audit yang cocok dengan filter yang dipilih.
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = data
      .map((item) => {
        const activeLabels = Object.entries(item.labels || {})
          .filter(([_, val]) => val === true)
          .map(([lbl, _]) => `<span class="badge badge-accent mr-1 mb-1">${escapeHtml(lbl)}</span>`)
          .join("");

        const statusClass = item.status.includes("Pardon")
          ? "badge-positive"
          : /Ban|Kick|Timeout/.test(item.status)
          ? "badge-negative"
          : "badge-warning";

            const datasetBtnHtml = item.in_dataset
              ? `<button class="btn-dc btn-dc-sm btn-dc-secondary opacity-60 cursor-not-allowed" disabled title="Pesan ini sudah ditambahkan ke dataset">✓ Di Dataset</button>`
              : `<button class="btn-dc btn-dc-sm btn-dc-primary js-open-dataset-modal" data-message-id="${item.message_id}" data-content="${escapeHtml(item.content)}" data-labels='${JSON.stringify(item.labels || {})}' title="Tambah ke Dataset">+ Dataset</button>`;

            return `
          <tr id="audit-row-${item.message_id}">
            <td>
              <div class="font-bold text-slate-900">${escapeHtml(item.author)}</div>
              <div class="text-xs text-slate-500 font-code">${escapeHtml(item.channel)}</div>
            </td>
            <td class="font-code text-xs text-slate-500">${item.timestamp.substring(11, 19)}</td>
            <td class="max-w-md">
              <div class="text-slate-900 text-xs mb-1.5 leading-relaxed">${escapeHtml(item.content)}</div>
              <div class="flex flex-wrap">${activeLabels || '<span class="text-xs text-slate-500">-</span>'}</div>
            </td>
            <td class="font-code text-xs text-right text-slate-500">
              ${item.latency_ms.toFixed(1)} ms
            </td>
            <td>
              <span class="badge ${statusClass}">${escapeHtml(item.status)}</span>
            </td>
            <td class="text-center">
              <div class="flex items-center justify-center space-x-1.5">
                ${datasetBtnHtml}
                <button class="btn-dc btn-dc-sm btn-dc-secondary js-open-detail-modal" data-message-id="${item.message_id}" title="Edit">
                  Edit
                </button>
                <button class="btn-dc btn-dc-sm btn-dc-danger js-delete-message" data-message-id="${item.message_id}" title="Hapus Log">
                  ✕
                </button>
              </div>
            </td>
          </tr>
        `;
      })
      .join("");
  } catch (err) {
    console.error("Failed to load audit logs:", err);
  }
}

/**
 * Reload and Synchronize User Grouping Directory (Tab Pengguna)
 */
async function reloadUsersSummary() {
  const container = document.getElementById("user-grouping-list");
  if (!container) return;

  try {
    const res = await fetch("/api/users-summary");
    if (!res.ok) return;
    const users = await res.json();

    // Preserve open accordions by author name
    const openAuthors = new Set();
    document.querySelectorAll(".user-group-card").forEach((card) => {
      const author = card.getAttribute("data-author");
      const body = card.querySelector("[id^='user-messages-']");
      if (body && !body.classList.contains("hidden")) {
        openAuthors.add(author);
      }
    });

    container.innerHTML = users
      .map((u, idx) => {
        const isOpen = openAuthors.has(u.author);
        const chevronStyle = isOpen ? "style=\"transform: rotate(90deg);\"" : "";
        const bodyClass = isOpen ? "" : "hidden";

        const messagesHtml = u.messages
          .map((msg) => {
            let statusBadge = "";
            let reviewButtonsHtml = "";

            if (msg.status === "Menunggu Tinjauan") {
              statusBadge = `<span class="badge badge-warning">Menunggu Tinjauan</span>`;
              reviewButtonsHtml = `
                <button class="btn-dc btn-dc-sm btn-dc-secondary js-open-detail-modal" data-message-id="${msg.message_id}" title="Edit Catatan">Edit Catatan</button>
                <button class="btn-dc btn-dc-sm btn-dc-success js-review-action" data-message-id="${msg.message_id}" data-action="pardon" title="Pulihkan">Pulihkan</button>
                <button class="btn-dc btn-dc-sm btn-dc-warning js-review-action" data-message-id="${msg.message_id}" data-action="warn" title="Peringatan DM Bot">Peringatan</button>
                <button class="btn-dc btn-dc-sm btn-dc-danger js-review-action" data-message-id="${msg.message_id}" data-action="timeout_1h" title="Timeout 1 Jam (Mute Sementara)">Timeout (1 Jam)</button>
                <button class="btn-dc btn-dc-sm btn-dc-danger js-review-action" data-message-id="${msg.message_id}" data-action="kick" title="Keluarkan dari server">Kick</button>
                <button class="btn-dc btn-dc-sm btn-dc-danger js-review-action" data-message-id="${msg.message_id}" data-action="ban" title="Ban (pilih durasi)">Ban</button>
              `;
            } else if (msg.status.includes("Pardon") || msg.status.includes("Dipulihkan")) {
              statusBadge = `<span class="badge badge-positive">${escapeHtml(msg.status)}</span>`;
            } else if (/Ban|Kick|Timeout/.test(msg.status)) {
              statusBadge = `<span class="badge badge-negative">${escapeHtml(msg.status)}</span>`;
            } else {
              statusBadge = `<span class="badge badge-accent">${escapeHtml(msg.status)}</span>`;
            }

            const datasetBtnHtml = msg.in_dataset
              ? `<button class="btn-dc btn-dc-sm btn-dc-secondary opacity-60 cursor-not-allowed" disabled title="Pesan ini sudah ditambahkan ke dataset">✓ Di Dataset</button>`
              : `<button class="btn-dc btn-dc-sm btn-dc-primary js-open-dataset-modal" data-message-id="${msg.message_id}" data-content="${escapeHtml(msg.content)}" data-labels='${JSON.stringify(msg.labels || {})}' title="Tambah ke Dataset">+ Dataset</button>`;

            const actionButtonsHtml = `
              <div class="flex items-center justify-end pt-1.5 border-t border-[var(--dc-border)] gap-1">
                ${datasetBtnHtml}
                ${reviewButtonsHtml}
              </div>
            `;

            return `
              <div class="p-2.5 bg-white rounded border border-[var(--dc-border)] space-y-1.5" id="user-msg-card-${msg.message_id}">
                <div class="flex items-center justify-between text-xs">
                  <span class="text-slate-500 font-code">${escapeHtml(msg.channel)} &bull; ${msg.timestamp.substring(11, 19)}</span>
                  ${statusBadge}
                </div>
                <div class="text-xs text-slate-900 leading-relaxed">
                  "${escapeHtml(msg.content)}"
                </div>
                ${actionButtonsHtml}
                <div class="text-[10px] text-slate-500 pt-1.5 border-t border-slate-100 flex items-center justify-between font-code">
                  <div>
                    Tindakan bot: <strong class="text-slate-800">${escapeHtml(msg.automated_action || msg.status)}</strong>
                  </div>
                  <div class="text-slate-400 num-tabular">
                    Latensi: ${msg.latency_ms.toFixed(1)} ms
                  </div>
                </div>
              </div>
            `;
          })
          .join("");

        return `
          <div class="user-group-card" data-author="${escapeHtml(u.author)}">
            <div class="user-group-header js-toggle-user-accordion" data-target="user-messages-${idx + 1}">
              <div class="flex items-center space-x-3">
                <div class="w-8 h-8 rounded-full bg-[#5865F2] flex items-center justify-center font-bold text-white text-xs">
                  ${escapeHtml(u.author_avatar)}
                </div>
                <div>
                  <div class="flex items-center space-x-2">
                    <span class="font-bold text-slate-900 text-sm">${escapeHtml(u.author)}</span>
                    <span class="badge ${u.risk_badge}">${escapeHtml(u.risk_tier)}</span>
                  </div>
                  <div class="text-[11px] text-slate-500 mt-0.5">
                    <span class="font-code text-slate-500">Saluran: ${escapeHtml(u.channels.join(", "))}</span>
                    <span>&bull;</span>
                    <span class="font-code text-slate-500">${u.total_messages} pesan</span>
                  </div>
                </div>
              </div>

              <div class="flex items-center space-x-3">
                <span class="text-xs font-bold text-slate-900 num-tabular">
                  ${u.violations_count} Pelanggaran
                </span>

                <button class="btn-dc btn-dc-sm btn-dc-danger js-open-user-modal" data-user="${escapeHtml(u.author)}" data-user-id="${escapeHtml(u.author_id)}" data-tier="${escapeHtml(u.risk_tier)}" data-violations="${u.violations_count}">
                  Kelola Sanksi
                </button>
                <span class="accordion-chevron text-xs" ${chevronStyle}>▶</span>
              </div>
            </div>

            <div id="user-messages-${idx + 1}" class="p-3 bg-slate-50 border-t border-[var(--dc-border)] ${bodyClass} space-y-2">
              <div class="text-[10px] uppercase font-bold text-slate-500">Riwayat Pesan Terdeteksi:</div>
              ${messagesHtml}
            </div>
          </div>
        `;
      })
      .join("");
  } catch (err) {
    console.error("Failed to reload users summary:", err);
  }
}

/**
 * Discord CRUD Modals Interactivity
 */
function initDiscordModals() {
  // 1. Open Message Detail & Edit Modal
  document.addEventListener("click", async (e) => {
    const trigger = e.target.closest(".js-open-detail-modal");
    if (!trigger) return;

    const messageId = trigger.getAttribute("data-message-id");
    if (!messageId) return;

    await openMessageDetailModal(messageId);
  });

  // 2. Open User Management Modal
  document.addEventListener("click", (e) => {
    const trigger = e.target.closest(".js-open-user-modal");
    if (!trigger) return;

    const user = trigger.getAttribute("data-user");
    const userId = trigger.getAttribute("data-user-id");
    const tier = trigger.getAttribute("data-tier");
    const violations = trigger.getAttribute("data-violations");

    openUserManageModal(user, userId, tier, violations);
  });

  // 3. Close Modals via Close Button, Cancel Button, or Backdrop Click
  document.addEventListener("click", (e) => {
    if (e.target.closest(".js-close-modal")) {
      closeAllModals();
      return;
    }

    if (e.target.classList.contains("modal-overlay")) {
      closeAllModals();
    }
  });

  // 4. Close via Escape key
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeAllModals();
    }
  });

  // 5. Save Changes in Message Edit Modal
  const saveBtn = document.getElementById("modal-save-btn");
  if (saveBtn) {
    saveBtn.addEventListener("click", async () => {
      if (!currentEditMessageId) return;

      const statusSelect = document.getElementById("modal-edit-status");
      const notesText = document.getElementById("modal-edit-notes");

      const originalText = saveBtn.innerText;
      saveBtn.innerText = "Menyimpan...";
      saveBtn.disabled = true;

      try {
        const res = await fetch(`/api/messages/${currentEditMessageId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            status: statusSelect ? statusSelect.value : "Menunggu Tinjauan",
            admin_notes: notesText ? notesText.value : "",
          }),
        });

        if (!res.ok) {
          const err = await res.json();
          alert(`Gagal menyimpan: ${err.error || "Kesalahan server"}`);
          saveBtn.innerText = originalText;
          saveBtn.disabled = false;
          return;
        }

        // If message was marked resolved, remove from review queue card
        const flaggedCard = document.getElementById(`flagged-card-${currentEditMessageId}`);
        if (flaggedCard && statusSelect && statusSelect.value !== "Menunggu Tinjauan") {
          flaggedCard.remove();
          updateFlaggedCount();
        }

        closeAllModals();
        showNotice(`Perubahan status pesan ${currentEditMessageId} berhasil disimpan!`, "success");
        reloadAuditLogs();
        reloadUsersSummary();
      } catch (err) {
        console.error("Save error:", err);
        alert("Koneksi gagal saat menyimpan perubahan pesan.");
      } finally {
        saveBtn.innerText = originalText;
        saveBtn.disabled = false;
      }
    });
  }

  // 6. Delete Message via Modal Delete Button
  const modalDeleteBtn = document.getElementById("modal-delete-btn");
  if (modalDeleteBtn) {
    modalDeleteBtn.addEventListener("click", async () => {
      if (!currentEditMessageId) return;
      await executeDeleteMessage(currentEditMessageId);
    });
  }

  // 7. Delete Message via Table Row Delete Button
  document.addEventListener("click", async (e) => {
    const deleteBtn = e.target.closest(".js-delete-message");
    if (!deleteBtn) return;

    const messageId = deleteBtn.getAttribute("data-message-id");
    if (!messageId) return;

    await executeDeleteMessage(messageId);
  });

  // 8. User Sanction Execution
  const applyUserBtn = document.getElementById("modal-user-apply-btn");
  if (applyUserBtn) {
    applyUserBtn.addEventListener("click", () => {
      if (!currentUserTarget) return;

      const actionSelect = document.getElementById("modal-user-action-select");
      const actionValue = actionSelect ? actionSelect.value : "warn";
      const actionText = actionSelect ? actionSelect.options[actionSelect.selectedIndex].text : "Sanksi";
      const userDisplay = currentUserTarget;
      const userId = currentUserId;
      const reason = (document.getElementById("modal-user-action-reason")?.value || "").trim();

      if (!userId) {
        alert("ID pengguna tidak ditemukan untuk akun ini.");
        return;
      }

      openConfirmModal({
        title: `Konfirmasi Tindakan: ${actionText}`,
        message: `Apakah Anda yakin ingin menerapkan "${actionText}" untuk ${userDisplay}?`,
        quote: userDisplay,
        subtext: CONFIRM_ACTIONS[actionValue]?.subtext || "Tindakan akan langsung diterapkan ke akun pengguna di server.",
        confirmText: "Eksekusi Tindakan",
        confirmClass: actionValue === "pardon" ? "btn-dc-success" : actionValue === "warn" ? "btn-dc-warning" : "btn-dc-danger",
        durations: CONFIRM_ACTIONS[actionValue]?.durations || null,
        onConfirm: async (durationMinutes) => {
          try {
            const res = await fetch("/api/actions/user", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                user_id: userId,
                action: actionValue,
                duration_minutes: durationMinutes,
                reason: reason,
              }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
              alert(`Gagal: ${data.error || "Terjadi kesalahan"}`);
              return;
            }

            closeAllModals();
            document.querySelectorAll(".flagged-item-card").forEach((card) => {
              const jump = card.querySelector(".js-jump-to-user");
              if (jump && jump.getAttribute("data-author") === userDisplay) card.remove();
            });
            updateFlaggedCount();
            showNotice(data.discord_message || `Tindakan "${actionText}" diterapkan untuk ${userDisplay}.`, "success");
            reloadAuditLogs();
            reloadUsersSummary();
          } catch (err) {
            console.error("User action error:", err);
            alert("Koneksi gagal saat menjalankan tindakan.");
          }
        },
      });
    });
  }
}

/**
 * Active Learning / Add to Dataset Modal Handler
 * Preserves raw text (read-only) and exports to 13-column IndoBERT format
 */
function initDatasetModal() {
  const TAXONOMY_KEYS = [
    "HS", "Abusive", "HS_Individual", "HS_Group",
    "HS_Religion", "HS_Race", "HS_Physical", "HS_Gender",
    "HS_Other", "HS_Weak", "HS_Moderate", "HS_Strong",
  ];

  // 1. Open Dataset Modal
  document.addEventListener("click", (e) => {
    const trigger = e.target.closest(".js-open-dataset-modal");
    if (!trigger) return;

    let text = trigger.getAttribute("data-content") || "";
    // If text was JSON-stringified or escaped
    if (text.startsWith('"') && text.endsWith('"') && text.length >= 2) {
      try {
        text = JSON.parse(text);
      } catch (_) {}
    }

    // Fallback: extract quote if data-content wasn't populated
    if (!text) {
      const card = trigger.closest(".flagged-item-card, [id^='user-msg-card-'], tr[id^='audit-row-']");
      if (card) {
        const quoteEl = card.querySelector(".dc-quote-box, .leading-relaxed");
        if (quoteEl) {
          text = quoteEl.textContent.trim().replace(/^["']|["']$/g, "");
        }
      }
    }

    const msgId = trigger.getAttribute("data-message-id") || "";
    let labels = {};
    const labelsAttr = trigger.getAttribute("data-labels");
    if (labelsAttr) {
      try {
        labels = JSON.parse(labelsAttr);
      } catch (err) {
        console.warn("Could not parse labels attribute:", err);
      }
    }

    const textEl = document.getElementById("dataset-modal-text");
    if (textEl) {
      textEl.textContent = text;
    }

    const msgIdInput = document.getElementById("dataset-modal-msg-id");
    if (msgIdInput) {
      msgIdInput.value = msgId;
    }

    // Pre-populate checkboxes according to model prediction
    TAXONOMY_KEYS.forEach((key) => {
      const chk = document.getElementById(`dataset-lbl-${key}`);
      if (chk) {
        chk.checked = !!labels[key];
      }
    });

    const modal = document.getElementById("modal-add-dataset");
    if (modal) {
      modal.classList.remove("hidden");
    }
  });

  // 2. Quick Reset / Uncheck All (for False Positive active learning)
  const uncheckAllBtn = document.getElementById("btn-dataset-uncheck-all");
  if (uncheckAllBtn) {
    uncheckAllBtn.addEventListener("click", () => {
      TAXONOMY_KEYS.forEach((key) => {
        const chk = document.getElementById(`dataset-lbl-${key}`);
        if (chk) chk.checked = false;
      });
      showNotice("Semua label dinolkan (Aman / False Positive).", "info");
    });
  }

  // 3. Save to Dataset Contribution Table
  const saveBtn = document.getElementById("dataset-modal-save-btn");
  if (saveBtn) {
    saveBtn.addEventListener("click", async () => {
      const textEl = document.getElementById("dataset-modal-text");
      const text = textEl ? textEl.textContent.trim() : "";
      if (!text || text === "-") {
        alert("Teks kalimat tidak boleh kosong.");
        return;
      }

      const msgIdInput = document.getElementById("dataset-modal-msg-id");
      const msgId = msgIdInput && msgIdInput.value ? parseInt(msgIdInput.value, 10) : null;

      const labels = {};
      TAXONOMY_KEYS.forEach((key) => {
        const chk = document.getElementById(`dataset-lbl-${key}`);
        labels[key] = chk && chk.checked ? 1 : 0;
      });

      const originalText = saveBtn.innerHTML;
      saveBtn.innerHTML = "Menyimpan...";
      saveBtn.disabled = true;

      try {
        const res = await fetch("/api/dataset/add", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text: text,
            labels: labels,
            source_log_id: isNaN(msgId) ? null : msgId,
          }),
        });

        if (!res.ok) {
          const err = await res.json();
          if (res.status === 409) {
            showNotice(err.error || "Pesan ini sudah pernah ditambahkan ke dataset.", "danger");
            const curMsgId = msgIdInput ? msgIdInput.value : "";
            if (curMsgId) {
              document.querySelectorAll(`.js-open-dataset-modal[data-message-id="${curMsgId}"]`).forEach((btn) => {
                const isSm = btn.classList.contains("btn-dc-sm");
                btn.outerHTML = `<button class="btn-dc ${isSm ? "btn-dc-sm" : ""} btn-dc-secondary opacity-60 cursor-not-allowed" disabled title="Pesan ini sudah ditambahkan ke dataset">✓ Di Dataset</button>`;
              });
            }
            const modal = document.getElementById("modal-add-dataset");
            if (modal) modal.classList.add("hidden");
            return;
          }
          alert(`Gagal menyimpan ke dataset: ${err.error || "Kesalahan server"}`);
          return;
        }

        const data = await res.json();
        const badge = document.getElementById("badge-dataset-count");
        if (badge && data.total !== undefined) {
          badge.textContent = data.total;
        }

        // Tandai tombol sebagai sudah ditambahkan (✓ Di Dataset) di seluruh tab
        const curMsgId = msgIdInput ? msgIdInput.value : "";
        if (curMsgId) {
          document.querySelectorAll(`.js-open-dataset-modal[data-message-id="${curMsgId}"]`).forEach((btn) => {
            const isSm = btn.classList.contains("btn-dc-sm");
            btn.outerHTML = `<button class="btn-dc ${isSm ? "btn-dc-sm" : ""} btn-dc-secondary opacity-60 cursor-not-allowed" disabled title="Pesan ini sudah ditambahkan ke dataset">✓ Di Dataset</button>`;
          });
        }

        showNotice(`Kalimat berhasil disimpan ke dataset (Total: ${data.total})!`, "success");

        const modal = document.getElementById("modal-add-dataset");
        if (modal) {
          modal.classList.add("hidden");
        }
      } catch (err) {
        console.error("Error saving dataset:", err);
        alert("Terjadi kesalahan koneksi saat menyimpan ke dataset.");
      } finally {
        saveBtn.innerHTML = originalText;
        saveBtn.disabled = false;
      }
    });
  }
}

/**
 * Jump to User Profile in Tab Pengguna from Flagged Message Card
 */
function initJumpToUser() {
  document.addEventListener("click", (e) => {
    const jumpBtn = e.target.closest(".js-jump-to-user");
    if (!jumpBtn) return;

    e.preventDefault();
    const targetAuthor = jumpBtn.getAttribute("data-author");
    if (!targetAuthor) return;

    // 1. Switch active sidebar item and tab to Tab Pengguna
    const usersTabNav = document.querySelector('.js-sidebar-nav[data-tab="tab-users"]');
    if (usersTabNav) {
      usersTabNav.click();
    }

    // 2. Find the user card matching data-author
    const userCards = document.querySelectorAll(".user-group-card");
    let matchedCard = null;
    userCards.forEach((card) => {
      const cardAuthor = card.getAttribute("data-author");
      if (
        cardAuthor === targetAuthor ||
        (cardAuthor && targetAuthor && (cardAuthor.includes(targetAuthor) || targetAuthor.includes(cardAuthor)))
      ) {
        matchedCard = card;
      }
    });

    if (matchedCard) {
      // Open accordion if closed
      const accordionHeader = matchedCard.querySelector(".js-toggle-user-accordion");
      const targetBodyId = accordionHeader?.getAttribute("data-target");
      const body = targetBodyId ? document.getElementById(targetBodyId) : null;
      if (body && body.classList.contains("hidden")) {
        accordionHeader.click();
      }

      // Scroll smoothly to the matched card and highlight
      setTimeout(() => {
        matchedCard.scrollIntoView({ behavior: "smooth", block: "center" });
        matchedCard.classList.add("ring-2", "ring-[#5865F2]", "transition-all", "duration-300");
        setTimeout(() => {
          matchedCard.classList.remove("ring-2", "ring-[#5865F2]");
        }, 2500);
      }, 100);
    }
  });
}

/**
 * Open and Populate Message Detail & Edit Modal
 */
async function openMessageDetailModal(messageId) {
  currentEditMessageId = messageId;
  const modal = document.getElementById("modal-edit-message");
  if (!modal) return;

  // Placeholder while loading
  document.getElementById("modal-msg-id").innerText = `ID: ${messageId}`;
  document.getElementById("modal-msg-content").innerText = "Memuat data pesan...";
  document.getElementById("modal-msg-author-channel").innerText = "...";
  document.getElementById("modal-msg-latency").innerText = "Latensi: ...";
  document.getElementById("modal-msg-labels").innerHTML = `<span class="text-xs text-slate-500">Memuat taksonomi...</span>`;

  modal.classList.remove("hidden");

  try {
    const res = await fetch(`/api/messages/${messageId}`);
    if (!res.ok) {
      showNotice(`Gagal mengambil detail pesan ${messageId}`, "danger");
      closeAllModals();
      return;
    }

    const data = await res.json();
    document.getElementById("modal-msg-content").innerText = `"${data.content}"`;
    const authorDisplay = data.author.startsWith("@") ? data.author : `@${data.author}`;
    const channelDisplay = data.channel.startsWith("#") ? data.channel : `#${data.channel}`;
    document.getElementById("modal-msg-author-channel").innerText = `${authorDisplay} di ${channelDisplay}`;
    document.getElementById("modal-msg-latency").innerText = `Latensi: ${data.latency_ms.toFixed(1)} ms`;

    // Render 12-taxonomy label badges
    const labelsContainer = document.getElementById("modal-msg-labels");
    if (labelsContainer && data.labels) {
      const activeLabels = Object.entries(data.labels)
        .filter(([_, val]) => val === true)
        .map(([lbl, _]) => `<span class="badge badge-accent font-code">${escapeHtml(lbl)}</span>`);

      labelsContainer.innerHTML = activeLabels.length > 0
        ? activeLabels.join(" ")
        : `<span class="text-xs text-slate-500">Tidak terdeteksi pelanggaran eksplisit</span>`;
    }

    // Set status select value
    const statusSelect = document.getElementById("modal-edit-status");
    if (statusSelect) {
      const status = data.status || "Menunggu Tinjauan";
      if (![...statusSelect.options].some((o) => o.value === status)) {
        statusSelect.add(new Option(status, status));
      }
      statusSelect.value = status;
    }

    // Set admin notes
    const notesText = document.getElementById("modal-edit-notes");
    if (notesText) {
      notesText.value = data.admin_notes || "";
    }
  } catch (err) {
    console.error("Failed to load message detail:", err);
    showNotice("Gagal menghubungi server untuk memuat detail pesan.", "danger");
  }
}

/**
 * Open and Populate User Management Modal
 */
function openUserManageModal(user, userId, tier, violations) {
  currentUserTarget = user;
  currentUserId = userId;
  const modal = document.getElementById("modal-user-manage");
  if (!modal) return;

  document.getElementById("modal-user-handle").innerText = user;
  document.getElementById("modal-user-tier").innerText = tier || "Moderate";
  document.getElementById("modal-user-violations").innerText = `${violations || 1} Pelanggaran`;

  const reasonText = document.getElementById("modal-user-action-reason");
  if (reasonText) reasonText.value = "";

  modal.classList.remove("hidden");
}

/**
 * Discord Light Mode Confirmation Modal Helper
 */
function openConfirmModal({
  title = "Konfirmasi Tindakan",
  message = "Apakah Anda yakin ingin melanjutkan tindakan ini?",
  quote = null,
  subtext = "Tindakan ini tidak dapat dibatalkan.",
  confirmText = "Konfirmasi",
  confirmClass = "btn-dc-danger",
  durations = null,
  onConfirm = null,
} = {}) {
  const modal = document.getElementById("modal-confirm");
  if (!modal) return;

  const titleEl = document.getElementById("modal-confirm-title");
  if (titleEl) titleEl.innerText = title;

  const msgEl = document.getElementById("modal-confirm-message");
  if (msgEl) msgEl.innerText = message;

  const quoteBox = document.getElementById("modal-confirm-quote-box");
  const quoteSpan = document.getElementById("modal-confirm-quote");
  if (quote && quoteBox && quoteSpan) {
    quoteSpan.innerText = quote;
    quoteBox.classList.remove("hidden");
  } else if (quoteBox) {
    quoteBox.classList.add("hidden");
  }

  const subEl = document.getElementById("modal-confirm-subtext");
  if (subEl) subEl.innerText = subtext;

  const durationWrap = document.getElementById("modal-confirm-duration-wrap");
  const durationSelect = document.getElementById("modal-confirm-duration");
  if (durationWrap && durationSelect) {
    if (durations) {
      durationSelect.innerHTML = durations.map((d) => `<option value="${d.value}">${escapeHtml(d.label)}</option>`).join("");
      durationWrap.classList.remove("hidden");
    } else {
      durationWrap.classList.add("hidden");
    }
  }

  const confirmBtn = document.getElementById("modal-confirm-btn");
  if (confirmBtn) {
    confirmBtn.innerText = confirmText;
    confirmBtn.className = `btn-dc ${confirmClass}`;
    confirmBtn.disabled = false;
    confirmBtn.onclick = async () => {
      if (onConfirm) {
        confirmBtn.disabled = true;
        const oldText = confirmBtn.innerText;
        confirmBtn.innerText = "Memproses...";
        try {
          await onConfirm(durations ? Number(durationSelect.value) : undefined);
        } finally {
          confirmBtn.disabled = false;
          confirmBtn.innerText = oldText;
          modal.classList.add("hidden");
        }
      } else {
        modal.classList.add("hidden");
      }
    };
  }

  modal.classList.remove("hidden");
}

/**
 * Close all active modal dialogs
 */
function closeAllModals() {
  document.querySelectorAll(".modal-overlay").forEach((m) => m.classList.add("hidden"));
  currentEditMessageId = null;
  currentUserTarget = null;
  currentUserId = null;
}

/**
 * Execute DELETE message action with Discord Confirmation Card
 */
async function executeDeleteMessage(messageId) {
  openConfirmModal({
    title: "Hapus Pesan dari Log",
    message: `Apakah Anda yakin ingin menghapus data pesan ini dari log admin?`,
    quote: `ID Pesan: ${messageId}`,
    subtext: "Tindakan ini permanen dan tidak dapat dibatalkan.",
    confirmText: "Hapus",
    confirmClass: "btn-dc-danger",
    onConfirm: async () => {
      try {
        const res = await fetch(`/api/messages/${messageId}`, {
          method: "DELETE",
        });

        if (!res.ok) {
          const err = await res.json();
          alert(`Gagal menghapus pesan: ${err.error || "Kesalahan server"}`);
          return;
        }

        closeAllModals();

        // Smoothly remove row from audit table
        const row = document.getElementById(`audit-row-${messageId}`);
        if (row) {
          row.style.transition = "opacity 0.25s ease, transform 0.25s ease";
          row.style.opacity = "0";
          row.style.transform = "scale(0.98)";
          setTimeout(() => row.remove(), 250);
        }

        // Smoothly remove card from flagged queue if present
        const card = document.getElementById(`flagged-card-${messageId}`);
        if (card) {
          card.style.transition = "opacity 0.25s ease, transform 0.25s ease";
          card.style.opacity = "0";
          card.style.transform = "scale(0.98)";
          setTimeout(() => {
            card.remove();
            updateFlaggedCount();
          }, 250);
        }

        showNotice(`Pesan ${messageId} berhasil dihapus dari log admin.`, "info");
        reloadAuditLogs();
        reloadUsersSummary();
      } catch (err) {
        console.error("Delete error:", err);
        alert("Koneksi gagal saat menghapus pesan dari server.");
      }
    },
  });
}

/**
 * Toast Notice Notification in Academic Style
 */
function showNotice(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const notice = document.createElement("div");
  notice.className = "bg-slate-900 text-white text-xs px-3.5 py-2.5 rounded-lg shadow-xl flex items-center justify-between border border-slate-700 space-x-2";
  
  const dotColor = type === "danger" 
    ? "bg-[#ed4245]" 
    : type === "success" 
    ? "bg-[#23a55a]" 
    : "bg-[#5865F2]";

  notice.innerHTML = `<span class="flex items-center"><span class="w-2 h-2 rounded-full mr-2.5 inline-block ${dotColor}"></span>${escapeHtml(message)}</span>`;

  container.appendChild(notice);
  setTimeout(() => {
    notice.style.transition = "opacity 0.25s ease, transform 0.25s ease";
    notice.style.opacity = "0";
    notice.style.transform = "translateY(4px)";
    setTimeout(() => notice.remove(), 250);
  }, 3500);
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
