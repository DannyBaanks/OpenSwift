//! Runs the `xtool` CLI (https://github.com/xtool-org/xtool) for the Studio window.
//!
//! OpenSwift does not link xtool. It starts the real binary inside a pseudo
//! terminal, so its own prompts (Apple ID, password, 2FA code, team) work, and
//! streams what it prints. Only the actions listed in `build_args` can be run,
//! and every argument is checked first.

use std::collections::HashMap;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use portable_pty::{native_pty_system, CommandBuilder, PtySize};
use serde::Serialize;

/// How to start xtool: a program plus any leading arguments (`wsl.exe`, `xtool`).
#[derive(Clone, Debug, PartialEq)]
pub struct Launcher {
    pub program: String,
    pub prefix: Vec<String>,
    pub via_wsl: bool,
}

/// Finds xtool: `OPENSWIFT_XTOOL`, then PATH and the usual install folders, then WSL on Windows.
pub fn find_xtool() -> Option<Launcher> {
    if let Ok(custom) = std::env::var("OPENSWIFT_XTOOL") {
        if Path::new(&custom).is_file() {
            return Some(Launcher { program: custom, prefix: vec![], via_wsl: false });
        }
    }
    let name = if cfg!(windows) { "xtool.exe" } else { "xtool" };
    let mut dirs: Vec<PathBuf> = std::env::var_os("PATH")
        .map(|p| std::env::split_paths(&p).collect())
        .unwrap_or_default();
    if let Some(home) = std::env::var_os("HOME").or_else(|| std::env::var_os("USERPROFILE")) {
        dirs.push(PathBuf::from(&home).join(".local/bin"));
        dirs.push(PathBuf::from(&home).join(".swiftpm/bin"));
    }
    dirs.push(PathBuf::from("/usr/local/bin"));
    for dir in dirs {
        let candidate = dir.join(name);
        if candidate.is_file() {
            return Some(Launcher { program: candidate.display().to_string(), prefix: vec![], via_wsl: false });
        }
    }
    if cfg!(windows) {
        let probe = Command::new("wsl.exe")
            .args(["-e", "sh", "-lc", "command -v xtool"])
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .output()
            .ok()?;
        if probe.status.success() && !probe.stdout.is_empty() {
            return Some(Launcher {
                program: "wsl.exe".into(),
                prefix: vec!["-e".into(), "xtool".into()],
                via_wsl: true,
            });
        }
    }
    None
}

fn clean_text(value: &str, max: usize) -> Result<String, String> {
    let value = value.trim();
    if value.is_empty() || value.len() > max {
        return Err("value is empty or too long".into());
    }
    if value.starts_with('-') || value.chars().any(|c| c.is_control() || c.is_whitespace()) {
        return Err("value has characters xtool arguments cannot carry".into());
    }
    Ok(value.to_string())
}

fn clean_udid(value: &str) -> Result<String, String> {
    let value = value.trim();
    let ok = (8..=64).contains(&value.len()) && value.chars().all(|c| c.is_ascii_hexdigit() || c == '-');
    if ok { Ok(value.to_string()) } else { Err("not a device UDID".into()) }
}

fn clean_package_name(value: &str) -> Result<String, String> {
    let mut chars = value.chars();
    let first_ok = chars.next().map_or(false, |c| c.is_ascii_alphabetic() || c == '_');
    if first_ok && value.len() <= 64 && chars.all(|c| c.is_ascii_alphanumeric() || c == '_') {
        Ok(value.to_string())
    } else {
        Err("package names use letters, digits and _, and cannot start with a digit".into())
    }
}

#[derive(Default, Debug, Clone, serde::Deserialize)]
pub struct Params {
    pub udid: Option<String>,
    pub username: Option<String>,
    pub name: Option<String>,
    pub path: Option<String>,
    #[serde(default)]
    pub sign: bool,
    #[serde(default)]
    pub ipa: bool,
    #[serde(default)]
    pub reset_2fa: bool,
}

fn needs_project(root: &Path) -> Result<(), String> {
    if root.join("Package.swift").is_file() {
        Ok(())
    } else {
        Err("this folder is not an xtool project (no Package.swift). Create one with the New project button.".into())
    }
}

