use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::Mutex;

use tauri::State;

struct Project(Mutex<PathBuf>);

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
}

fn inside(root: &Path, raw: &str) -> Result<PathBuf, String> {
    let path = PathBuf::from(raw);
    let full = if path.is_absolute() { path } else { root.join(path) };
    let full = full.canonicalize().map_err(|e| e.to_string())?;
    if full != root && !full.starts_with(root) {
        return Err("path escapes the project".into());
    }
    Ok(full)
}

fn swift_files(root: &Path) -> Vec<String> {
    let mut out = Vec::new();
    walkdir_simple(root, root, &mut out);
    out.sort();
    out
}

fn walkdir_simple(root: &Path, dir: &Path, out: &mut Vec<String>) {
    let entries = match fs::read_dir(dir) {
        Ok(entries) => entries,
        Err(_) => return,
    };
    for entry in entries.flatten() {
        let path = entry.path();
        let name = entry.file_name().to_string_lossy().to_string();
        if name.starts_with('.') || name == "node_modules" || name == "target" {
            continue;
        }
        if path.is_dir() {
            walkdir_simple(root, &path, out);
        } else if name.ends_with(".swift") {
            if let Ok(rel) = path.strip_prefix(root) {
                out.push(rel.to_string_lossy().replace('\\', "/"));
            }
        }
    }
}

#[tauri::command]
fn project_info(state: State<Project>) -> Result<serde_json::Value, String> {
    let root = state.0.lock().map_err(|e| e.to_string())?;
    Ok(serde_json::json!({
        "root": root.display().to_string(),
        "files": swift_files(&root),
    }))
}

#[tauri::command]
fn set_project(state: State<Project>, path: String) -> Result<(), String> {
    let next = PathBuf::from(&path).canonicalize().map_err(|e| e.to_string())?;
    if !next.is_dir() {
        return Err("not a directory".into());
    }
    *state.0.lock().map_err(|e| e.to_string())? = next;
    Ok(())
}

#[tauri::command]
fn read_source(state: State<Project>, path: String) -> Result<String, String> {
    let root = state.0.lock().map_err(|e| e.to_string())?;
    let file = inside(&root, &path)?;
    fs::read_to_string(file).map_err(|e| e.to_string())
}

#[tauri::command]
fn write_source(state: State<Project>, path: String, text: String) -> Result<(), String> {
    let root = state.0.lock().map_err(|e| e.to_string())?;
    let file = inside(&root, &path)?;
    fs::write(file, text).map_err(|e| e.to_string())
}

fn python_json(args: &[&str], source: &str) -> Result<serde_json::Value, String> {
    let root = repo_root();
    let mut child = Command::new("python3")
        .args(args)
        .current_dir(&root)
        .env("PYTHONPATH", &root)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("python3: {e}"))?;
    {
        let mut stdin = child.stdin.take().ok_or("no stdin")?;
        stdin.write_all(source.as_bytes()).map_err(|e| e.to_string())?;
    }
    let output = child.wait_with_output().map_err(|e| e.to_string())?;
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }
    serde_json::from_slice(&output.stdout).map_err(|e| e.to_string())
}

#[tauri::command]
fn highlight_source(source: String) -> Result<serde_json::Value, String> {
    let root = repo_root();
    let lex = root.join("bin/openswift-lex");
    let mut child = Command::new(&lex)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("{}: {e}", lex.display()))?;
    {
        let mut stdin = child.stdin.take().ok_or("no stdin")?;
        stdin.write_all(source.as_bytes()).map_err(|e| e.to_string())?;
    }
    let output = child.wait_with_output().map_err(|e| e.to_string())?;
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }
    serde_json::from_slice(&output.stdout).map_err(|e| e.to_string())
}

#[tauri::command]
fn render_source(source: String) -> Result<serde_json::Value, String> {
    python_json(&["-m", "openswift", "sketch", "-"], &source)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let start = repo_root().canonicalize().unwrap_or(repo_root());
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(Project(Mutex::new(start)))
        .invoke_handler(tauri::generate_handler![
            project_info,
            set_project,
            read_source,
            write_source,
            render_source,
            highlight_source
        ])
        .run(tauri::generate_context!())
        .expect("error while running OpenSwift");
}
