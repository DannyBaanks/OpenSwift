//! Sideloading tools: the engine behind iLoader (`isideload` + `idevice`).
//!
//! Adapted from iLoader (https://github.com/nab138/iloader, MIT, Copyright (c)
//! 2025 nab138); see NOTICE.md. This is a separate Apple sign-in from the
//! xtool one on purpose: it lets the window revoke certificates, delete App
//! IDs, install an .ipa that was not built here, and place pairing files.
//! Nothing here is kept between runs except what `isideload` stores (anisette
//! state and the signing key) in the OS keyring, or in the app folder when no
//! keyring exists.

use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::{Arc, Mutex, OnceLock};
use std::time::Duration;

use futures::FutureExt;
use idevice::{
    afc::AfcClient,
    house_arrest::HouseArrestClient,
    installation_proxy::InstallationProxyClient,
    lockdown::LockdownClient,
    provider::{IdeviceProvider, UsbmuxdProvider},
    remote_pairing::{RemotePairingLockdownService, RpPairingFile},
    usbmuxd::{Connection, UsbmuxdAddr, UsbmuxdConnection},
    IdeviceService,
};
use isideload::{
    anisette::remote_v3::RemoteV3AnisetteProvider,
    auth::apple_account::{AppleAccount, TwoFactorCallbackParams, TwoFactorCallbackResponse},
    dev::{
        app_ids::{AppIdsApi, ListAppIdsResponse},
        certificates::{CertificatesApi, DevelopmentCertificate},
        developer_session::DeveloperSession,
    },
    sideload::{
        builder::{ExtensionsBehavior, ExtensionsBehaviorSelection, MaxCertsBehavior},
        sideloader::Sideloader,
        SideloaderBuilder,
    },
    util::{
        callbacks::{ExtensionsBehaviorCallbackBox, MaxCertsCallbackBox},
        fs_storage::FsStorage,
        keyring_storage::KeyringStorage,
        storage::SideloadingStorage,
    },
};
use rootcause::prelude::*;
use serde::{de::DeserializeOwned, Deserialize, Serialize};
use tauri::{Emitter, Listener, Manager, State, Window};
use tauri_plugin_dialog::DialogExt;
use tokio::sync::oneshot;

type Engine = Sideloader<MaxCertsCallbackBox, ExtensionsBehaviorCallbackBox>;

#[derive(Default)]
pub struct SideState {
    sideloader: Mutex<Option<Engine>>,
    device: Mutex<Option<SelectedDevice>>,
}

#[derive(Clone)]
struct SelectedDevice {
    info: DeviceInfo,
    pairing: Vec<u8>,
}

/// Takes the signed-in engine out of the state while a call uses it, and puts it back after.
struct EngineGuard<'a> {
    state: &'a Mutex<Option<Engine>>,
    engine: Option<Engine>,
}

impl<'a> EngineGuard<'a> {
    fn take(state: &'a Mutex<Option<Engine>>) -> Result<Self, String> {
        let engine = state
            .lock()
            .map_err(|e| e.to_string())?
            .take()
            .ok_or("Not signed in to the sideloading account")?;
        Ok(Self { state, engine: Some(engine) })
    }

    fn get(&mut self) -> &mut Engine {
        self.engine.as_mut().expect("engine is present until drop")
    }
}

impl Drop for EngineGuard<'_> {
    fn drop(&mut self) {
        if let Ok(mut guard) = self.state.lock() {
            *guard = self.engine.take();
        }
    }
}

/// Turns a report from isideload or idevice into one readable sentence.
fn explain(report: Report) -> String {
    let text = report.to_string();
    let lower = text.to_lowercase();
    let hint = if lower.contains("maximum number of installed apps") {
        " Free accounts can keep 3 sideloaded apps at once; remove one first."
    } else if lower.contains("not enough available app ids") {
        " This account has used its App IDs for the week; delete one in the App IDs list or wait."
    } else if lower.contains("anisette") {
        " The Anisette server did not answer. Try another server address."
    } else if lower.contains("-20209") {
        " Apple says this account is locked."
    } else {
        ""
    };
    format!("{text}.{hint}").replace("..", ".")
}

fn friendly<E: std::fmt::Display>(prefix: &str, err: E) -> String {
    format!("{prefix}: {err}")
}