/// The only commands the window can start. Anything else is refused.
pub fn build_args(action: &str, params: &Params, root: &Path) -> Result<Vec<String>, String> {
    let s = |items: &[&str]| items.iter().map(|i| i.to_string()).collect::<Vec<_>>();
    let mut args = match action {
        "version" => s(&["--version"]),
        "auth-status" => s(&["auth", "status"]),
        "sdk-status" => s(&["sdk", "status"]),
        "devices" => s(&["devices", "--no-wait"]),
        "setup" => s(&["setup"]),
        "auth-login" => {
            let mut a = s(&["auth", "login", "--mode", "password"]);
            if let Some(user) = params.username.as_deref().filter(|u| !u.trim().is_empty()) {
                a.push("--username".into());
                a.push(clean_text(user, 254)?);
            }
            a
        }
        "auth-logout" => {
            let mut a = s(&["auth", "logout"]);
            if params.reset_2fa {
                a.push("--reset-2fa".into());
            }
            a
        }
        "new" => {
            let name = clean_package_name(params.name.as_deref().unwrap_or(""))?;
            vec!["new".into(), name, "--skip-setup".into()]
        }
        "build" => {
            needs_project(root)?;
            let mut a = s(&["dev", "build"]);
            if params.sign {
                a.push("--sign".into());
            }
            if params.ipa {
                a.push("--ipa".into());
            }
            a
        }
        "run" => {
            needs_project(root)?;
            let mut a = s(&["dev", "run"]);
            if let Some(udid) = params.udid.as_deref() {
                a.push("--udid".into());
                a.push(clean_udid(udid)?);
            }
            a
        }
        "install" => {
            let udid = clean_udid(params.udid.as_deref().ok_or("choose a device first")?)?;
            let raw = params.path.as_deref().ok_or("choose an .ipa or .app")?;
            let full = PathBuf::from(raw).canonicalize().map_err(|e| e.to_string())?;
            if !full.starts_with(root) {
                return Err("only files inside the project can be installed".into());
            }
            let lower = full.to_string_lossy().to_lowercase();
            if !(lower.ends_with(".ipa") || lower.ends_with(".app")) {
                return Err("expected an .ipa or .app".into());
            }
            vec!["install".into(), full.display().to_string(), "--udid".into(), udid]
        }
        other => return Err(format!("unknown xtool action {other}")),
    };
    // Interactive prompts need a terminal; nothing here asks xtool to read secrets from argv.
    args.shrink_to_fit();
    Ok(args)
}

// ---------- reading what xtool prints ----------

pub fn strip_ansi(input: &str) -> String {
    let mut out = String::with_capacity(input.len());
    let mut chars = input.chars().peekable();
    while let Some(c) = chars.next() {
        if c != '\u{1b}' {
            out.push(c);
            continue;
        }
        match chars.peek() {
            Some('[') => {
                chars.next();
                for n in chars.by_ref() {
                    if ('@'..='~').contains(&n) {
                        break;
                    }
                }
            }
            Some(']') => {
                chars.next();
                while let Some(n) = chars.next() {
                    if n == '\u{7}' || (n == '\u{1b}' && chars.peek() == Some(&'\\')) {
                        break;
                    }
                }
            }
            _ => {
                chars.next();
            }
        }
    }
    out
}

/// Turns a terminal byte stream into lines. A lone `\r` rewrites the current line,
/// which is how progress bars ("Packaging... 40%") draw.
#[derive(Default)]
pub struct LineBuf {
    pub lines: Vec<String>,
    pub partial: String,
    pending_cr: bool,
}

impl LineBuf {
    pub fn feed(&mut self, text: &str) {
        for c in strip_ansi(text).chars() {
            match c {
                '\r' => self.pending_cr = true,
                '\n' => {
                    self.pending_cr = false;
                    let line = std::mem::take(&mut self.partial);
                    self.lines.push(line);
                }
                c if c.is_control() && c != '\t' => {}
                c => {
                    if self.pending_cr {
                        self.partial.clear();
                        self.pending_cr = false;
                    }
                    self.partial.push(c);
                }
            }
        }
    }
}

#[derive(Serialize, Debug, PartialEq, Clone)]
pub struct DeviceInfo {
    pub name: String,
    pub connection: String,
    pub udid: String,
}

