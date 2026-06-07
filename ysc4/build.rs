//! build.rs — SIMD feature 검증 및 cfg 방출.
//!
//! 패턴은 ypsilenti의 build.rs와 동일.

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
            "ysc4: features `stable-portable-simd` and `nightly-portable-simd` are \
             mutually exclusive. Pick one."
        );
    }

    println!("cargo:rustc-check-cfg=cfg(ysc4_simd_stable)");
    println!("cargo:rustc-check-cfg=cfg(ysc4_simd_nightly)");
    println!("cargo:rustc-check-cfg=cfg(ysc4_simd_any)");

    if stable {
        println!("cargo:rustc-cfg=ysc4_simd_stable");
        println!("cargo:rustc-cfg=ysc4_simd_any");
    }
    if nightly {
        println!("cargo:rustc-cfg=ysc4_simd_nightly");
        println!("cargo:rustc-cfg=ysc4_simd_any");
    }

    let target_arch = env::var("CARGO_CFG_TARGET_ARCH").unwrap_or_default();
    let target_features: Vec<String> = env::var("CARGO_CFG_TARGET_FEATURE")
        .unwrap_or_default()
        .split(',')
        .map(|s| s.to_string())
        .filter(|s| !s.is_empty())
        .collect();

    for arch in &["x86_64", "aarch64", "wasm32", "riscv64", "powerpc64", "sparc64"] {
        println!("cargo:rustc-check-cfg=cfg(ysc4_arch_{})", arch);
    }
    println!("cargo:rustc-cfg=ysc4_arch_{}", target_arch);

    if stable || nightly {
        let recommended: &[&str] = match target_arch.as_str() {
            "x86_64" => &["sse2", "sse4.2", "avx2", "avx512f"],
            "aarch64" => &["neon"],
            "wasm32" => &["simd128"],
            "riscv64" => &["v"],
            "powerpc64" => &["vsx"],
            _ => &[],
        };
        let has_any = recommended.iter().any(|f| target_features.iter().any(|tf| tf == f));
        if !recommended.is_empty() && !has_any {
            println!(
                "cargo:warning=ysc4 SIMD feature enabled for target_arch={} but no \
                 SIMD target_feature detected (looked for: {}). Apply a preset.",
                target_arch,
                recommended.join(", ")
            );
        }
    }
}