/// Emits `ask`, then waits for one reply on `reply`. The listener is registered first so the answer cannot be missed.
async fn ask<T: DeserializeOwned>(
    window: &Window,
    ask: &str,
    payload: impl Serialize + Clone,
    reply: &str,
    seconds: u64,
) -> Result<T, String> {
    let (tx, rx) = oneshot::channel::<String>();
    let tx = Arc::new(Mutex::new(Some(tx)));
    let sender = tx.clone();
    let id = window.listen(reply, move |event| {
        if let Some(tx) = sender.lock().ok().and_then(|mut s| s.take()) {
            let _ = tx.send(event.payload().to_string());
        }
    });
    let sent = window.emit(ask, payload).map_err(|e| e.to_string());
    let answer = match sent {
        Ok(()) => tokio::time::timeout(Duration::from_secs(seconds), rx).await,
        Err(e) => {
            window.unlisten(id);
            return Err(e);
        }
    };
    window.unlisten(id);
    let raw = answer.map_err(|_| "Timed out waiting for your answer".to_string())?.map_err(|_| "No answer".to_string())?;
    serde_json::from_str(&raw).map_err(|e| e.to_string())
}

// ---------- storage ----------

static FORCE_FILE_STORAGE: OnceLock<bool> = OnceLock::new();

fn keyring_works() -> bool {
    if FORCE_FILE_STORAGE.get().copied().unwrap_or(false) {
        return false;
    }
    match keyring::Entry::new("openswift-sideload", "probe") {
        Ok(entry) => entry.set_password("probe").is_ok() && entry.get_password().is_ok(),
        Err(_) => false,
    }
}

fn storage(app: &tauri::AppHandle) -> Result<Box<dyn SideloadingStorage>, String> {
    if keyring_works() {
        return Ok(Box::new(KeyringStorage::new("openswift-sideload".to_string())));
    }
    let dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    Ok(Box::new(FsStorage::new(dir)))
}

#[tauri::command]
pub fn side_storage_kind() -> String {
    if keyring_works() { "keyring".into() } else { "file".into() }
}

// ---------- account ----------

/// `ani.sidestore.io` style input becomes a full URL.
pub fn anisette_url(input: &str) -> String {
    let input = input.trim().trim_end_matches('/');
    if input.starts_with("http://") || input.starts_with("https://") {
        input.to_string()
    } else {
        format!("https://{input}")
    }
}

#[derive(Serialize, Deserialize, Clone, Debug)]
#[serde(rename_all = "camelCase")]
pub struct CertInfo {
    pub name: Option<String>,
    pub certificate_id: Option<String>,
    pub serial_number: Option<String>,
    pub machine_name: Option<String>,
    pub machine_id: Option<String>,
}

impl From<DevelopmentCertificate> for CertInfo {
    fn from(c: DevelopmentCertificate) -> Self {
        CertInfo {
            name: c.name,
            certificate_id: c.certificate_id,
            serial_number: c.serial_number,
            machine_name: c.machine_name,
            machine_id: c.machine_id,
        }
    }
}

#[tauri::command]
pub async fn side_login(
    app: tauri::AppHandle,
    window: Window,
    state: State<'_, SideState>,
    email: String,
    password: String,
    anisette_server: String,
) -> Result<String, String> {
    let email = email.trim().to_lowercase();
    if email.is_empty() || password.is_empty() {
        return Err("Enter your Apple ID and password".into());
    }
    let url = anisette_url(&anisette_server);
    let two_factor_window = window.clone();
    let two_factor = move |params: TwoFactorCallbackParams| {
        let window = two_factor_window.clone();
        async move {
            let code: String = ask(&window, "side-2fa", params, "side-2fa-code", 180)
                .await
                .map_err(|e| report!("{e}"))?;
            Ok(TwoFactorCallbackResponse::SubmitCode(code.trim().to_string()))
        }
        .boxed()
    };

    let mut account = AppleAccount::builder(&email)
        .anisette_provider(
            RemoteV3AnisetteProvider::default()
                .map_err(explain)?
                .set_serial_number("0".to_string())
                .set_storage(storage(&app)?)
                .set_url(&url),
        )
        .login(&password, Box::new(two_factor))
        .await
        .map_err(explain)?;

    let dev_session = DeveloperSession::from_account(&mut account).await.map_err(explain)?;

    let max_certs_window = window.clone();
    let max_certs: MaxCertsCallbackBox = Box::new(move |certs: Vec<DevelopmentCertificate>| {
        let window = max_certs_window.clone();
        Box::pin(async move {
            let list: Vec<CertInfo> = certs.into_iter().map(CertInfo::from).collect();
            // The window answers with the serial numbers to revoke, or null to give up.
            let answer: Option<Vec<String>> = ask(&window, "side-max-certs", list, "side-max-certs-reply", 300)
                .await
                .map_err(|e| report!("{e}"))?;
            Ok(answer)
        })
    });

    let engine = SideloaderBuilder::new(dev_session, email.clone())
        .machine_name("OpenSwift".into())
        .storage(storage(&app)?)
        .extensions_behavior(ExtensionsBehaviorSelection::Fixed(ExtensionsBehavior::ReuseMain))
        .max_certs_behavior(MaxCertsBehavior::Prompt(max_certs))
        .build();

    *state.sideloader.lock().map_err(|e| e.to_string())? = Some(engine);
    Ok(email)
}