/// `iPhone de Ana [USB]: 00008110-...`, one per line, as `xtool devices` prints them.
pub fn parse_devices(text: &str) -> Vec<DeviceInfo> {
    text.lines()
        .filter_map(|line| {
            let (head, udid) = line.rsplit_once("]: ")?;
            let (name, connection) = head.rsplit_once(" [")?;
            let udid = udid.trim();
            if name.trim().is_empty() || clean_udid(udid).is_err() {
                return None;
            }
            Some(DeviceInfo { name: name.trim().into(), connection: connection.trim().into(), udid: udid.into() })
        })
        .collect()
}

#[derive(Serialize, Debug, PartialEq, Clone)]
pub struct AuthInfo {
    pub logged_in: bool,
    pub detail: String,
}

pub fn parse_auth_status(text: &str) -> AuthInfo {
    let text = strip_ansi(text);
    let logged_in = text.contains("Logged in") && !text.contains("Logged out");
    let detail = text.lines().skip(1).map(str::trim).filter(|l| !l.is_empty()).collect::<Vec<_>>().join(" · ");
    AuthInfo { logged_in, detail }
}

#[derive(Serialize, Debug, PartialEq, Clone)]
pub struct SdkInfo {
    pub installed: bool,
    pub version: String,
}

pub fn parse_sdk_status(text: &str) -> SdkInfo {
    let text = strip_ansi(text);
    let installed = text.contains("Darwin SDK is installed");
    let version = text
        .lines()
        .find_map(|l| l.trim().strip_prefix("Version:").map(|v| v.trim().to_string()))
        .unwrap_or_default();
    SdkInfo { installed, version }
}

// ---------- running it ----------

fn capture(launcher: &Launcher, args: &[String], cwd: &Path, limit: Duration) -> Result<String, String> {
    let mut cmd = Command::new(&launcher.program);
    cmd.args(&launcher.prefix).args(args).current_dir(cwd).stdin(Stdio::null()).stdout(Stdio::piped()).stderr(Stdio::piped());
    let mut child = cmd.spawn().map_err(|e| format!("{}: {e}", launcher.program))?;
    let mut out = child.stdout.take().ok_or("no stdout")?;
    let mut err = child.stderr.take().ok_or("no stderr")?;
    let reader = std::thread::spawn(move || {
        let (mut a, mut b) = (String::new(), String::new());
        let _ = out.read_to_string(&mut a);
        let _ = err.read_to_string(&mut b);
        a + &b
    });
    let started = Instant::now();
    loop {
        match child.try_wait().map_err(|e| e.to_string())? {
            Some(_) => break,
            None if started.elapsed() > limit => {
                let _ = child.kill();
                let _ = child.wait();
                return Err("xtool did not answer in time".into());
            }
            None => std::thread::sleep(Duration::from_millis(40)),
        }
    }
    reader.join().map_err(|_| "reader panicked".to_string())
}

#[derive(Serialize, Debug, Clone)]
pub struct XtoolStatus {
    pub installed: bool,
    pub path: String,
    pub via_wsl: bool,
    pub version: String,
    pub sdk: SdkInfo,
    pub auth: AuthInfo,
    pub project_ready: bool,
    pub host: String,
}

pub fn status(launcher: Option<&Launcher>, root: &Path) -> XtoolStatus {
    let host = std::env::consts::OS.to_string();
    let project_ready = root.join("Package.swift").is_file();
    let Some(l) = launcher else {
        return XtoolStatus {
            installed: false,
            path: String::new(),
            via_wsl: false,
            version: String::new(),
            sdk: SdkInfo { installed: false, version: String::new() },
            auth: AuthInfo { logged_in: false, detail: String::new() },
            project_ready,
            host,
        };
    };
    let run = |action: &str| {
        build_args(action, &Params::default(), root)
            .and_then(|a| capture(l, &a, root, Duration::from_secs(20)))
            .unwrap_or_default()
    };
    XtoolStatus {
        installed: true,
        path: format!("{} {}", l.program, l.prefix.join(" ")).trim().to_string(),
        via_wsl: l.via_wsl,
        version: strip_ansi(&run("version")).trim().to_string(),
        sdk: parse_sdk_status(&run("sdk-status")),
        auth: parse_auth_status(&run("auth-status")),
        project_ready,
        host,
    }
}

pub fn list_devices(launcher: &Launcher, root: &Path) -> Result<Vec<DeviceInfo>, String> {
    let args = build_args("devices", &Params::default(), root)?;
    Ok(parse_devices(&strip_ansi(&capture(launcher, &args, root, Duration::from_secs(25))?)))
}

