// iLoader tab: the iLoader engine (isideload + idevice) in Rust.
// It has its own Apple sign-in, separate from the xtool one on the Account tab.
import { listen, emit } from "@tauri-apps/api/event";

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

const ANISETTE = [
  ["mac-ani.jkcoxson.com", "jkcoxson (default)"],
  ["new.ani.sidestore.io", "SideStore"],
  ["custom", "Other server…"],
];

export function mountSideload({ invoke, makePanel, pickFile, notify }) {
  const panel = makePanel("sideload");
  const say = el("div", { class: "xnote xsay" });
  let busy = false;

  async function task(label, fn) {
    if (busy) return notify("Another sideload task is running");
    busy = true;
    say.className = "xnote xsay";
    say.textContent = label + "…";
    try {
      const result = await fn();
      say.textContent = label + ": done";
      say.className = "xnote xsay ok";
      return result;
    } catch (err) {
      say.textContent = label + " failed. " + String(err);
      say.className = "xnote xsay bad";
      notify(`${label} failed: ${err}`);
    } finally {
      busy = false;
    }
  }
  const button = (text, onclick, cls = "button-quiet") => el("button", { class: cls, text, onclick });

  // ---------- account ----------
  const who = el("span", { class: "xnote", text: "Not signed in" });
  const appleId = el("input", { class: "xinput", type: "email", placeholder: "Apple ID", autocomplete: "off", spellcheck: "false" });
  const password = el("input", { class: "xinput", type: "password", placeholder: "Password", autocomplete: "off" });
  const anisette = el("select", { class: "xselect" }, ANISETTE.map(([v, t]) => el("option", { value: v, text: t })));
  const custom = el("input", { class: "xinput", placeholder: "ani.example.com", hidden: "", spellcheck: "false" });
  anisette.addEventListener("change", () => { custom.hidden = anisette.value !== "custom"; });
  const storageNote = el("span", { class: "xnote" });
  const signOut = button("Sign out", async () => { await invoke("side_logout"); await refreshAccount(); });
  const form = el("form", { class: "xrow" }, appleId, password, anisette, custom, el("button", { type: "submit", class: "primary", text: "Sign in" }));
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const pass = password.value;
    password.value = "";
    const server = anisette.value === "custom" ? custom.value : anisette.value;
    if (!appleId.value.trim() || !pass) return notify("Enter your Apple ID and password");
    await task("Sign in", () => invoke("side_login", { email: appleId.value, password: pass, anisetteServer: server }));
    await refreshAccount();
  });

  // 2FA and the "too many certificates" question arrive as events from Rust.
  const prompt = el("div", { class: "xprompt", hidden: "" });
  const askText = (label, secret = false) => new Promise((resolve) => {
    const input = el("input", { class: "xprompt-input", type: secret ? "password" : "text", autocomplete: "off" });
    const send = el("button", { type: "submit", class: "primary", text: "Send" });
    const f = el("form", { class: "xprompt-form" }, el("label", { class: "xprompt-label", text: label }), input, send);
    f.addEventListener("submit", (e) => { e.preventDefault(); prompt.hidden = true; prompt.replaceChildren(); resolve(input.value.trim()); });
    prompt.replaceChildren(f);
    prompt.hidden = false;
    input.focus();
  });
  listen("side-2fa", async () => {
    const code = await askText("Apple sent a 6-digit code to your devices:");
    emit("side-2fa-code", code);
  });
  listen("side-max-certs", (event) => {
    const certs = event.payload || [];
    const boxes = certs.map((c) => {
      const box = el("input", { type: "checkbox", value: c.serialNumber || "" });
      return { box, row: el("label", { class: "xcheck" }, box, `${c.name || "certificate"} · ${c.machineName || ""} · ${c.serialNumber || ""}`) };
    });
    const go = button("Revoke selected and continue", () => {
      const picked = boxes.filter((b) => b.box.checked).map((b) => b.box.value);
      if (!picked.length) return notify("Pick at least one certificate to revoke");
      if (!window.confirm(`Revoke ${picked.length} certificate(s)? Apps signed with them stop opening.`)) return;
      prompt.hidden = true; prompt.replaceChildren();
      emit("side-max-certs-reply", picked);
    }, "primary");
    const no = button("Cancel", () => { prompt.hidden = true; prompt.replaceChildren(); emit("side-max-certs-reply", null); });
    prompt.replaceChildren(el("div", { class: "xcol" }, el("strong", { class: "xprompt-label", text: "Your account has the maximum number of certificates. Pick which to revoke:" }), ...boxes.map((b) => b.row), el("div", { class: "xrow" }, go, no)));
    prompt.hidden = false;
  });

  // ---------- device ----------
  const devSelect = el("select", { class: "xselect" });
  const devNote = el("span", { class: "xnote" });
  let devices = [];
  async function loadDevices() {
    devNote.textContent = "Looking for devices…";
    try {
      devices = await invoke("side_devices");
      devSelect.replaceChildren(el("option", { value: "", text: "Choose a device" }), ...devices.map((d) => el("option", { value: d.udid, text: `${d.name} · ${d.connectionType} · iOS ${d.version || "?"}` })));
      devNote.textContent = devices.length ? "" : "No device found. Plug it in and unlock it.";
    } catch (err) {
      devNote.textContent = String(err);
    }
  }
  devSelect.addEventListener("change", async () => {
    const picked = devices.find((d) => d.udid === devSelect.value) || null;
    await task(picked ? "Pairing with " + picked.name : "Clearing device", () => invoke("side_select_device", { device: picked }));
    pairingBox.replaceChildren();
  });
  const needDevice = () => { if (!devSelect.value) { notify("Choose a device first"); return false; } return true; };

  // ---------- install ----------
  const nightly = el("input", { type: "checkbox" });
  const installIpa = button("Install .ipa…", async () => {
    if (!needDevice()) return;
    const path = await pickFile(["ipa", "app"]);
    if (path) await task("Install " + path.split(/[\\/]/).pop(), () => invoke("side_install_ipa", { path }));
  });
  const sideStore = button("Install SideStore", () => needDevice() && task("Install SideStore", () => invoke("side_install_sidestore", { nightly: nightly.checked, liveContainer: false })));
  const liveContainer = button("Install LiveContainer + SideStore", () => needDevice() && task("Install LiveContainer + SideStore", () => invoke("side_install_sidestore", { nightly: nightly.checked, liveContainer: true })));

  // ---------- pairing ----------
  const pairingBox = el("div", { class: "xrow" });
  const findPairingApps = button("Find apps that need a pairing file", async () => {
    if (!needDevice()) return;
    const apps = await task("Look for pairing apps", () => invoke("side_pairing_apps"));
    if (!apps) return;
    pairingBox.replaceChildren(...(apps.length ? apps.map((a) => button("Place in " + a.name, () => task("Place pairing in " + a.name, () => invoke("side_place_pairing", { bundleId: a.bundleId, path: a.path })))) : [el("span", { class: "xnote", text: "None of the supported apps is installed." })]));
  });
  const exportPairing = button("Export pairing file…", () => needDevice() && task("Export pairing file", () => invoke("side_export_pairing")));

  // ---------- certificates and App IDs ----------
  const list = el("div", { class: "xtable-box" }, el("span", { class: "xnote", text: "Sign in to list certificates and App IDs." }));
  const table = (cols, rows) => el("table", { class: "xtable" }, el("thead", {}, el("tr", {}, cols.map((c) => el("th", { text: c })), el("th"))), el("tbody", {}, rows));
  async function showCertificates() {
    const certs = await task("List certificates", () => invoke("side_certificates"));
    if (!certs) return;
    list.replaceChildren(el("span", { class: "xnote", text: `${certs.length} development certificate(s)` }), table(["name", "machine", "serial number"], certs.map((c) => el("tr", {},
      el("td", { text: c.name || "" }), el("td", { text: c.machineName || "" }), el("td", { text: c.serialNumber || "" }),
      el("td", {}, button("Revoke", async () => {
        if (!window.confirm(`Revoke certificate ${c.serialNumber}? Apps signed with it stop opening.`)) return;
        await task("Revoke certificate", () => invoke("side_revoke_certificate", { serialNumber: c.serialNumber }));
        showCertificates();
      }, "button-quiet danger"))))));
  }
  async function showAppIds() {
    const res = await task("List App IDs", () => invoke("side_app_ids"));
    if (!res) return;
    const quota = res.maxQuantity != null ? ` · ${res.availableQuantity} of ${res.maxQuantity} still available` : "";
    list.replaceChildren(el("span", { class: "xnote", text: `${res.appIds.length} App ID(s)${quota}` }), table(["name", "identifier", "expires"], res.appIds.map((a) => el("tr", {},
      el("td", { text: a.name || "" }), el("td", { text: a.identifier || "" }), el("td", { text: a.expirationDate || "" }),
      el("td", {}, button("Delete", async () => {
        if (!window.confirm(`Delete App ID ${a.identifier}? Apps that use it stop opening.`)) return;
        await task("Delete App ID", () => invoke("side_delete_app_id", { appIdId: a.appIdId }));
        showAppIds();
      }, "button-quiet danger"))))));
  }

  async function refreshAccount() {
    const email = await invoke("side_account").catch(() => null);
    who.textContent = email ? "Signed in as " + email : "Not signed in";
    form.hidden = Boolean(email);
    signOut.hidden = !email;
    const kind = await invoke("side_storage_kind").catch(() => "file");
    storageNote.textContent = kind === "keyring" ? "Your signing key is kept in the system keyring." : "No system keyring found: the signing key is kept in a file in the app folder. Protect that folder.";
  }

  panel.append(
    el("div", { class: "xmissing", text: "This tab is iLoader (SideStore, certificates, App IDs, pairing) and signs in to Apple on its own, apart from the Account tab. Sign-in goes through a third-party Anisette server that supplies device-ID data; your credentials only go to Apple. Use a secondary Apple ID if you can. Free accounts: 3 apps, 7-day certificates." }),
    el("div", { class: "xrow xtop" }, who, signOut),
    form, storageNote, prompt,
    el("div", { class: "xrow" }, el("strong", { class: "xnote", text: "Device" }), devSelect, button("↻", loadDevices), devNote),
    el("div", { class: "xrow" }, installIpa, sideStore, liveContainer, el("label", { class: "xnote" }, nightly, " nightly")),
    el("div", { class: "xrow" }, findPairingApps, exportPairing, pairingBox),
    el("div", { class: "xrow" }, el("strong", { class: "xnote", text: "Manage" }), button("Certificates", showCertificates), button("App IDs", showAppIds)),
    say, list,
  );

  return {
    onShow() {
      refreshAccount();
      if (!devSelect.options.length) loadDevices();
    },
  };
}