#[tauri::command]
pub fn side_account(state: State<'_, SideState>) -> Option<String> {
    state.sideloader.lock().ok()?.as_ref().map(|e| e.get_email().to_string())
}

#[tauri::command]
pub fn side_logout(state: State<'_, SideState>) -> Result<(), String> {
    *state.sideloader.lock().map_err(|e| e.to_string())? = None;
    Ok(())
}

#[tauri::command]
pub async fn side_certificates(state: State<'_, SideState>) -> Result<Vec<CertInfo>, String> {
    let mut guard = EngineGuard::take(&state.sideloader)?;
    let team = guard.get().get_team().await.map_err(explain)?;
    let certs = guard.get().get_dev_session().list_all_development_certs(&team, None).await.map_err(explain)?;
    Ok(certs.into_iter().map(CertInfo::from).collect())
}

#[tauri::command]
pub async fn side_revoke_certificate(state: State<'_, SideState>, serial_number: String) -> Result<(), String> {
    clean_serial(&serial_number)?;
    let mut guard = EngineGuard::take(&state.sideloader)?;
    let team = guard.get().get_team().await.map_err(explain)?;
    guard.get().get_dev_session().revoke_development_cert(&team, &serial_number, None).await.map_err(explain)?;
    Ok(())
}

#[tauri::command]
pub async fn side_app_ids(state: State<'_, SideState>) -> Result<ListAppIdsResponse, String> {
    let mut guard = EngineGuard::take(&state.sideloader)?;
    let team = guard.get().get_team().await.map_err(explain)?;
    let response = guard.get().get_dev_session().list_app_ids(&team, None).await.map_err(explain)?;
    Ok(response.clone())
}

#[tauri::command]
pub async fn side_delete_app_id(state: State<'_, SideState>, app_id_id: String) -> Result<(), String> {
    clean_serial(&app_id_id)?;
    let mut guard = EngineGuard::take(&state.sideloader)?;
    let team = guard.get().get_team().await.map_err(explain)?;
    guard.get().get_dev_session().delete_app_id(&team, &app_id_id, None).await.map_err(explain)?;
    Ok(())
}

/// Serial numbers and App ID ids are hex or alphanumeric tokens; anything else is not one of ours.
pub fn clean_serial(value: &str) -> Result<(), String> {
    if !value.is_empty() && value.len() <= 80 && value.chars().all(|c| c.is_ascii_alphanumeric() || c == '-') {
        Ok(())
    } else {
        Err("that is not a certificate serial or App ID".into())
    }
}

// ---------- devices ----------

#[derive(Serialize, Deserialize, Clone, Debug)]
#[serde(rename_all = "camelCase")]
pub struct DeviceInfo {
    pub name: String,
    pub udid: String,
    pub connection_type: String,
    pub version: String,
}

async fn usbmuxd() -> Result<UsbmuxdConnection, String> {
    UsbmuxdConnection::default()
        .await
        .map_err(|e| friendly("Could not reach usbmuxd. Is it running (Linux) or Apple Devices / iTunes installed (Windows)?", e))
}

fn addr() -> Result<UsbmuxdAddr, String> {
    UsbmuxdAddr::from_env_var().map_err(|e| friendly("Invalid usbmuxd address", e))
}

