// Build, sign and install panels for the dock. They talk to the Rust side
// (`xtool_*` commands), which runs the real xtool CLI in a pseudo terminal.

const el = (tag, attrs = {}, ...kids) => {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  });
  kids.flat().forEach((kid) => kid != null && node.append(kid));
  return node;
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** One terminal: streams a job's output and asks for what xtool asks for. */
function makeTerminal(invoke, { onDone } = {}) {
  const log = el("pre", { class: "xlog", text: "Nothing has run yet." });
  const promptLabel = el("label", { class: "xprompt-label" });
  const promptInput = el("input", { class: "xprompt-input", autocomplete: "off", spellcheck: "false" });
  const promptForm = el("form", { class: "xprompt", hidden: "" }, promptLabel, promptInput, el("button", { type: "submit", class: "primary", text: "Send" }));
  const cancel = el("button", { class: "button-quiet", text: "Cancel", hidden: "" });
  const status = el("span", { class: "xstatus" });
  const root = el("div", { class: "xterm" }, el("div", { class: "xterm-bar" }, status, cancel), log, promptForm);

  let job = null;
  let secretAnswer = null; // typed in this window, sent once, never stored
  let answered = new Set();

  const write = (text) => {
    log.textContent += (log.textContent ? "\n" : "") + text;
    log.scrollTop = log.scrollHeight;
  };
  const reset = (title) => {
    log.textContent = "";
    write("$ xtool " + title);
    promptForm.hidden = true;
    answered = new Set();
  };

  promptForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!job) return;
    const text = promptInput.value;
    promptInput.value = "";
    promptForm.hidden = true;
    try {
      await invoke("xtool_input", { id: job.id, text });
    } catch (err) {
      write(String(err));
    }
  });
  cancel.addEventListener("click", async () => {
    if (job) await invoke("xtool_cancel", { id: job.id }).catch(() => {});
  });

  async function poll() {
    if (!job) return;
    let p;
    try {
      p = await invoke("xtool_poll", { id: job.id, since: job.next });
    } catch (err) {
      write(String(err));
      return;
    }
    p.lines.forEach(write);
    job.next = p.next;
    if (p.prompt) {
      const key = p.next + ":" + p.prompt;
      if (p.secret && secretAnswer != null && !answered.has(key)) {
        answered.add(key);
        const text = secretAnswer;
        secretAnswer = null;
        invoke("xtool_input", { id: job.id, text }).catch((e) => write(String(e)));
      } else if (!answered.has(key) || promptForm.hidden) {
        promptLabel.textContent = p.prompt;
        promptInput.type = p.secret ? "password" : "text";
        promptForm.hidden = false;
        promptInput.focus();
      }
    } else {
      promptForm.hidden = true;
    }
    if (p.done) {
      const ok = p.code === 0;
      status.textContent = ok ? "Finished" : p.code == null ? "Stopped" : "Failed (exit " + p.code + ")";
      status.className = "xstatus " + (ok ? "ok" : "bad");
      cancel.hidden = true;
      promptForm.hidden = true;
      const finished = job;
      job = null;
      secretAnswer = null;
      if (onDone) onDone(finished.action, ok);
      return;
    }
    await sleep(220);
    poll();
  }

  return {
    root,
    busy: () => job !== null,
    /** Starts an xtool action. `secret` is answered once when xtool asks for a password. */
    async run(action, params = {}, { title = action, secret = null } = {}) {
      reset(title);
      status.textContent = "Running…";
      status.className = "xstatus";
      cancel.hidden = false;
      secretAnswer = secret;
      try {
        const id = await invoke("xtool_start", { action, params });
        job = { id, next: 0, action };
        poll();
      } catch (err) {
        write(String(err));
        status.textContent = "Could not start";
        status.className = "xstatus bad";
        cancel.hidden = true;
        secretAnswer = null;
      }
    },
  };
}

const chip = (label, state, detail = "") =>
  el("span", { class: "xchip " + state, title: detail }, el("i"), label);

