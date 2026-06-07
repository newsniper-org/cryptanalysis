//! build.rs — SIMD feature 검증 및 target_feature 기반 cfg 방출.
//!
//! 1) stable-portable-simd 와 nightly-portable-simd 동시 활성화 금지
//! 2) 활성화된 SIMD feature가 있을 때 target_arch 별 권장 target_feature 누락 경고
//! 3) 편의용 cfg 방출 (ypsi_simd_stable, ypsi_simd_nightly, ypsi_arch_*)

use std::env;

fn has(env_name: &str) -> bool {
    env::var(env_name).is_ok()
}

fn main() {
    println!("cargo:rerun-if-changed=build.rs");

    let stable = has("CARGO_FEATURE_STABLE_PORTABLE_SIMD");
    let nightly = has("CARGO_FEATURE_NIGHTLY_PORTABLE_SIMD");

    if stable && nightly {
        panic!(
            "ypsilenti: features `stable-portable-simd` and `nightly-portable-simd` are \
             mutually exclusive. Pick one."
        );
    }

    // cfg 방출 — 소스에서 #[cfg(ypsi_simd_any)] 등으로 사용
    println!("cargo:rustc-check-cfg=cfg(ypsi_simd_stable)");
    println!("cargo:rustc-check-cfg=cfg(ypsi_simd_nightly)");
    println!("cargo:rustc-check-cfg=cfg(ypsi_simd_any)");

    if stable {
        println!("cargo:rustc-cfg=ypsi_simd_stable");
        println!("cargo:rustc-cfg=ypsi_simd_any");
    }
    if nightly {
        println!("cargo:rustc-cfg=ypsi_simd_nightly");
        println!("cargo:rustc-cfg=ypsi_simd_any");
    }

    // arch 정보 — host가 아닌 target 기준
    let target_arch = env::var("CARGO_CFG_TARGET_ARCH").unwrap_or_default();
    let target_features: Vec<String> = env::var("CARGO_CFG_TARGET_FEATURE")
        .unwrap_or_default()
        .split(',')
        .map(|s| s.to_string())
        .filter(|s| !s.is_empty())
        .collect();

    // arch 별 cfg
    for arch in &["x86_64", "aarch64", "wasm32", "riscv64", "powerpc64", "sparc64"] {
        println!("cargo:rustc-check-cfg=cfg(ypsi_arch_{})", arch);
    }
    println!("cargo:rustc-cfg=ypsi_arch_{}", target_arch);

    // SIMD 활성화 시 target_feature 누락 경고
    if stable || nightly {
        let recommended: &[&str] = match target_arch.as_str() {
            "x86_64" => &["sse2", "sse4.2", "avx2"],
            "aarch64" => &["neon"],
            "wasm32" => &["simd128"],
            "riscv64" => &["v"],
            "powerpc64" => &["vsx"],
            _ => &[],
        };

        let has_any = recommended.iter().any(|f| target_features.iter().any(|tf| tf == f));
        if !recommended.is_empty() && !has_any {
            println!(
                "cargo:warning=ypsilenti SIMD feature enabled for target_arch={} but no \
                 SIMD target_feature detected (looked for: {}). Apply a preset: \
                 `cargo run -p xtask -- preset <name>`.",
                target_arch,
                recommended.join(", ")
            );
        }
    }
}
