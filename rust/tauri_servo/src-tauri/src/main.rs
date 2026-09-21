//! Tauri × Servo 探索台的宿主进程。
//!
//! 与 Tauri 默认模板的两点差异，都是刻意的：
//!
//! 1. **不设置 `windows_subsystem = "windows"`**。保留控制台才能看到 Servo / Verso 的日志，
//!    也让自动化报告模式能通过 stdout 回传结果。要做「双击即用」的发行版时再加回来。
//! 2. **用 `tauri_runtime_verso::builder()` 取代 `tauri::Builder::new()`**，
//!    把渲染引擎从 WebView2 换成 Servo。

use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::Instant;

use serde::Serialize;
use tauri::State;

/// 回传结果时使用的分隔标记，供 `scripts/bench.js` 解析。
const REPORT_BEGIN: &str = "___VERSO_REPORT_BEGIN___";
const REPORT_END: &str = "___VERSO_REPORT_END___";
/// 冷启动耗时（进程入口 -> 页面脚本执行完毕并回传）的分隔标记。
const STARTUP_MARK: &str = "___VERSO_STARTUP_MS___";

/// 本应用使用的 Tauri runtime。
///
/// Tauri 的 `AppHandle` 等类型带 runtime 泛型参数，命令签名里必须写具体类型，
/// 否则会编译失败（trait bound `CommandArg<'_, VersoRuntime>` is not satisfied）。
type Runtime = tauri_runtime_verso::VersoRuntime;

/// 宿主的运行期状态。
struct HostState {
    /// 是否为 `--compat-report` 自动化模式。
    report_mode: bool,
    /// Verso DevTools 端口，0 表示未启用。
    devtools_port: u16,
    /// 实际使用的 versoview 二进制路径。
    verso_path: Option<PathBuf>,
    /// 进程入口时刻，用于计算冷启动耗时。
    started_at: Instant,
    /// 回传报告后继续驻留的毫秒数，便于外部测量内存占用。
    hold_ms: u64,
}

/// 返回给前端的宿主信息。
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct AppInfo {
    /// 应用名。
    name: String,
    /// 应用版本。
    version: String,
    /// 链接进来的 Tauri 版本。
    tauri_version: &'static str,
    /// 构建类型。
    profile: &'static str,
    /// 编译目标三元组。
    target: &'static str,
    /// 当前可执行文件路径。
    exe_path: String,
    /// versoview 二进制路径（未找到时为空串）。
    verso_path: String,
    /// Verso DevTools 端口。
    devtools_port: u16,
    /// 是否处于自动化报告模式。
    report_mode: bool,
}

/// 当前构建产物的文件名，例如 `versoview-x86_64-pc-windows-msvc.exe`。
fn versoview_file_name() -> String {
    let target = env!("BUILD_TARGET");
    if cfg!(windows) {
        format!("versoview-{target}.exe")
    } else {
        format!("versoview-{target}")
    }
}

/// 定位 versoview：优先用可执行文件旁边那份（打包后的形态），
/// 开发期则退回构建脚本下载到源码目录里的那份。
///
/// 返回 `(路径, 是否需要显式告知 runtime)`。
fn resolve_verso_path() -> Option<(PathBuf, bool)> {
    let file_name = versoview_file_name();

    if let Some(dir) = std::env::current_exe().ok().and_then(|p| p.parent().map(Path::to_path_buf)) {
        let beside_exe = dir.join(&file_name);
        if beside_exe.is_file() {
            return Some((beside_exe, false));
        }
    }

    let in_source = Path::new(env!("CARGO_MANIFEST_DIR")).join("versoview").join(&file_name);
    if in_source.is_file() {
        return Some((in_source, true));
    }

    None
}

/// 解析 DevTools 端口：命令行 `--devtools <port>` 优先，其次环境变量 `VERSO_DEVTOOLS_PORT`。
fn resolve_devtools_port(args: &[String]) -> u16 {
    if let Some(index) = args.iter().position(|a| a == "--devtools") {
        if let Some(value) = args.get(index + 1) {
            if let Ok(port) = value.parse() {
                return port;
            }
        }
    }

    std::env::var("VERSO_DEVTOOLS_PORT")
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(0)
}

/// 解析 `--hold-ms <毫秒>`：回传报告后继续驻留的时间，便于外部采样内存占用。
fn resolve_hold_ms(args: &[String]) -> u64 {
    if let Some(index) = args.iter().position(|a| a == "--hold-ms") {
        if let Some(value) = args.get(index + 1) {
            if let Ok(ms) = value.parse() {
                return ms;
            }
        }
    }

    0
}