export function mountXtool({ invoke, pickFile, notify }) {
  const dock = document.querySelector("#dock");
  const center = document.querySelector("#center");
  const panels = {};
  const refreshers = [];

  function makePanel(name) {
    const panel = el("div", { class: "xpanel", hidden: "" });
    dock.appendChild(panel);
    panels[name] = panel;
    return panel;
  }

  let state = null; // last xtool_status
  const listeners = [];
  async function refreshStatus() {
    try {
      state = await invoke("xtool_status");
    } catch (err) {
      state = null;
      notify(String(err));
    }
    listeners.forEach((fn) => fn(state));
    return state;
  }

  // ---------------- Build ----------------
  const build = makePanel("build");
  const chips = el("div", { class: "xchips" });
  const terminal = makeTerminal(invoke, {
    onDone: (action, ok) => {
      if (["setup", "new", "auth-login", "auth-logout"].includes(action) || ok) refreshStatus();
      if (action === "build" && ok) notify("Build finished");
    },
  });
  const deviceSelect = el("select", { class: "xselect", title: "Connected device" });
  const deviceNote = el("span", { class: "xnote" });
  const nameInput = el("input", { class: "xinput", placeholder: "New project name", spellcheck: "false", value: "HelloApp" });

  const button = (text, onclick, cls = "button-quiet") => el("button", { class: cls, text, onclick });
  const guard = (fn) => () => {
    if (terminal.busy()) return notify("Another xtool job is running");
    fn();
  };

  const setupBtn = button("Set up xtool", guard(() => terminal.run("setup", {}, { title: "setup" })), "primary");
  const newBtn = button("Create project", guard(() => terminal.run("new", { name: nameInput.value }, { title: "new " + nameInput.value })));
  const buildBtn = button("Build", guard(() => terminal.run("build", {}, { title: "dev build" })));
  const signBtn = button("Build + sign .ipa", guard(() => terminal.run("build", { sign: true, ipa: true }, { title: "dev build --sign --ipa" })));
  const runBtn = button("Run on device", guard(() => {
    if (!deviceSelect.value) return notify("Connect a device and refresh the list");
    terminal.run("run", { udid: deviceSelect.value }, { title: "dev run --udid " + deviceSelect.value });
  }), "primary");
  const installBtn = button("Install .ipa…", async () => {
    if (terminal.busy()) return notify("Another xtool job is running");
    if (!deviceSelect.value) return notify("Connect a device and refresh the list");
    const path = await pickFile(["ipa", "app"]);
    if (path) terminal.run("install", { udid: deviceSelect.value, path }, { title: "install" });
  });
  const refreshDevices = button("↻", async () => {
    deviceNote.textContent = "Looking for devices…";
    try {
      const found = await invoke("xtool_devices");
      deviceSelect.replaceChildren(...found.map((d) => el("option", { value: d.udid, text: `${d.name} · ${d.connection}` })));
      deviceNote.textContent = found.length ? "" : "No device found. Plug it in and unlock it.";
    } catch (err) {
      deviceNote.textContent = String(err);
    }
  });
  refreshDevices.title = "Refresh devices";
  const recheck = button("↻ Check again", () => refreshStatus());

  const missing = el("div", { class: "xmissing", hidden: "" });
  const actions = el("div", { class: "xrow" }, setupBtn, buildBtn, signBtn, el("span", { class: "xsep" }), deviceSelect, refreshDevices, runBtn, installBtn, deviceNote);
  const newRow = el("div", { class: "xrow", hidden: "" }, nameInput, newBtn, el("span", { class: "xnote", text: "This folder has no Package.swift yet." }));
  build.append(el("div", { class: "xrow xtop" }, chips, recheck), missing, newRow, actions, terminal.root);

  listeners.push((s) => {
    chips.replaceChildren();
    const installed = Boolean(s && s.installed);
    missing.hidden = installed;
    newRow.hidden = !installed || s.project_ready;
    actions.hidden = !installed;
    if (!installed) {
      chips.append(chip("xtool not found", "bad"));
      const onWindows = s && s.host === "windows";
      missing.replaceChildren(
        el("strong", { text: "xtool is not installed" }),
        el("span", {
          text: onWindows
            ? " OpenSwift looks for it inside WSL. Install WSL, then follow the xtool install guide inside it."
            : " Install it from github.com/xtool-org/xtool, then press Check again. It needs a Swift toolchain and an Xcode.xip you download from Apple.",
        }),
      );
      return;
    }
    const where = s.via_wsl ? "WSL" : "local";
    chips.append(
      chip("xtool " + (s.version || "").split("\n")[0], "ok", s.path + " (" + where + ")"),
      chip(s.sdk.installed ? "iOS SDK " + s.sdk.version : "iOS SDK missing", s.sdk.installed ? "ok" : "warn"),
      chip(s.auth.logged_in ? "Apple ID signed in" : "Not signed in", s.auth.logged_in ? "ok" : "warn", s.auth.detail),
      chip(s.project_ready ? "xtool project" : "No Package.swift", s.project_ready ? "ok" : "warn"),
    );
    const ready = s.sdk.installed && s.auth.logged_in;
    setupBtn.hidden = ready;
    buildBtn.disabled = !s.project_ready;
    signBtn.disabled = !s.project_ready || !s.auth.logged_in;
    runBtn.disabled = !s.project_ready || !s.auth.logged_in;
    installBtn.disabled = !s.auth.logged_in;
    signBtn.title = s.auth.logged_in ? "" : "Sign in first (Account tab)";
  });

  // ---------------- Account ----------------
  const account = makePanel("account");
  const accountTerm = makeTerminal(invoke, {
    onDone: () => refreshStatus(),
  });
  const appleId = el("input", { class: "xinput", type: "email", placeholder: "Apple ID", autocomplete: "username", spellcheck: "false" });
  const password = el("input", { class: "xinput", type: "password", placeholder: "Password", autocomplete: "current-password" });
  const who = el("div", { class: "xwho" });
  const loginForm = el("form", { class: "xrow" }, appleId, password, el("button", { type: "submit", class: "primary", text: "Sign in" }));
  const signOut = button("Sign out", () => {
    if (accountTerm.busy()) return notify("Another xtool job is running");
    accountTerm.run("auth-logout", {}, { title: "auth logout" });
  });
  const forget = button("Sign out and forget this computer (2FA)", () => {
    if (accountTerm.busy()) return notify("Another xtool job is running");
    accountTerm.run("auth-logout", { reset_2fa: true }, { title: "auth logout --reset-2fa" });
  });
  const warning = el("div", { class: "xmissing", text: "Heads up (from xtool): password sign-in emulates a Mac and talks to Apple through private APIs. Your credentials go only to Apple, but consider a secondary Apple ID. Free accounts allow a few App IDs per week and certificates last 7 days. Paid-program API keys are not offered here; use `xtool auth login --mode key` in a terminal." });
  const missingAcct = el("div", { class: "xmissing", hidden: "", text: "xtool is not installed, so there is nothing to sign in to yet. See the Build tab." });
  loginForm.addEventListener("submit", (event) => {
    event.preventDefault();
    if (accountTerm.busy()) return notify("Another xtool job is running");
    const user = appleId.value.trim();
    const pass = password.value;
    if (!user || !pass) return notify("Enter your Apple ID and password");
    password.value = ""; // the password lives only in the terminal's one-shot answer
    accountTerm.run("auth-login", { username: user }, { title: "auth login --mode password --username " + user, secret: pass });
  });
  account.append(
    el("div", { class: "xrow xtop" }, who, el("div", { class: "xrow" }, signOut, forget)),
    missingAcct, warning, loginForm,
    el("span", { class: "xnote", text: "If Apple asks for a verification code or a team, a prompt appears below." }),
    accountTerm.root,
  );
  listeners.push((s) => {
    const installed = Boolean(s && s.installed);
    missingAcct.hidden = installed;
    loginForm.hidden = !installed;
    signOut.hidden = forget.hidden = !installed || !s.auth.logged_in;
    who.replaceChildren(
      installed && s.auth.logged_in
        ? chip("Signed in", "ok", s.auth.detail)
        : chip(installed ? "Signed out" : "xtool missing", installed ? "warn" : "bad"),
      installed && s.auth.logged_in && s.auth.detail ? el("span", { class: "xnote", text: s.auth.detail }) : "",
    );
  });

  // ---------------- Devices & Apple inventory ----------------
  const devices = makePanel("devices");
  const INVENTORY = {
    teams: ["Teams", ["name", "status", "id", "memberships"]],
    certificates: ["Certificates", ["name", "type", "expiry", "serial number"]],
    identifiers: ["App IDs", ["name", "identifier", "platform"]],
    devices: ["Registered devices", ["name", "platform", "udid"]],
    profiles: ["Profiles", ["name", "profile type", "profile state", "expiration date"]],
  };
  let kind = "certificates";
  const kindBar = el("div", { class: "xrow xkinds" });
  const tableBox = el("div", { class: "xtable-box" }, el("span", { class: "xnote", text: "Pick what to list. This reads your Apple Developer account through xtool (no second sign-in)." }));
  const devTerm = makeTerminal(invoke, {});
  const bundle = el("input", { class: "xinput", placeholder: "Bundle ID, e.g. com.example.HelloApp", spellcheck: "false" });
  const devSelect = el("select", { class: "xselect", title: "Connected device" });
  const devNote = el("span", { class: "xnote" });

  async function loadDevices() {
    devNote.textContent = "Looking for devices…";
    try {
      const found = await invoke("xtool_devices");
      devSelect.replaceChildren(...found.map((d) => el("option", { value: d.udid, text: `${d.name} · ${d.connection}` })));
      devNote.textContent = found.length ? "" : "No device found. Plug it in and unlock it.";
    } catch (err) {
      devNote.textContent = String(err);
    }
  }
  function renderInventory(inv) {
    const [title, columns] = INVENTORY[inv.kind];
    if (!inv.records.length) {
      tableBox.replaceChildren(
        el("span", { class: "xnote", text: "Nothing to show for " + title.toLowerCase() + "." }),
        inv.raw ? el("pre", { class: "xlog", text: inv.raw }) : "",
      );
      return;
    }
    const rows = inv.records.map((r) => Object.fromEntries(r.fields));
    const cols = columns.filter((c) => rows.some((r) => r[c] != null));
    const table = el("table", { class: "xtable" },
      el("thead", {}, el("tr", {}, cols.map((c) => el("th", { text: c })))),
      el("tbody", {}, rows.map((r) => el("tr", {}, cols.map((c) => el("td", { text: r[c] ?? "" }))))),
    );
    tableBox.replaceChildren(el("span", { class: "xnote", text: `${rows.length} ${title.toLowerCase()}` }), table);
  }
  async function loadInventory(which) {
    kind = which;
    kindBar.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.kind === which));
    tableBox.replaceChildren(el("span", { class: "xnote", text: "Asking Apple…" }));
    try {
      renderInventory(await invoke("xtool_inventory", { kind: which }));
    } catch (err) {
      tableBox.replaceChildren(el("span", { class: "xnote", text: String(err) }));
    }
  }
  Object.entries(INVENTORY).forEach(([key, [title]]) => {
    const b = el("button", { class: "button-quiet", text: title, "data-kind": key, onclick: () => loadInventory(key) });
    kindBar.append(b);
  });
  const act = (action, label, danger) => button(label, () => {
    if (devTerm.busy()) return notify("Another xtool job is running");
    if (!devSelect.value) return notify("Connect a device and refresh the list");
    if (!bundle.value.trim()) return notify("Enter the bundle ID of the app");
    if (danger && !window.confirm(`${label} ${bundle.value.trim()} on the selected device?`)) return;
    devTerm.run(action, { udid: devSelect.value, bundle_id: bundle.value.trim() }, { title: `${action} ${bundle.value.trim()}` });
  }, danger ? "button-quiet danger" : "button-quiet");
  devices.append(
    el("div", { class: "xrow xtop" }, kindBar, button("↻ Reload", () => loadInventory(kind))),
    tableBox,
    el("div", { class: "xrow" }, el("strong", { class: "xnote", text: "On the device" }), devSelect, button("↻", loadDevices), bundle, act("launch", "Launch"), act("uninstall", "Uninstall", true), devNote),
    devTerm.root,
  );
  listeners.push((s) => {
    const ok = Boolean(s && s.installed && s.auth.logged_in);
    kindBar.querySelectorAll("button").forEach((b) => { b.disabled = !ok; });
    if (!ok) tableBox.replaceChildren(el("span", { class: "xnote", text: s && s.installed ? "Sign in from the Account tab to see your certificates, App IDs and devices." : "xtool is not installed. See the Build tab." }));
  });

  return {
    terminal,
    panels,
    makePanel,
    makeTerminal: (opts) => makeTerminal(invoke, opts),
    chip,
    el,
    onStatus: (fn) => { listeners.push(fn); if (state) fn(state); },
    refreshStatus,
    getState: () => state,
    has: (name) => name in panels,
    show(name) {
      Object.entries(panels).forEach(([key, node]) => { node.hidden = key !== name; });
      center.classList.add("tall");
      const pre = document.querySelector("#dockpre");
      if (pre) pre.hidden = true;
      refreshStatus();
      if (name === "build" && !deviceSelect.options.length) refreshDevices.click();
      if (name === "devices") {
        if (!devSelect.options.length) loadDevices();
        refreshStatus().then((s) => { if (s && s.installed && s.auth.logged_in) loadInventory(kind); });
      }
    },
    hideAll() {
      Object.values(panels).forEach((node) => { node.hidden = true; });
      center.classList.remove("tall");
      const pre = document.querySelector("#dockpre");
      if (pre) pre.hidden = false;
    },
  };
}
