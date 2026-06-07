//! YHash vs BLAKE3 vs KangarooTwelve — 종합 벤치마크.
//!
//! 동일 조건:
//! - 동일 입력 사이즈 (16 B ~ 1 MB)
//! - 동일 iteration 횟수
//! - 동일 측정 방식 (warmup + Instant)
//! - 256-bit (32-byte) digest 출력
//!
//! 비교 대상:
//! - yhash (256-bit, Farfalle-tree on YSC4-p)
//! - ypsilenti (128-bit, 8×u32 σ-GLM)
//! - BLAKE3 (256-bit, ARX Merkle tree)
//! - KangarooTwelve (256-bit, sponge-tree on Keccak-p[1600])

use std::mem::size_of;
use std::time::Instant;

use yhash::YHashBuilder;
use ypsilenti::YpsiBuilder;

use blake3::Hasher as Blake3Hasher;
use k12::Kt128;
use k12::digest::{Update, ExtendableOutput, XofReader};

// ---- per-hash 함수들 (one-shot 패턴) ----

fn hash_yhash(data: &[u8], iv_builder: &YHashBuilder) -> [u8; 32] {
    let mut h = iv_builder.build_hasher();
    h.update(data);
    h.finalize()
}

fn hash_ypsi(data: &[u8], iv_builder: &YpsiBuilder) -> [u8; 16] {
    let mut h = iv_builder.build_hasher();
    h.update(data);
    h.finalize()
}

fn hash_blake3(data: &[u8]) -> [u8; 32] {
    let mut h = Blake3Hasher::new();
    h.update(data);
    *h.finalize().as_bytes()
}

fn hash_k12(data: &[u8]) -> [u8; 32] {
    let mut h = Kt128::default();
    Update::update(&mut h, data);
    let mut out = [0u8; 32];
    let mut reader = h.finalize_xof();
    reader.read(&mut out);
    out
}

// ---- 측정 헬퍼 ----

fn bench_throughput<R>(name: &str, sizes: &[usize], iters: usize, mut hash_fn: impl FnMut(&[u8]) -> R) {
    println!("\n--- Throughput ({}): ---", name);
    for &size in sizes {
        let data = vec![0xABu8; size];
        for _ in 0..100 {
            std::hint::black_box(hash_fn(&data));
        }
        let t0 = Instant::now();
        for _ in 0..iters {
            std::hint::black_box(hash_fn(&data));
        }
        let elapsed = t0.elapsed();
        let total_bytes = (size as u64) * (iters as u64);
        let mb_per_sec = (total_bytes as f64) / elapsed.as_secs_f64() / 1e6;
        let ns_per_hash = elapsed.as_nanos() as f64 / iters as f64;
        println!(
            "  size={:>7} bytes: {:>9.2} MB/s  ({:>11.2} ns/hash)",
            size, mb_per_sec, ns_per_hash
        );
    }
}

fn report_state_sizes() {
    println!("\n--- State size (Hasher instance) ---");
    println!("  YHasher (yhash)    : {:>5} bytes", size_of::<yhash::YHasher>());
    println!("  YpsiHasher (ypsi)  : {:>5} bytes", size_of::<ypsilenti::YpsiHasher>());
    println!("  Blake3 Hasher      : {:>5} bytes", size_of::<Blake3Hasher>());
    println!("  KangarooTwelve(Kt128): {:>5} bytes", size_of::<Kt128>());
}

fn main() {
    println!("===== Secure hash 비교: YHash vs ypsilenti vs BLAKE3 vs KangarooTwelve =====");
    println!("(builder 공유, hasher per call. 모두 256-bit digest 출력 — ypsilenti는 128-bit)");

    report_state_sizes();

    // 작은 / 중간 / 큰 입력
    let sizes: &[usize] = &[16, 64, 256, 1024, 4_096, 65_536, 1_048_576];
    let iters_small = 50_000;
    let iters_large = 1_000;

    // Small (16 ~ 4096)
    let small_sizes = &sizes[..5];
    {
        let builder = YHashBuilder::unkeyed();
        bench_throughput("yhash (unkeyed, 256-bit)", small_sizes, iters_small,
                         |d| hash_yhash(d, &builder));
    }
    {
        let builder = YpsiBuilder::unkeyed();
        bench_throughput("ypsilenti (unkeyed, 128-bit)", small_sizes, iters_small,
                         |d| hash_ypsi(d, &builder));
    }
    bench_throughput("BLAKE3 (256-bit)", small_sizes, iters_small, hash_blake3);
    bench_throughput("KangarooTwelve (256-bit)", small_sizes, iters_small, hash_k12);

    // Large (64 KB, 1 MB)
    let large_sizes = &sizes[5..];
    {
        let builder = YHashBuilder::unkeyed();
        bench_throughput("yhash large", large_sizes, iters_large,
                         |d| hash_yhash(d, &builder));
    }
    {
        let builder = YpsiBuilder::unkeyed();
        bench_throughput("ypsilenti large", large_sizes, iters_large,
                         |d| hash_ypsi(d, &builder));
    }
    bench_throughput("BLAKE3 large", large_sizes, iters_large, hash_blake3);
    bench_throughput("KangarooTwelve large", large_sizes, iters_large, hash_k12);

    println!("\n===== 정리 =====");
    println!("- yhash      : Farfalle-tree on YSC4-p (1024-bit state, 256-bit digest)");
    println!("- ypsilenti  : Farfalle-tree on 8×u32 σ-GLM (256-bit state, 128-bit digest)");
    println!("- BLAKE3     : ARX Merkle tree (state per node, well-optimized SIMD)");
    println!("- K12        : sponge-tree on Keccak-p[1600] (12 rounds)");
}