async fn provider_for(udid: &str) -> Result<UsbmuxdProvider, String> {
    let mut mux = usbmuxd().await?;
    let device = mux.get_device(udid).await.map_err(|e| friendly("Device not found", e))?;
    Ok(device.to_provider(addr()?, "openswift"))
}

#[tauri::command]
pub async fn side_devices() -> Result<Vec<DeviceInfo>, String> {
    let mut mux = usbmuxd().await?;
    let devices = mux.get_devices().await.map_err(|e| friendly("Could not list devices", e))?;
    let mut found = Vec::new();
    for d in devices {
        let provider = d.to_provider(addr()?, "openswift");
        let kind = match d.connection_type {
            Connection::Usb => "USB",
            Connection::Network(_) => "Network",
            Connection::Unknown(_) => "Unknown",
        };
        let mut lockdown = match LockdownClient::connect(&provider).await {
            Ok(l) => l,
            Err(_) => {
                found.push(DeviceInfo { name: format!("{} (locked or untrusted)", d.udid), udid: d.udid.clone(), connection_type: kind.into(), version: String::new() });
                continue;
            }
        };
        let text = |value: Result<plist::Value, idevice::IdeviceError>| value.ok().and_then(|v| v.as_string().map(str::to_string)).unwrap_or_default();
        let name = text(lockdown.get_value(Some("DeviceName"), None).await);
        let version = text(lockdown.get_value(Some("ProductVersion"), None).await);
        found.push(DeviceInfo { name: if name.is_empty() { d.udid.clone() } else { name }, udid: d.udid.clone(), connection_type: kind.into(), version });
    }
    Ok(found)
}

// ---------- pairing ----------

fn version_below(version: &str, major: u32, minor: u32) -> bool {
    let mut parts = version.split('.').map(|p| p.chars().take_while(char::is_ascii_digit).collect::<String>().parse::<u32>().unwrap_or(0));
    let (a, b) = (parts.next().unwrap_or(0), parts.next().unwrap_or(0));
    (a, b) < (major, minor)
}

async fn lockdown_pairing(udid: &str, provider: &dyn IdeviceProvider, mux: &mut UsbmuxdConnection) -> Result<plist::Dictionary, String> {
    let mut record = mux.get_pair_record(udid).await.map_err(|e| friendly("No pairing record. Unlock the device and tap Trust, then try again", e))?;
    record.udid = Some(udid.to_string());
    let mut lockdown = LockdownClient::connect(provider).await.map_err(|e| friendly("Could not reach the device", e))?;
    lockdown.start_session(&record).await.map_err(|e| friendly("Could not start a lockdown session", e))?;
    lockdown
        .set_value("EnableWifiDebugging", true.into(), Some("com.apple.mobile.wireless_lockdown"))
        .await
        .map_err(|e| friendly("Could not enable Wi-Fi debugging", e))?;
    let bytes = record.serialize().map_err(|e| friendly("Could not serialize the pairing record", e))?;
    plist::Value::from_reader_xml(std::io::Cursor::new(bytes))
        .map_err(|e| friendly("Pairing record is not a plist", e))?
        .into_dictionary()
        .ok_or_else(|| "Pairing record is not a dictionary".to_string())
}

fn host_label(app: &tauri::AppHandle, udid: &str) -> Result<String, String> {
    let store = storage(app)?;
    let key = format!("host_label_{udid}");
    if let Some(bytes) = store.retrieve_data(&key).map_err(|e| e.to_string())? {
        return String::from_utf8(bytes).map_err(|e| e.to_string());
    }
    let id = uuid::Uuid::new_v4().simple().to_string();
    let label = format!("openswift-{}", &id[..6]);
    store.store_data(&key, label.as_bytes()).map_err(|e| e.to_string())?;
    Ok(label)
}

