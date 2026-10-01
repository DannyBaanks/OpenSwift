import "./style.css";
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";

const app = document.querySelector("#app");
app.innerHTML = `
<header>
  <div class="brand"><span class="brand-mark">O</span><div><strong>OpenSwift</strong><small>SwiftUI sketch studio</small></div></div>
  <div class="toolbar">
    <button id="open" class="button-quiet"><span class="button-icon">▱</span> Open project</button>
    <span class="toolbar-rule"></span>
    <button id="run" class="primary" disabled><span class="button-icon">▶</span> Run preview <kbd>Ctrl+Enter</kbd></button>
    <button id="save" class="button-quiet" disabled>Save <kbd>Ctrl+S</kbd></button>
  </div>
  <label class="search-box"><span>⌕</span><input id="search" placeholder="Find a Swift file" /><kbd>Ctrl+K</kbd></label>
</header>
<main>
  <aside id="files"><div class="section-heading"><div><span class="eyebrow">WORKSPACE</span><h2>Project files</h2></div><span id="filecount" class="count-badge">0</span></div><div id="list"></div><div id="files-empty" class="sidebar-empty"><span class="empty-glyph">⌘</span><strong>No Swift files yet</strong><span>Open a project folder to browse its Swift views.</span></div></aside>
  <section id="center">
    <div id="tab"><span class="swift-badge">S</span><span id="filename">No file selected</span><span id="dirty" class="dirty-state">Saved</span></div>
    <div id="editor">
      <pre id="hi"></pre>
      <textarea id="code" spellcheck="false" placeholder="Your Swift source will appear here…"></textarea>
      <div id="editor-welcome" class="editor-welcome"><div class="welcome-icon">⌘</div><p class="eyebrow">A SMALLER LOOP FOR UI IDEAS</p><h1>One screen at a time.</h1><p>Open a Swift file to sketch its layout, then compare ideas in the preview.</p><button id="welcome-open" class="button-quiet">Open a project</button><span class="welcome-note">A sketch, not a Swift build.</span></div>
    </div>
    <div id="dock">
      <div class="dock-top"><div class="tabs">
        <button data-pane="debug" class="on">Sketch tree</button>
        <button data-pane="output">Output</button>
        <button data-pane="problems">Problems</button>
        <button data-pane="console">Console</button>
      </div><span class="dock-caption">PREVIEW INSPECTOR</span></div>
      <pre id="dockpre">Open a file and run a preview to inspect its sketch tree.</pre>
    </div>
  </section>
  <aside id="stage">
    <div class="preview-heading"><div><span class="eyebrow">CANVAS</span><h2>Preview</h2></div><span class="preview-status"><i></i> Approximate</span></div>
    <label class="device-picker"><span>Device frame</span><select id="device"></select></label>
    <div class="phone-stage"><div id="phone"><div id="screen"><div id="empty"><span class="empty-glyph">◉</span><strong>Your preview lives here</strong><span>Open a Swift file and run it to see the sketch.</span></div></div></div></div>
    <div class="preview-footnote"><span class="tiny-dot"></span> Static layout preview <span>·</span> no Swift runtime</div>
  </aside>
</main>
<footer><div class="footer-project"><span class="tiny-dot"></span><span id="rootlabel">No project open</span></div><div class="footer-meta"><span>OpenSwift Studio</span><span>·</span><span>Local workspace</span></div></footer>
`;

const code = document.querySelector("#code");
const list = document.querySelector("#list");
const filename = document.querySelector("#filename");
const screen = document.querySelector("#screen");
const dockpre = document.querySelector("#dockpre");
const editorWelcome = document.querySelector("#editor-welcome");
const filesEmpty = document.querySelector("#files-empty");
const DEVICES = [
  ["iphone-11", "iPhone 11"],
  ["iphone-12", "iPhone 12"],
  ["iphone-13", "iPhone 13"],
  ["iphone-14", "iPhone 14"],
  ["iphone-14-plus", "iPhone 14 Plus"],
  ["iphone-14-pro", "iPhone 14 Pro · isla"],
  ["iphone-15", "iPhone 15"],
  ["iphone-16", "iPhone 16"],
  ["iphone-16-pro", "iPhone 16 Pro"],
];
const deviceSelect = document.querySelector("#device");
DEVICES.forEach(([id, name]) => {
  const opt = document.createElement("option");
  opt.value = id;
  opt.textContent = name;
  deviceSelect.appendChild(opt);
});
deviceSelect.value = "iphone-14";

