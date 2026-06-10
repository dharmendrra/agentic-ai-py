// Agent chat UI — thread, sidebar, toggles, conversation state.
const $ = (id) => document.getElementById(id);

let conversationId = null;
let useWeb = false;
let useLibrary = false;

const ICONS = {
  book: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>',
  extlink: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></svg>',
  help: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/></svg>',
  msg: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
  trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>',
};

const SOURCE_LABELS = { pdf: "from My Library", web: "from Web", mongo: "from Database", model: "model's own knowledge" };
function hostOf(u) { try { return new URL(u).hostname.replace(/^www\./, ""); } catch (e) { return u; } }

function addBubble(role, text, opts = {}) {
  const div = document.createElement("div");
  if (opts.clarify) {
    div.className = "bubble clarify";
    div.innerHTML = ICONS.help + "<div></div>";
    div.lastChild.textContent = text;
  } else {
    div.className = "bubble " + role;
    div.textContent = text;
  }

  // Provenance + clickable web citations on every answer (not on clarifications).
  if (role === "assistant" && !opts.clarify) {
    const wrap = document.createElement("div");
    wrap.className = "tags";
    const srcs = (opts.sources && opts.sources.length) ? opts.sources : ["model"];
    srcs.forEach((s) => {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.innerHTML = (s === "web" ? ICONS.extlink : ICONS.book) + "<span></span>";
      chip.lastChild.textContent = SOURCE_LABELS[s] || s;
      wrap.appendChild(chip);
    });
    (opts.citations || []).forEach((c) => {
      const a = document.createElement("a");
      a.className = "chip";
      a.href = c.url; a.target = "_blank"; a.rel = "noopener noreferrer";
      a.title = c.title || c.url;
      a.style.color = "var(--py-blue)";
      a.style.textDecoration = "none";
      a.innerHTML = ICONS.extlink + "<span></span>";
      a.lastChild.textContent = hostOf(c.url);
      wrap.appendChild(a);
    });
    if (wrap.children.length) div.appendChild(wrap);
  }
  $("thread").appendChild(div);
  div.scrollIntoView({ behavior: "smooth", block: "end" });
}

function showError(msg) {
  $("errorText").textContent = msg;
  $("errorBanner").style.display = "flex";
}
function clearError() { $("errorBanner").style.display = "none"; }

function setLoading(on) {
  $("loading").style.display = on ? "inline-flex" : "none";
  $("loadingText").textContent = useLibrary ? "Searching My Library…" : (useWeb ? "Searching the web…" : "Thinking…");
  $("sendBtn").disabled = on;
}

async function send() {
  const q = $("query").value.trim();
  if (!q) return;
  clearError();
  addBubble("user", q);
  $("query").value = "";
  setLoading(true);
  try {
    const r = await fetch("/api/agent/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: q,
        conversation_id: conversationId,
        use_web: useWeb,
        use_library: useLibrary,
      }),
    });
    const j = await r.json();
    if (!r.ok) { showError(j.detail || ("HTTP " + r.status)); return; }
    conversationId = j.conversation_id;
    addBubble("assistant", j.answer, {
      clarify: j.needs_clarification,
      sources: j.sources,
      citations: j.citations,
    });
    loadConversations();
  } catch (e) {
    showError(String(e));
  } finally {
    setLoading(false);
  }
}

async function loadConversations() {
  try {
    const r = await fetch("/api/conversations");
    const list = await r.json();
    const el = $("convList");
    el.innerHTML = "";
    list.forEach((c) => {
      const item = document.createElement("div");
      item.className = "conv-item" + (c._id === conversationId ? " active" : "");
      const title = document.createElement("span");
      title.className = "title";
      title.textContent = c.title || "Untitled";
      const del = document.createElement("button");
      del.className = "del";
      del.title = "Delete";
      del.innerHTML = ICONS.trash;
      del.addEventListener("click", (ev) => { ev.stopPropagation(); deleteConv(c._id); });
      item.innerHTML = ICONS.msg;
      item.appendChild(title);
      item.appendChild(del);
      item.addEventListener("click", () => openConversation(c._id));
      el.appendChild(item);
    });
  } catch (e) { /* sidebar best-effort */ }
}

async function openConversation(id) {
  try {
    const r = await fetch("/api/conversations/" + id);
    const j = await r.json();
    conversationId = id;
    $("thread").innerHTML = "";
    (j.messages || []).forEach((m) => addBubble(m.role, m.content, { sources: m.sources, citations: m.citations }));
    loadConversations();
  } catch (e) { showError(String(e)); }
}

async function deleteConv(id) {
  try {
    await fetch("/api/conversations/" + id, { method: "DELETE" });
    if (id === conversationId) newChat();
    loadConversations();
  } catch (e) { showError(String(e)); }
}

function newChat() {
  conversationId = null;
  $("thread").innerHTML = "";
  clearError();
  loadConversations();
}

$("sendBtn").addEventListener("click", send);
$("query").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
});
$("newChatBtn").addEventListener("click", newChat);
$("webToggle").addEventListener("click", () => {
  useWeb = !useWeb; $("webToggle").classList.toggle("active", useWeb);
});
$("libToggle").addEventListener("click", () => {
  useLibrary = !useLibrary; $("libToggle").classList.toggle("active", useLibrary);
});

loadConversations();
