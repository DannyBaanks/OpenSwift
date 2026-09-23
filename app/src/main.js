import "./style.css";
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";

const app = document.querySelector("#app");
app.innerHTML = `
<header>
  <strong>OpenSwift</strong>
  <button id="open">Open</button>
  <button id="run" class="primary" disabled>Run</button>
  <button id="save" disabled>Save</button>
  <input id="search" placeholder="Filter files" />
</header>
<main>
  <aside id="files"><h2>PROJECT NAVIGATOR</h2><div id="list"></div></aside>
  <section id="center">
    <div id="tab">No file</div>
    <div id="editor">
      <pre id="hi"></pre>
      <textarea id="code" spellcheck="false" placeholder="Open a project, pick a .swift file, press Run. This does not compile Swift."></textarea>
    </div>
    <div id="dock">
      <div class="tabs">
        <button data-pane="debug" class="on">Debugger</button>
        <button data-pane="output">Output</button>
        <button data-pane="problems">Problems</button>
        <button data-pane="console">Console</button>
      </div>
      <pre id="dockpre"></pre>
    </div>
  </section>
  <aside id="stage">
    <h2>PREVIEW</h2>
    <select id="device"></select>
    <div id="phone"><div id="screen"><div id="empty">Run to draw this file.</div></div></div>
  </aside>
</main>
<footer><span id="rootlabel"></span><span>approximate-web · not a Swift debugger</span></footer>
`;

const code = document.querySelector("#code");
const list = document.querySelector("#list");
const tab = document.querySelector("#tab");
const screen = document.querySelector("#screen");
const dockpre = document.querySelector("#dockpre");
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
    row.innerHTML = `<span class="chev">${open ? "▾" : "▸"}</span><span>${dir.name}</span>`;
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
    row.innerHTML = `<span class="ficon">S</span><span>${file.name}</span>${dirty ? '<em class="mark">M</em>' : ""}`;
    row.onclick = () => openFile(file.path);
    list.appendChild(row);
  });
}
function drawFiles() {
  list.innerHTML = "";
  addTree(treeFrom(files), 0);
}
async function refresh() {
  const info = await invoke("project_info");
  document.querySelector("#rootlabel").textContent = info.root || "No project";
  files = info.files || [];
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
  tab.textContent = path;
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

document.querySelector("#open").onclick = async () => {
  const picked = await open({ directory: true, multiple: false });
  if (!picked) return;
  await invoke("set_project", { path: picked });
  seeded = false;
  openFolders = new Set();
  current = "";
  code.value = "";
  tab.textContent = "No file";
  await refresh();
  log("console", "project " + picked);
};
document.querySelector("#run").onclick = () => run().catch((err) => log("console", String(err)));
document.querySelector("#save").onclick = async () => {
  if (!current) return;
  await invoke("write_source", { path: current, text: code.value });
  saved = code.value;
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
code.addEventListener("input", () => { scheduleHighlight(); drawFiles(); });
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
show();
refresh().catch((err) => log("console", String(err)));