/// 打印可用的命令行参数。
fn print_usage() {
    println!("Tauri × Servo 探索台\n");
    println!("用法: tauri-servo-lab [选项]\n");
    println!("选项:");
    println!("  --compat-report        采集兼容性矩阵后通过 stdout 回传并退出（供自动化使用）");
    println!("  --hold-ms <毫秒>       回传后继续驻留指定时长，便于外部采样内存占用");
    println!("  --devtools <端口>      启动 Verso DevTools 服务，用 Firefox 的 about:debugging 连接");
    println!("  -h, --help             显示本帮助");
}

/// 把宿主信息交给前端展示。
#[tauri::command]
fn get_app_info(app: tauri::AppHandle<Runtime>, state: State<'_, HostState>) -> AppInfo {
    let package = app.package_info();

    AppInfo {
        name: package.name.clone(),
        version: package.version.to_string(),
        tauri_version: tauri::VERSION,
        profile: if cfg!(debug_assertions) { "debug" } else { "release" },
        target: env!("BUILD_TARGET"),
        exe_path: std::env::current_exe()
            .map(|p| p.display().to_string())
            .unwrap_or_else(|_| "未知".to_string()),
        verso_path: state
            .verso_path
            .as_ref()
            .map(|p| p.display().to_string())
            .unwrap_or_default(),
        devtools_port: state.devtools_port,
        report_mode: state.report_mode,
    }
}

/// 接收前端回传的报告。自动化模式下打印到 stdout（可选驻留一段时间）后退出。
#[tauri::command]
fn submit_report(kind: String, payload: String, state: State<'_, HostState>) -> String {
    if state.report_mode {
        let startup_ms = state.started_at.elapsed().as_secs_f64() * 1000.0;

        println!("{STARTUP_MARK} {startup_ms:.1}");
        println!("{REPORT_BEGIN}");
        println!("{payload}");
        println!("{REPORT_END}");
        let _ = std::io::stdout().flush();

        // 驻留一小段时间：外部测量工具需要进程存活才能读到内存占用。
        if state.hold_ms > 0 {
            std::thread::sleep(std::time::Duration::from_millis(state.hold_ms));
        }

        // 已经拿到结果，直接退出，避免自动化流程等待窗口关闭。
        std::process::exit(0);
    }

    format!("已接收 {kind} 报告（{} 字节），非自动化模式，仅记录。", payload.len())
}

fn main() {
    // 冷启动计时的起点放在最前面，尽量贴近进程入口。
    let started_at = Instant::now();
    let args: Vec<String> = std::env::args().skip(1).collect();

    if args.iter().any(|a| a == "--help" || a == "-h") {
        print_usage();
        return;
    }

    let report_mode = args.iter().any(|a| a == "--compat-report");
    let devtools_port = resolve_devtools_port(&args);
    let hold_ms = resolve_hold_ms(&args);
    let verso = resolve_verso_path();

    if report_mode {
        println!("自动化模式已启用：将采集兼容性矩阵并回传结果。");
    }

    if devtools_port > 0 {
        println!("Verso DevTools 已启用，端口 {devtools_port}（Firefox: about:debugging 连接 localhost:{devtools_port}）");
        // 必须在创建任何 webview 之前设置。
        tauri_runtime_verso::set_verso_devtools_port(devtools_port);
    }

    if let Some((path, needs_explicit_path)) = &verso {
        if *needs_explicit_path {
            println!("开发期：使用源码目录中的 versoview -> {}", path.display());
            tauri_runtime_verso::set_verso_path(path.clone());
        } else {
            println!("使用可执行文件旁边的 versoview -> {}", path.display());
        }
    } else {
        eprintln!(
            "警告：未找到 versoview 二进制，窗口将无法创建。\
             请先执行 `cargo build`，让构建脚本下载预编译的 versoview。"
        );
    }

    let state = HostState {
        report_mode,
        devtools_port,
        verso_path: verso.as_ref().map(|(path, _)| path.clone()),
        started_at,
        hold_ms,
    };

    tauri_runtime_verso::builder()
        .manage(state)
        .invoke_handler(tauri::generate_handler![get_app_info, submit_report])
        .run(tauri::generate_context!())
        .expect("运行 Tauri 应用失败");
}