async fn remote_pairing(app: &tauri::AppHandle, udid: &str, provider: &dyn IdeviceProvider) -> Result<plist::Dictionary, String> {
    let store = storage(app)?;
    let key = format!("rppairing_file_{udid}");
    let bytes = match store.retrieve_data(&key).map_err(|e| e.to_string())? {
        Some(cached) => cached,
        None => {
            let label = host_label(app, udid)?;
            let service = RemotePairingLockdownService::connect(provider).await.map_err(|e| friendly("Remote pairing is not available on this device", e))?;
            let mut client = service.into_client(&label).map_err(|e| friendly("Remote pairing has no socket", format!("{e:?}")))?;
            let mut file = RpPairingFile::generate(&label);
            client
                .connect(&mut file, async || "000000".to_string())
                .await
                .map_err(|e| friendly("Remote pairing failed. Keep the device unlocked and accept any prompt", e))?;
            let bytes = file.to_bytes();
            store.store_data(&key, &bytes).map_err(|e| e.to_string())?;
            bytes
        }
    };
    plist::Value::from_reader_xml(std::io::Cursor::new(bytes))
        .map_err(|e| friendly("Stored remote pairing is invalid", e))?
        .into_dictionary()
        .ok_or_else(|| "Remote pairing is not a dictionary".to_string())
}

/// Builds the pairing file apps like SideStore read: the lockdown record, plus the remote pairing on iOS 17.4 and later.
async fn pairing_bytes(app: &tauri::AppHandle, info: &DeviceInfo) -> Result<Vec<u8>, String> {
    let provider = provider_for(&info.udid).await?;
    let mut mux = usbmuxd().await?;
    let mut dict = lockdown_pairing(&info.udid, &provider, &mut mux).await?;
    if !version_below(&info.version, 17, 4) {
        for (key, value) in remote_pairing(app, &info.udid, &provider).await? {
            dict.insert(key, value);
        }
    }
    let mut out = Vec::new();
    plist::to_writer_xml(&mut out, &plist::Value::Dictionary(dict)).map_err(|e| e.to_string())?;
    Ok(out)
}

#[tauri::command]
pub async fn side_select_device(app: tauri::AppHandle, state: State<'_, SideState>, device: Option<DeviceInfo>) -> Result<(), String> {
    let Some(info) = device else {
        *state.device.lock().map_err(|e| e.to_string())? = None;
        return Ok(());
    };
    let pairing = pairing_bytes(&app, &info).await?;
    *state.device.lock().map_err(|e| e.to_string())? = Some(SelectedDevice { info, pairing });
    Ok(())
}

fn selected(state: &SideState) -> Result<SelectedDevice, String> {
    state.device.lock().map_err(|e| e.to_string())?.clone().ok_or_else(|| "Choose a device first".to_string())
}

// ---------- installing ----------

/// Only an .ipa or .app the person picked, as an absolute path to an existing file or folder.
pub fn clean_app_path(raw: &str) -> Result<PathBuf, String> {
    let path = PathBuf::from(raw);
    let lower = raw.to_lowercase();
    if !(lower.ends_with(".ipa") || lower.ends_with(".app")) {
        return Err("Expected an .ipa or .app".into());
    }
    path.canonicalize().map_err(|e| friendly("Cannot read that file", e))
}

async fn install_path(state: &SideState, path: PathBuf) -> Result<(), String> {
    let device = selected(state)?;
    let provider = provider_for(&device.info.udid).await?;
    let mut guard = EngineGuard::take(&state.sideloader)?;
    guard
        .get()
        .install_app(&provider, path, true, None::<fn(f32) -> std::future::Ready<()>>, Some(device.pairing.as_slice()))
        .await
        .map_err(explain)?;
    Ok(())
}

#[tauri::command]
pub async fn side_install_ipa(state: State<'_, SideState>, path: String) -> Result<(), String> {
    install_path(&state, clean_app_path(&path)?).await
}

/// Where the pairing file goes inside each app that reads one.
pub const PAIRING_APPS: &[(&str, &str)] = &[
    ("SideStore", "ALTPairingFile.mobiledevicepairing;PairingFile_RemoteRP.plist;PairingFile_Lockdown.plist"),
    ("LiveContainer", "SideStore/Documents/ALTPairingFile.mobiledevicepairing"),
    ("Feather", "pairingFile.plist"),
    ("StikDebug", "pairingFile.plist"),
    ("StikTest", "stiktest_pairing.plist"),
    ("Protokolle", "pairingFile.plist"),
    ("Antrag", "pairingFile.plist"),
    ("SparseBox", "pairingFile.plist"),
    ("StikStore", "pairingFile.plist"),
    ("Reynard", "pairingFile.plist"),
];

#[derive(Serialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct PairingApp {
    pub name: String,
    pub bundle_id: String,
    pub path: String,
}

