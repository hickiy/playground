//! 构建脚本：准备 Verso 二进制，然后生成 Tauri 上下文。

use std::path::PathBuf;

fn main() {
    // 让 TARGET 在应用内可见，便于把构建目标写进运行时信息。
    println!(
        "cargo:rustc-env=BUILD_TARGET={}",
        std::env::var("TARGET").unwrap_or_else(|_| "unknown".to_string())
    );

    // 准备 versoview（Servo webview 是独立进程，不是链接进本程序的库）。
    //
    // 优先使用仓库里预置好的二进制：既省掉每次构建的下载，也让离线构建可行。
    // 预置步骤见 README，只需手动做一次；没有预置时才回退到官方下载。
    let manifest_dir = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").expect("缺少 CARGO_MANIFEST_DIR"));
    let target = std::env::var("TARGET").unwrap_or_default();
    let extension = if target.contains("windows") { ".exe" } else { "" };
    let versoview = manifest_dir
        .join("versoview")
        .join(format!("versoview-{target}{extension}"));

    if versoview.is_file() {
        println!("cargo:warning=使用预置的 versoview：{}", versoview.display());
    } else {
        println!("cargo:warning=未发现预置的 versoview，尝试从 GitHub 下载（受限环境下可能失败）");
        tauri_runtime_verso_build::get_verso_as_external_bin().expect(
            "准备 versoview 失败。请手工预置一次预编译版本：\n\
             1) curl -L -o %TEMP%\\verso.tar.gz https://github.com/tauri-apps/verso/releases/download/versoview-v0.0.9/verso-x86_64-pc-windows-msvc.tar.gz\n\
             2) tar -xzf %TEMP%\\verso.tar.gz -C src-tauri\\versoview\n\
             3) 把解压出的 versoview.exe 重命名为 versoview-x86_64-pc-windows-msvc.exe",
        );
    }

    // 资源变化时需要重新运行本脚本，让 Tauri 重新生成上下文（嵌入的前端资源随之更新）。
    println!("cargo:rerun-if-changed=../web");
    println!("cargo:rerun-if-changed=tauri.conf.json");
    println!("cargo:rerun-if-changed=capabilities");
    println!("cargo:rerun-if-changed=icons");

    tauri_build::build();
}