pub struct Job {
    buf: Mutex<LineBuf>,
    done: AtomicBool,
    code: Mutex<Option<i32>>,
    last_output: Mutex<Instant>,
    writer: Mutex<Option<Box<dyn Write + Send>>>,
    killer: Mutex<Option<Box<dyn portable_pty::ChildKiller + Send + Sync>>>,
    pub action: String,
}

#[derive(Serialize, Debug, Clone)]
pub struct Poll {
    pub lines: Vec<String>,
    pub next: usize,
    pub done: bool,
    pub code: Option<i32>,
    pub prompt: String,
    pub secret: bool,
    pub action: String,
}

#[derive(Default)]
pub struct Jobs {
    jobs: Mutex<HashMap<u32, Arc<Job>>>,
    counter: AtomicU32,
}

impl Jobs {
    fn running(&self) -> bool {
        self.jobs.lock().map(|j| j.values().any(|job| !job.done.load(Ordering::SeqCst))).unwrap_or(false)
    }

    /// Starts one job at a time inside a pseudo terminal.
    pub fn start(&self, launcher: &Launcher, args: Vec<String>, cwd: &Path, action: &str) -> Result<u32, String> {
        if self.running() {
            return Err("another xtool job is still running. Cancel it or wait for it to finish.".into());
        }
        let pair = native_pty_system()
            .openpty(PtySize { rows: 40, cols: 120, pixel_width: 0, pixel_height: 0 })
            .map_err(|e| e.to_string())?;
        let mut cmd = CommandBuilder::new(&launcher.program);
        for p in &launcher.prefix {
            cmd.arg(p);
        }
        for a in &args {
            cmd.arg(a);
        }
        cmd.cwd(cwd);
        cmd.env("TERM", "dumb");
        cmd.env("NO_COLOR", "1");
        let mut child = pair.slave.spawn_command(cmd).map_err(|e| format!("{}: {e}", launcher.program))?;
        drop(pair.slave);
        let mut reader = pair.master.try_clone_reader().map_err(|e| e.to_string())?;
        let writer = pair.master.take_writer().map_err(|e| e.to_string())?;
        let job = Arc::new(Job {
            buf: Mutex::new(LineBuf::default()),
            done: AtomicBool::new(false),
            code: Mutex::new(None),
            last_output: Mutex::new(Instant::now()),
            writer: Mutex::new(Some(writer)),
            killer: Mutex::new(Some(child.clone_killer())),
            action: action.to_string(),
        });
        let id = self.counter.fetch_add(1, Ordering::SeqCst) + 1;
        self.jobs.lock().map_err(|e| e.to_string())?.insert(id, job.clone());

        let reading = job.clone();
        let read_thread = std::thread::spawn(move || {
            let mut chunk = [0u8; 4096];
            let mut carry: Vec<u8> = Vec::new();
            loop {
                match reader.read(&mut chunk) {
                    Ok(0) | Err(_) => break,
                    Ok(n) => {
                        carry.extend_from_slice(&chunk[..n]);
                        let valid = match std::str::from_utf8(&carry) {
                            Ok(_) => carry.len(),
                            Err(e) => e.valid_up_to(),
                        };
                        let text = String::from_utf8_lossy(&carry[..valid]).to_string();
                        carry.drain(..valid);
                        if let Ok(mut buf) = reading.buf.lock() {
                            buf.feed(&text);
                        }
                        if let Ok(mut t) = reading.last_output.lock() {
                            *t = Instant::now();
                        }
                    }
                }
            }
        });
        let waiting = job.clone();
        std::thread::spawn(move || {
            let status = child.wait();
            // Let the reader drain what is left before the job is marked done.
            drop(pair.master);
            let _ = read_thread.join();
            if let Ok(mut buf) = waiting.buf.lock() {
                let rest = std::mem::take(&mut buf.partial);
                if !rest.is_empty() {
                    buf.lines.push(rest);
                }
            }
            if let Ok(mut code) = waiting.code.lock() {
                *code = status.ok().map(|s| s.exit_code() as i32);
            }
            if let Ok(mut w) = waiting.writer.lock() {
                *w = None;
            }
            waiting.done.store(true, Ordering::SeqCst);
        });
        Ok(id)
    }