async fn installed_apps(udid: &str) -> Result<HashMap<String, String>, String> {
    let provider = provider_for(udid).await?;
    let mut proxy = InstallationProxyClient::connect(&provider).await.map_err(|e| friendly("Could not reach the installation service", e))?;
    let apps = proxy.get_apps(Some("User"), None).await.map_err(|e| friendly("Could not list installed apps", e))?;
    let mut names = HashMap::new();
    for (bundle_id, app) in apps {
        if let Some(name) = app.as_dictionary().and_then(|d| d.get("CFBundleDisplayName")).and_then(|v| v.as_string()) {
            names.insert(name.to_string(), bundle_id);
        }
    }
    Ok(names)
}

/// Which known pairing-file apps are installed, given name → bundle id.
pub fn pairing_apps_from(installed: &HashMap<String, String>) -> Vec<PairingApp> {
    PAIRING_APPS
        .iter()
        .filter_map(|(name, path)| {
            installed.get(*name).map(|bundle| PairingApp { name: (*name).into(), bundle_id: bundle.clone(), path: (*path).into() })
        })
        .collect()
}

#[tauri::command]
pub async fn side_pairing_apps(state: State<'_, SideState>) -> Result<Vec<PairingApp>, String> {
    let device = selected(&state)?;
    Ok(pairing_apps_from(&installed_apps(&device.info.udid).await?))
}

async fn place(pairing: &[u8], udid: &str, bundle_id: &str, paths: &str) -> Result<(), String> {
    let provider = provider_for(udid).await?;
    let house = HouseArrestClient::connect(&provider).await.map_err(|e| friendly("Could not reach house arrest", e))?;
    let mut afc = house.vend_documents(bundle_id.to_string()).await.map_err(|e| friendly("The app did not open its Documents folder", e))?;
    for file in paths.split(';').map(str::trim).filter(|p| !p.is_empty()) {
        write_file(&mut afc, pairing, file).await?;
    }
    Ok(())
}

async fn write_file(afc: &mut AfcClient, bytes: &[u8], path: &str) -> Result<(), String> {
    let folder = path.rsplit_once('/').map(|x| x.0).unwrap_or("");
    afc.mk_dir(format!("/Documents/{folder}")).await.map_err(|e| friendly("Could not create the folder on the device", e))?;
    let mut file = afc
        .open(format!("/Documents/{path}"), idevice::afc::opcode::AfcFopenMode::Wr)
        .await
        .map_err(|e| friendly("Could not open the file on the device", e))?;
    file.write_entire(bytes).await.map_err(|e| friendly("Could not write the pairing file", e))?;
    file.close().await.map_err(|e| friendly("Could not close the file", e))?;
    Ok(())
}

#[tauri::command]
pub async fn side_place_pairing(state: State<'_, SideState>, bundle_id: String, path: String) -> Result<(), String> {
    let device = selected(&state)?;
    // Only the destinations this table knows, never a path typed by the caller.
    let allowed = PAIRING_APPS.iter().any(|(_, p)| *p == path);
    if !allowed {
        return Err("Unknown pairing destination".into());
    }
    place(&device.pairing, &device.info.udid, &bundle_id, &path).await
}

#[tauri::command]
pub async fn side_export_pairing(app: tauri::AppHandle, state: State<'_, SideState>) -> Result<(), String> {
    let device = selected(&state)?;
    let target = app
        .dialog()
        .file()
        .add_filter("Pairing file", &["plist", "mobiledevicepairing"])
        .set_file_name("pairingFile.plist")
        .set_title("Export pairing file")
        .blocking_save_file();
    let Some(path) = target.and_then(|p| p.into_path().ok()) else {
        return Err("Export canceled".into());
    };
    tokio::fs::write(path, &device.pairing).await.map_err(|e| friendly("Could not write the file", e))
}

