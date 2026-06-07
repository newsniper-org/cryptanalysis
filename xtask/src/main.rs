//! Project automation: preset application, workload suggestion.
//!
//! Usage:
//!   cargo run -p xtask -- preset <name>     # apply preset to .cargo/config.toml
//!   cargo run -p xtask -- list                # list available presets
//!   cargo run -p xtask -- suggest             # suggest preset for current host
//!   cargo run -p xtask -- help

use std::env;
use std::fs;
use std::path::PathBuf;
use std::process;

fn presets_dir() -> PathBuf {
    // 프로젝트 루트의 presets/.
    let manifest_dir = env::var("CARGO_MANIFEST_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|_| env::current_dir().unwrap());
    let workspace_root = manifest_dir.parent().unwrap_or(&manifest_dir).to_path_buf();
    workspace_root.join("presets")
}

fn list_presets() -> Vec<String> {
    let dir = presets_dir();
    let mut names = vec![];
    if let Ok(entries) = fs::read_dir(&dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().and_then(|s| s.to_str()) == Some("toml") {
                if let Some(stem) = path.file_stem().and_then(|s| s.to_str()) {
                    names.push(stem.to_string());
                }
            }
        }
    }
    names.sort();
    names
}

fn cmd_list() {
    let presets = list_presets();
    if presets.is_empty() {
        eprintln!("No presets found in {}/", presets_dir().display());
        process::exit(1);
    }
    println!("Available presets ({}):", presets.len());
    for p in &presets {
        // brief description from file header (first comment line)
        let path = presets_dir().join(format!("{}.toml", p));
        let desc = fs::read_to_string(&path)
            .ok()
            .and_then(|content| {
                content.lines()
                    .find(|l| l.starts_with("# "))
                    .map(|l| l.trim_start_matches("# ").to_string())
            })
            .unwrap_or_default();
        println!("  {:<24}  {}", p, desc);
    }
    println!();
    println!("Apply with: cargo run -p xtask -- preset <name>");
    println!("Get suggestion: cargo run -p xtask -- suggest");
}

fn cmd_preset(name: &str) {
    let src = presets_dir().join(format!("{}.toml", name));
    if !src.exists() {
        eprintln!("✗ Preset '{}' not found at {}", name, src.display());
        eprintln!();
        eprintln!("Available presets:");
        for p in list_presets() {
            eprintln!("  {}", p);
        }
        process::exit(1);
    }

    // 현재 작업 디렉토리의 .cargo/config.toml로 복사
    let cwd = env::current_dir().expect("current dir");
    let dst_dir = cwd.join(".cargo");
    fs::create_dir_all(&dst_dir).expect("create .cargo");
    let dst = dst_dir.join("config.toml");

    if dst.exists() {
        // 기존 파일 백업
        let backup = dst_dir.join("config.toml.bak");
        fs::copy(&dst, &backup).expect("backup");
        eprintln!("ℹ Existing config.toml backed up to .cargo/config.toml.bak");
    }

    fs::copy(&src, &dst).expect("copy preset");
    println!("✓ Applied preset '{}' to {}", name, dst.display());
    println!();
    println!("Next: cargo build --features stable-portable-simd,preset-{}", name);
    println!("  or: cargo build --features nightly-portable-simd,preset-{} (requires nightly)", name);
}

fn detect_host_arch() -> String {
    // env::consts::ARCH는 컴파일러 타깃을 반환 (xtask 실행 시 host arch).
    env::consts::ARCH.to_string()
}

fn detect_host_os() -> String {
    env::consts::OS.to_string()
}

fn cmd_suggest() {
    let arch = detect_host_arch();
    let os = detect_host_os();
    println!("Detected host: {}-{}", arch, os);
    println!();

    let suggestions: Vec<(&str, &str)> = match arch.as_str() {
        "x86_64" => vec![
            ("preset-x86-64-v3", "modern CPU (2013+, AVX2/FMA/BMI2)"),
            ("preset-x86-64-v4", "latest CPU (2017+, AVX-512). Verify with `cat /proc/cpuinfo | grep avx512`"),
            ("preset-x86-64-v2", "older CPU (2008+, SSE4.2). Conservative."),
            ("baseline", "no SIMD (scalar). Most conservative."),
        ],
        "aarch64" => vec![
            ("preset-aarch64-v8.2", "Apple Silicon, Graviton2+, modern smartphones"),
            ("preset-aarch64-baseline", "ARMv8.0 NEON (always available)"),
            ("preset-aarch64-sve", "Graviton3, A64FX (requires SVE-capable CPU)"),
        ],
        "wasm32" => vec![
            ("preset-wasm-simd", "modern browsers/WASI (simd128 stable since 2021)"),
            ("baseline", "older WASM runtimes (no SIMD)"),
        ],
        "riscv64" => vec![
            ("preset-rv64gcv", "RISC-V with V extension (RVV 1.0)"),
            ("baseline", "RV64GC without vector extension"),
        ],
        "powerpc64" => vec![
            ("preset-ppc64-power9", "POWER9+ (VSX-3)"),
            ("preset-ppc64-power8", "POWER8+ (VSX-2)"),
            ("baseline", "older PowerPC"),
        ],
        _ => vec![
            ("baseline", "no SIMD support; scalar fallback"),
        ],
    };

    println!("Suggested presets (most-likely first):");
    for (name, desc) in &suggestions {
        println!("  {:<28}  {}", name, desc);
    }
    println!();
    println!("Apply: cargo run -p xtask -- preset <name>");
    println!("Note: verify CPU features (e.g. /proc/cpuinfo on Linux) before choosing.");
}

fn print_help() {
    println!("xtask — project automation");
    println!();
    println!("USAGE:");
    println!("  cargo run -p xtask -- <COMMAND>");
    println!();
    println!("COMMANDS:");
    println!("  preset <name>    Apply preset to .cargo/config.toml");
    println!("  list             List available presets");
    println!("  suggest          Suggest preset for current host arch");
    println!("  help             Print this help");
    println!();
    println!("EXAMPLES:");
    println!("  cargo run -p xtask -- list");
    println!("  cargo run -p xtask -- suggest");
    println!("  cargo run -p xtask -- preset x86-64-v3");
    println!("  cd ypsilenti && cargo run -p xtask -- preset wasm-simd");
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let cmd = args.get(1).map(String::as_str).unwrap_or("help");
    match cmd {
        "preset" => {
            let name = args.get(2).cloned().unwrap_or_else(|| {
                eprintln!("Missing preset name. Try: cargo run -p xtask -- list");
                process::exit(1);
            });
            cmd_preset(&name);
        }
        "list" => cmd_list(),
        "suggest" => cmd_suggest(),
        "help" | "-h" | "--help" => print_help(),
        other => {
            eprintln!("Unknown command: {}", other);
            print_help();
            process::exit(1);
        }
    }
}