    fn get(&self, id: u32) -> Result<Arc<Job>, String> {
        self.jobs.lock().map_err(|e| e.to_string())?.get(&id).cloned().ok_or_else(|| "unknown job".to_string())
    }

    pub fn poll(&self, id: u32, since: usize) -> Result<Poll, String> {
        let job = self.get(id)?;
        let done = job.done.load(Ordering::SeqCst);
        let buf = job.buf.lock().map_err(|e| e.to_string())?;
        let from = since.min(buf.lines.len());
        let idle = job.last_output.lock().map(|t| t.elapsed() > Duration::from_millis(350)).unwrap_or(false);
        // A prompt is a half-written line that stopped growing while the job is still waiting.
        let prompt = if !done && idle && !buf.partial.trim().is_empty() { buf.partial.clone() } else { String::new() };
        let secret = prompt.to_lowercase().contains("password");
        let code = *job.code.lock().map_err(|e| e.to_string())?;
        let lines = buf.lines[from..].to_vec();
        let next = buf.lines.len();
        Ok(Poll {
            lines,
            next,
            done,
            code,
            prompt,
            secret,
            action: job.action.clone(),
        })
    }

    /// Types one answer into the job. A secret answer is never kept anywhere.
    pub fn input(&self, id: u32, text: &str) -> Result<(), String> {
        let job = self.get(id)?;
        let mut writer = job.writer.lock().map_err(|e| e.to_string())?;
        let w = writer.as_mut().ok_or("the job already finished")?;
        w.write_all(text.as_bytes()).map_err(|e| e.to_string())?;
        w.write_all(b"\n").map_err(|e| e.to_string())?;
        w.flush().map_err(|e| e.to_string())?;
        if let Ok(mut buf) = job.buf.lock() {
            buf.partial.clear();
        }
        Ok(())
    }