#[tauri::command]
pub async fn side_install_sidestore(
    app: tauri::AppHandle,
    state: State<'_, SideState>,
    nightly: bool,
    live_container: bool,
) -> Result<(), String> {
    let (file, url) = sidestore_release(nightly, live_container);
    let dest = app.path().temp_dir().map_err(|e| e.to_string())?.join(file);
    download(url, &dest).await?;
    install_path(&state, dest).await?;
    let device = selected(&state)?;
    let installed = installed_apps(&device.info.udid).await?;
    let wanted: &[&str] = if live_container { &["SideStore", "LiveContainer"] } else { &["SideStore"] };
    let target = pairing_apps_from(&installed).into_iter().find(|a| wanted.contains(&a.name.as_str()));
    match target {
        Some(a) => place(&device.pairing, &device.info.udid, &a.bundle_id, &a.path).await,
        None => Err("The device did not report SideStore as installed".into()),
    }
}

/// The official release files, by channel. Nothing else is ever downloaded.
pub fn sidestore_release(nightly: bool, live_container: bool) -> (&'static str, &'static str) {
    match (live_container, nightly) {
        (true, true) => ("LiveContainerSideStore-Nightly.ipa", "https://github.com/LiveContainer/LiveContainer/releases/download/nightly/LiveContainer+SideStore.ipa"),
        (true, false) => ("LiveContainerSideStore.ipa", "https://github.com/LiveContainer/LiveContainer/releases/latest/download/LiveContainer+SideStore.ipa"),
        (false, true) => ("SideStore-Nightly.ipa", "https://github.com/SideStore/SideStore/releases/download/nightly/SideStore.ipa"),
        (false, false) => ("SideStore.ipa", "https://github.com/SideStore/SideStore/releases/latest/download/SideStore.ipa"),
    }
}

async fn download(url: &str, dest: &PathBuf) -> Result<(), String> {
    let response = reqwest::get(url).await.map_err(|e| friendly("Download failed", e))?;
    if !response.status().is_success() {
        return Err(format!("Download failed: HTTP {}", response.status()));
    }
    let bytes = response.bytes().await.map_err(|e| friendly("Download failed", e))?;
    tokio::fs::write(dest, &bytes).await.map_err(|e| friendly("Could not save the download", e))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn anisette_input_becomes_a_url() {
        assert_eq!(anisette_url("ani.example.io"), "https://ani.example.io");
        assert_eq!(anisette_url(" https://ani.example.io/ "), "https://ani.example.io");
        assert_eq!(anisette_url("http://localhost:6969"), "http://localhost:6969");
    }

    #[test]
    fn ios_version_decides_whether_remote_pairing_is_used() {
        assert!(version_below("16.7.2", 17, 4));
        assert!(version_below("17.3.1", 17, 4));
        assert!(!version_below("17.4", 17, 4));
        assert!(!version_below("18.0", 17, 4));
        assert!(version_below("", 17, 4));
    }

    #[test]
    fn only_plain_tokens_are_accepted_as_serials_and_app_ids() {
        assert!(clean_serial("5A1B-2C3D").is_ok());
        for bad in ["", "a b", "x;y", "../x", &"a".repeat(81)] {
            assert!(clean_serial(bad).is_err(), "{bad}");
        }
    }

    #[test]
    fn app_paths_must_be_existing_ipa_or_app() {
        assert!(clean_app_path("/etc/hosts").is_err());
        assert!(clean_app_path("/definitely/not/here.ipa").is_err());
        let file = std::env::temp_dir().join(format!("openswift-side-{}.ipa", std::process::id()));
        std::fs::write(&file, b"x").unwrap();
        assert!(clean_app_path(&file.display().to_string()).is_ok());
    }

    #[test]
    fn pairing_destinations_come_from_the_table() {
        let mut installed = HashMap::new();
        installed.insert("SideStore".to_string(), "com.SideStore.SideStore".to_string());
        installed.insert("Calculator".to_string(), "com.apple.calc".to_string());
        let found = pairing_apps_from(&installed);
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].bundle_id, "com.SideStore.SideStore");
        assert!(found[0].path.contains("ALTPairingFile.mobiledevicepairing"));
    }

    #[test]
    fn sidestore_downloads_are_the_four_official_releases() {
        let mut urls = Vec::new();
        for live in [false, true] {
            for nightly in [false, true] {
                let (name, url) = sidestore_release(nightly, live);
                assert!(name.ends_with(".ipa"));
                assert!(url.starts_with("https://github.com/SideStore/SideStore/") || url.starts_with("https://github.com/LiveContainer/LiveContainer/"));
                urls.push(url);
            }
        }
        urls.sort();
        urls.dedup();
        assert_eq!(urls.len(), 4);
    }
}
