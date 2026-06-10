// Retrieval upload + search test UI.
const $ = (id) => document.getElementById(id);

function log(el, line, cls) {
  el.style.display = "block";
  const span = document.createElement("div");
  if (cls) span.className = cls;
  span.textContent = line;
  el.appendChild(span);
  el.scrollTop = el.scrollHeight;
}

// ── Drag-and-drop upload zone ────────────────────────────────────────────────
const dropzone = $("dropzone");
const pdfInput = $("pdf");

function showSelectedFile() {
  const f = pdfInput.files[0];
  if (f) {
    $("dzFileName").textContent = f.name;
    $("dzFile").style.display = "flex";
  } else {
    $("dzFile").style.display = "none";
  }
}

dropzone.addEventListener("click", () => pdfInput.click());
dropzone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pdfInput.click(); }
});
pdfInput.addEventListener("change", showSelectedFile);

["dragenter", "dragover"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add("dragover"); })
);
["dragleave", "drop"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.remove("dragover"); })
);
dropzone.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files && e.dataTransfer.files[0];
  if (!file) return;
  if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
    log($("status"), "Only PDF files are supported.", "err");
    return;
  }
  pdfInput.files = e.dataTransfer.files;
  showSelectedFile();
});

// ── Upload & ingest ──────────────────────────────────────────────────────────
$("uploadBtn").addEventListener("click", async () => {
  const f = pdfInput.files[0];
  const status = $("status");
  status.innerHTML = "";
  if (!f) { log(status, "Choose or drop a PDF first.", "err"); return; }
  const btn = $("uploadBtn");
  btn.disabled = true;
  log(status, `> uploading ${f.name} …`, "ok");
  const fd = new FormData();
  fd.append("file", f);
  if ($("book").value.trim()) fd.append("book_title", $("book").value.trim());
  try {
    const r = await fetch("/api/ingest", { method: "POST", body: fd });
    const j = await r.json();
    if (!r.ok) { log(status, "ERROR: " + (j.detail || r.status), "err"); return; }
    log(status, "OK: " + j.message, "ok");
    log(status, `book="${j.book_title}"  pages=${j.pages}  chunks=${j.chunks}  upserted=${j.upserted}`);
  } catch (e) { log(status, "ERROR: " + e, "err"); }
  finally { btn.disabled = false; }
});

// ── Test search (raw Pinecone retrieval) ─────────────────────────────────────
$("searchBtn").addEventListener("click", async () => {
  const q = $("q").value.trim();
  const book = $("searchBook").value.trim();
  const out = $("searchOut");
  out.innerHTML = "";
  if (!q) { log(out, "Enter a query.", "err"); return; }
  const payload = { query: q };
  if (book) payload.book = book;
  log(out, `> POST /api/search ${JSON.stringify(payload)}`, "ok");
  try {
    const r = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!r.ok) { log(out, "HTTP " + r.status, "err"); return; }
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const chunk = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const ev = (chunk.match(/event: (.*)/) || [])[1] || "";
        const data = (chunk.match(/data: (.*)/) || [])[1] || "";
        const cls = ev === "error" ? "err" : (ev === "sources" || ev === "clarification") ? "ok" : "";
        log(out, `[${ev}] ${data}`, cls);
      }
    }
  } catch (e) { log(out, "ERROR: " + e, "err"); }
});