    pub fn cancel(&self, id: u32) -> Result<(), String> {
        let job = self.get(id)?;
        if let Ok(mut k) = job.killer.lock() {
            if let Some(killer) = k.as_mut() {
                let _ = killer.kill();
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn root_with_package() -> PathBuf {
        let dir = std::env::temp_dir().join(format!("openswift-xtool-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("Package.swift"), "// swift-tools-version: 6.0").unwrap();
        dir.canonicalize().unwrap()
    }

    #[test]
    fn only_known_actions_with_checked_arguments() {
        let root = root_with_package();
        let p = Params { sign: true, ipa: true, ..Params::default() };
        assert_eq!(build_args("build", &p, &root).unwrap(), ["dev", "build", "--sign", "--ipa"]);
        assert_eq!(build_args("devices", &Params::default(), &root).unwrap(), ["devices", "--no-wait"]);
        assert!(build_args("rm -rf", &Params::default(), &root).is_err());
        let run = Params { udid: Some("00008110-001A2B3C4D5E801E".into()), ..Params::default() };
        assert_eq!(build_args("run", &run, &root).unwrap(), ["dev", "run", "--udid", "00008110-001A2B3C4D5E801E"]);
        let bad = Params { udid: Some("--help".into()), ..Params::default() };
        assert!(build_args("run", &bad, &root).is_err());
        let flag = Params { username: Some("--password".into()), ..Params::default() };
        assert!(build_args("auth-login", &flag, &root).is_err());
        let spaced = Params { username: Some("a b".into()), ..Params::default() };
        assert!(build_args("auth-login", &spaced, &root).is_err());
        let ok = Params { username: Some("ana@example.com".into()), ..Params::default() };
        assert_eq!(
            build_args("auth-login", &ok, &root).unwrap(),
            ["auth", "login", "--mode", "password", "--username", "ana@example.com"]
        );
    }

    #[test]
    fn build_and_run_need_a_package_and_install_stays_inside_the_project() {
        let empty = std::env::temp_dir().join(format!("openswift-xtool-empty-{}", std::process::id()));
        std::fs::create_dir_all(&empty).unwrap();
        assert!(build_args("build", &Params::default(), &empty).is_err());
        let root = root_with_package();
        std::fs::write(root.join("App.ipa"), b"x").unwrap();
        let inside = Params { udid: Some("00008110-AAAA".into()), path: Some(root.join("App.ipa").display().to_string()), ..Params::default() };
        assert!(build_args("install", &inside, &root).is_ok());
        let outside = Params { udid: Some("00008110-AAAA".into()), path: Some("/etc/hosts".into()), ..Params::default() };
        assert!(build_args("install", &outside, &root).is_err());
        let wrong = Params { udid: Some("00008110-AAAA".into()), path: Some(root.join("Package.swift").display().to_string()), ..Params::default() };
        assert!(build_args("install", &wrong, &root).is_err());
        assert!(build_args("new", &Params { name: Some("1bad".into()), ..Params::default() }, &root).is_err());
        assert_eq!(
            build_args("new", &Params { name: Some("Hello_App".into()), ..Params::default() }, &root).unwrap(),
            ["new", "Hello_App", "--skip-setup"]
        );
    }

    #[test]
    fn terminal_bytes_become_lines_and_progress_rewrites_in_place() {
        let mut b = LineBuf::default();
        b.feed("\u{1b}[32mok\u{1b}[0m\r\nPackaging... 10%\rPackaging... 90%\rPackaging... 100%\r\ndone\nApple ID: ");
        assert_eq!(b.lines, ["ok", "Packaging... 100%", "done"]);
        assert_eq!(b.partial, "Apple ID: ");
    }

    #[test]
    fn status_text_is_parsed() {
        let devices = "Waiting for devices...\nAna's iPhone [USB]: 00008110-001A2B3C4D5E801E\nPad [Network]: ABCDEF12-3456\n";
        let found = parse_devices(devices);
        assert_eq!(found.len(), 2);
        assert_eq!(found[0].name, "Ana's iPhone");
        assert_eq!(found[1].connection, "Network");
        assert!(parse_auth_status("Logged in.\nana@example.com (team ABC)").logged_in);
        assert!(!parse_auth_status("Logged out").logged_in);
        let sdk = parse_sdk_status("Darwin SDK is installed\n  Path: /x\n  Version: 16.2\n");
        assert!(sdk.installed);
        assert_eq!(sdk.version, "16.2");
        assert!(!parse_sdk_status("Not installed").installed);
    }

    #[test]
    fn status_without_xtool_says_so_and_still_reports_the_project() {
        let root = root_with_package();
        let s = status(None, &root);
        assert!(!s.installed);
        assert!(s.project_ready);
        assert!(!s.auth.logged_in && !s.sdk.installed);
    }

    #[cfg(unix)]
    #[test]
    fn a_job_streams_output_answers_prompts_and_reports_the_exit_code() {
        use std::os::unix::fs::PermissionsExt;
        let dir = std::env::temp_dir().join(format!("openswift-fake-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let fake = dir.join("fake-xtool");
        std::fs::write(
            &fake,
            "#!/bin/sh\necho \"args: $@\"\nprintf 'Apple ID: '\nread user\nprintf 'Password: '\nstty -echo\nread pass\nstty echo\necho\necho \"hello $user ${#pass}\"\nexit 3\n",
        )
        .unwrap();
        std::fs::set_permissions(&fake, std::fs::Permissions::from_mode(0o755)).unwrap();
        let launcher = Launcher { program: fake.display().to_string(), prefix: vec![], via_wsl: false };
        let jobs = Jobs::default();
        let id = jobs.start(&launcher, vec!["auth".into(), "login".into()], &dir, "auth-login").unwrap();
        assert!(jobs.start(&launcher, vec![], &dir, "x").is_err(), "one job at a time");

        let mut seen = Vec::new();
        let mut next = 0;
        let mut answered = 0;
        let started = Instant::now();
        loop {
            let poll = jobs.poll(id, next).unwrap();
            next = poll.next;
            seen.extend(poll.lines.clone());
            if !poll.prompt.is_empty() {
                if poll.prompt.contains("Apple ID") && answered == 0 {
                    jobs.input(id, "ana").unwrap();
                    answered = 1;
                } else if poll.secret && answered == 1 {
                    jobs.input(id, "s3cret").unwrap();
                    answered = 2;
                }
            }
            if poll.done {
                assert_eq!(poll.code, Some(3));
                break;
            }
            assert!(started.elapsed() < Duration::from_secs(15), "job timed out: {seen:?}");
            std::thread::sleep(Duration::from_millis(50));
        }
        let all = seen.join("\n");
        assert!(all.contains("args: auth login"), "{all}");
        assert!(all.contains("hello ana 6"), "{all}");
        assert!(!all.contains("s3cret"), "the password must never show: {all}");
    }
}