let current = "";
let saved = "";
let files = [];
let openFolders = new Set();
let seeded = false;
let pane = "debug";
const panes = {
  debug: "No Swift runtime.\nBreakpoints are not executed.\nRun shows the sketch tree here.",
  output: "",
  problems: "",
  console: "",
};

function esc(text) {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function paint(source, tokens) {
  const hi = document.querySelector("#hi");
  if (!tokens || !tokens.length) { hi.textContent = source + "\n"; return; }
  let html = "";
  let cursor = 0;
  for (const tok of tokens) {
    if (tok.start > cursor) html += esc(source.slice(cursor, tok.start));
    const slice = source.slice(tok.start, tok.end);
    let cls = tok.type;
    if (tok.type === "identifier" && /^[A-Z@]/.test(slice)) cls = "type";
    html += `<span class="${cls}">${esc(slice)}</span>`;
    cursor = tok.end;
  }
  html += esc(source.slice(cursor));
  hi.innerHTML = html + "\n";
}
let highlightTimer = 0;
function scheduleHighlight() {
  clearTimeout(highlightTimer);
  highlightTimer = setTimeout(async () => {
    try {
      const tokens = await invoke("highlight_source", { source: code.value });
      paint(code.value, tokens);
    } catch (err) {
      paint(code.value, []);
      log("problems", String(err));
    }
  }, 80);
}
function show() { dockpre.textContent = panes[pane]; }
function log(which, line) {
  panes[which] = (panes[which] ? panes[which] + "\n" : "") + line;
  if (pane === which) show();
}
function treeText(node, depth) {
  if (!node) return "";
  const label = node.text ? ` "${node.text}"` : "";
  return `${"  ".repeat(depth)}${node.kind}${label}\n` + (node.children || []).map((c) => treeText(c, depth + 1)).join("");
}
function treeFrom(paths) {
  const root = { dirs: new Map(), files: [] };
  const q = document.querySelector("#search").value.toLowerCase();
  paths.filter((p) => p.toLowerCase().includes(q)).forEach((p) => {
    const parts = p.split("/");
    let node = root;
    for (let i = 0; i < parts.length - 1; i++) {
      const key = parts.slice(0, i + 1).join("/");
      if (!node.dirs.has(key)) node.dirs.set(key, { name: parts[i], dirs: new Map(), files: [] });
      node = node.dirs.get(key);
    }
    node.files.push({ name: parts[parts.length - 1], path: p });
  });
  return root;
}
function addTree(node, depth) {
  node.dirs.forEach((dir, key) => {
    const open = openFolders.has(key) || document.querySelector("#search").value !== "";
    const row = document.createElement("button");
    row.className = "folder";
    row.style.paddingLeft = (6 + depth * 14) + "px";
    const chev = document.createElement("span");
    chev.className = "chev";
    chev.textContent = open ? "▾" : "▸";
    const name = document.createElement("span");
    name.textContent = dir.name;
    row.append(chev, name);
    row.onclick = () => {
      if (openFolders.has(key)) openFolders.delete(key);
      else openFolders.add(key);
      drawFiles();
    };
    list.appendChild(row);
    if (open) addTree(dir, depth + 1);
  });
  node.files.forEach((file) => {
    const row = document.createElement("button");
    row.className = "file" + (file.path === current ? " on" : "");
    row.style.paddingLeft = (8 + (depth + 1) * 14) + "px";
    const dirty = file.path === current && code.value !== saved;
    const icon = document.createElement("span");
    icon.className = "ficon";
    icon.textContent = "S";
    const name = document.createElement("span");
    name.textContent = file.name;
    row.append(icon, name);
    if (dirty) {
      const mark = document.createElement("em");
      mark.className = "mark";
      mark.textContent = "M";
      row.appendChild(mark);
    }
    row.onclick = () => openFile(file.path);
    list.appendChild(row);
  });
}
function drawFiles() {
  list.innerHTML = "";
  addTree(treeFrom(files), 0);
  document.querySelector("#filecount").textContent = String(files.length);
  filesEmpty.hidden = files.length > 0;
}
async function refresh() {
  const info = await invoke("project_info");
  document.querySelector("#rootlabel").textContent = info.root || "No project";
  files = info.files || [];
  editorWelcome.hidden = Boolean(current);
  if (!seeded) {
    files.forEach((p) => {
      const parts = p.split("/");
      for (let i = 1; i < parts.length; i++) openFolders.add(parts.slice(0, i).join("/"));
    });
    seeded = true;
  }
  drawFiles();
}
async function openFile(path) {
  const text = await invoke("read_source", { path });
  current = path;
  saved = text;
  code.value = text;
  paint(text, []);
  scheduleHighlight();
  filename.textContent = path;
  editorWelcome.hidden = true;
  document.querySelector("#dirty").textContent = "Saved";
  document.querySelector("#dirty").classList.remove("is-dirty");
  document.querySelector("#run").disabled = false;
  document.querySelector("#save").disabled = false;
  drawFiles();
  log("console", "opened " + path);
}
async function run() {
  const data = await invoke("render_source", { source: code.value, device: deviceSelect.value });
  if (data.svg) screen.innerHTML = data.svg;
  if (!data.ok) {
    panes.problems = data.error || "Could not read a view.";
    panes.debug = panes.problems;
    show();
    log("output", "render failed: " + panes.problems);
    return;
  }
  screen.innerHTML = data.svg;
  panes.debug = "Sketch tree (not a call stack)\n\n" + treeText(data.tree, 0);
  panes.problems = data.problems.length ? data.problems.join("\n") : "No problems in the known views.";
  panes.output = "rendered " + (current || "buffer") + "\nprovider approximate-web";
  show();
  log("console", "rendered");
}

async function openProject() {
  const picked = await open({ directory: true, multiple: false });
  if (!picked) return;
  await invoke("set_project", { path: picked });
  seeded = false;
  openFolders = new Set();
  current = "";
  code.value = "";
  document.querySelector("#run").disabled = true;
  document.querySelector("#save").disabled = true;
  filename.textContent = "No file selected";
  editorWelcome.hidden = false;
  await refresh();
  log("console", "project " + picked);
}
document.querySelector("#open").onclick = openProject;
document.querySelector("#welcome-open").onclick = openProject;
document.querySelector("#run").onclick = () => run().catch((err) => log("console", String(err)));
document.querySelector("#save").onclick = async () => {
  if (!current) return;
  await invoke("write_source", { path: current, text: code.value });
  saved = code.value;
  document.querySelector("#dirty").textContent = "Saved";
  document.querySelector("#dirty").classList.remove("is-dirty");
  drawFiles();
  log("console", "saved " + current);
};
document.querySelector("#search").oninput = drawFiles;
document.querySelectorAll("#dock .tabs button").forEach((b) => {
  b.onclick = () => {
    document.querySelectorAll("#dock .tabs button").forEach((x) => x.classList.remove("on"));
    b.classList.add("on");
    pane = b.dataset.pane;
    show();
  };
});
code.addEventListener("input", () => {
  scheduleHighlight();
  document.querySelector("#dirty").textContent = code.value === saved ? "Saved" : "Unsaved changes";
  document.querySelector("#dirty").classList.toggle("is-dirty", code.value !== saved);
  drawFiles();
});
deviceSelect.addEventListener("change", () => { if (code.value) run().catch((err) => log("console", String(err))); });
code.addEventListener("scroll", () => {
  const hi = document.querySelector("#hi");
  hi.scrollTop = code.scrollTop;
  hi.scrollLeft = code.scrollLeft;
});
code.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); run(); }
  if ((e.metaKey || e.ctrlKey) && e.key === "s") { e.preventDefault(); document.querySelector("#save").click(); }
});
document.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    document.querySelector("#search").focus();
  }
});
show();
refresh().catch((err) => log("console", String(err)));
