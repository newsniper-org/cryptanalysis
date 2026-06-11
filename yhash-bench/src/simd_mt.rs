//! SIMD / 멀티쓰레딩 벤치 매트릭스.
//!
//! 측정 항목:
//!   1. 순열 micro-bench — scalar vs SIMD (한 바이너리에서 직접 비교)
//!   2. 전체 해시 throughput — streaming(직렬) baseline
//!   3. MT 스케일링 — hash_parallel × {Serial, StdThread, Rayon}
//!
//! 빌드 (전체 매트릭스):
//!   cargo +nightly run --release -p yhash_bench --bin simd_mt --features simd,mt
//! 일부만:
//!   cargo run --release -p yhash_bench --bin simd_mt --features mt      # MT만 (stable)
//!   cargo +nightly run --release -p yhash_bench --bin simd_mt --features simd  # SIMD perm만

use std::hint::black_box;
use std::time::Instant;

use yhash::YHashBuilder;
use ypsilenti::YpsiBuilder;

fn fmt_mbps(bytes: u64, secs: f64) -> f64 {
    (bytes as f64) / secs / 1e6
}

// ============ 1. leaf 압축 micro-bench (Level B: scalar 8-block vs batch) ============
//
// 단일 순열이 아니라 *leaf의 8-블록 mask-derive+compress* 단위를 비교한다.
// Level B SIMD는 8개 블록을 lane에 실어 한 번에 처리 → scalar 8회 루프와 대조.

fn bench_leaf_compress() {
    println!("\n===== 1. leaf 8-block 압축 micro-bench (scalar vs Level B SIMD) =====");
    let iters = 500_000usize;

    // ---- ysc4 / yhash: 8 × 128-byte 블록 ----
    {
        use yhash::consts::{rounds, LevelTag, STATE_WORDS};
        let iv: [u64; STATE_WORDS] = core::array::from_fn(|i| 0x9E37_79B9_7F4A_7C15u64 ^ i as u64);
        let blocks: [[u8; 128]; 8] = core::array::from_fn(|j| core::array::from_fn(|b| (j * 31 + b) as u8));
        let seeds: [[u8; 16]; 8] =
            core::array::from_fn(|j| yhash::encode::encode(LevelTag::Leaf, 0, j as u32));

        // scalar: 8× (derive_mask + compress_block)
        let scalar = || {
            let mut acc = [0u64; STATE_WORDS];
            for j in 0..8 {
                let mask = yhash::perm::derive_mask(&seeds[j], &iv);
                let y = yhash::perm::compress_block(&blocks[j], &mask, rounds::LEAF);
                for i in 0..STATE_WORDS {
                    acc[i] ^= y[i];
                }
            }
            acc
        };
        let scalar_ns = time_ns(iters, || black_box(scalar()));
        print!("  yhash leaf (8×128B): scalar {:>8.1} ns/leaf", scalar_ns);

        #[cfg(any(feature = "simd", feature = "simd-stable"))]
        {
            let batch = || {
                yhash::perm_simd::compute_leaf_acc(
                    &blocks, &seeds, 8, &iv, rounds::MASK_DERIVE, rounds::LEAF,
                )
            };
            assert_eq!(scalar(), batch(), "yhash Level B != scalar");
            let simd_ns = time_ns(iters, || black_box(batch()));
            print!("  |  SIMD {:>8.1} ns  ({:.2}× speedup)", simd_ns, scalar_ns / simd_ns);
        }
        #[cfg(not(any(feature = "simd", feature = "simd-stable")))]
        print!("  |  SIMD (--features simd, nightly)");
        println!();
    }

    // ---- ypsilenti: 8 × 32-byte 블록 ----
    {
        use ypsilenti::consts::{rounds, LevelTag, STATE_WORDS};
        let iv: [u32; STATE_WORDS] = core::array::from_fn(|i| 0x9E37_79B9u32 ^ i as u32);
        let blocks: [[u8; 32]; 8] = core::array::from_fn(|j| core::array::from_fn(|b| (j * 17 + b) as u8));
        let seeds: [[u8; 16]; 8] =
            core::array::from_fn(|j| ypsilenti::encode::encode(LevelTag::Leaf, 0, j as u32));

        let scalar = || {
            let mut acc = [0u32; STATE_WORDS];
            for j in 0..8 {
                let mask = ypsilenti::perm::derive_mask(&seeds[j], &iv);
                let y = ypsilenti::perm::compress_block(&blocks[j], &mask, rounds::LEAF);
                for i in 0..STATE_WORDS {
                    acc[i] ^= y[i];
                }
            }
            acc
        };
        let scalar_ns = time_ns(iters, || black_box(scalar()));
        print!("  ypsi  leaf (8× 32B): scalar {:>8.1} ns/leaf", scalar_ns);

        #[cfg(any(feature = "simd", feature = "simd-stable"))]
        {
            let batch = || {
                ypsilenti::perm_simd::compute_leaf_acc(
                    &blocks, &seeds, 8, &iv, rounds::MASK_DERIVE, rounds::LEAF,
                )
            };
            assert_eq!(scalar(), batch(), "ypsilenti Level B != scalar");
            let simd_ns = time_ns(iters, || black_box(batch()));
            print!("  |  SIMD {:>8.1} ns  ({:.2}× speedup)", simd_ns, scalar_ns / simd_ns);
        }
        #[cfg(not(any(feature = "simd", feature = "simd-stable")))]
        print!("  |  SIMD (--features simd, nightly)");
        println!();
    }
}

#[inline]
fn time_ns<F: FnMut() -> T, T>(iters: usize, mut f: F) -> f64 {
    for _ in 0..(iters / 20).max(1000) {
        black_box(f());
    }
    let t0 = Instant::now();
    for _ in 0..iters {
        black_box(f());
    }
    t0.elapsed().as_nanos() as f64 / iters as f64
}

// ============ 2. 전체 해시 throughput (streaming, 직렬) ============

fn bench_throughput() {
    use std::hash::Hasher;
    println!("\n===== 2. 전체 해시 throughput (streaming 직렬) =====");
    #[cfg(any(feature = "simd", feature = "simd-stable"))]
    println!("  [SIMD build]");
    #[cfg(not(any(feature = "simd", feature = "simd-stable")))]
    println!("  [scalar build]");

    let sizes: &[usize] = &[1024, 4096, 65_536, 1_048_576];
    let yb = YHashBuilder::unkeyed();
    let pb = YpsiBuilder::unkeyed();

    for &size in sizes {
        let data = vec![0xABu8; size];
        let iters = core::cmp::max(50, (64 * 1_048_576) / size);

        // yhash
        let t0 = Instant::now();
        for _ in 0..iters {
            let mut h = yb.build_hasher();
            h.write(black_box(&data));
            black_box(h.finish());
        }
        let yh_mbps = fmt_mbps((size as u64) * iters as u64, t0.elapsed().as_secs_f64());

        // ypsilenti
        let t0 = Instant::now();
        for _ in 0..iters {
            let mut h = pb.build_hasher();
            h.write(black_box(&data));
            black_box(h.finish());
        }
        let yp_mbps = fmt_mbps((size as u64) * iters as u64, t0.elapsed().as_secs_f64());

        println!(
            "  size={:>8}: yhash {:>9.1} MB/s  |  ypsilenti {:>9.1} MB/s",
            size, yh_mbps, yp_mbps
        );
    }
}

// ============ 3. MT 스케일링 ============

#[cfg(feature = "mt")]
fn bench_mt() {
    use yhash::parallel::hash_parallel as yhash_par;
    use yhash::spawner as ys;
    use ypsilenti::parallel::hash_parallel as ypsi_par;
    use ypsilenti::spawner as ps;

    println!("\n===== 3. MT 스케일링 (hash_parallel × spawner) =====");
    println!("  threads (rayon) = {}", rayon::current_num_threads());

    let sizes: &[usize] = &[256 * 1024, 1_048_576, 16 * 1_048_576, 64 * 1_048_576];
    let yb = YHashBuilder::unkeyed();
    let pb = YpsiBuilder::unkeyed();

    for &size in sizes {
        let data = vec![0xABu8; size];
        let iters = core::cmp::max(5, (256 * 1_048_576) / size);

        macro_rules! time {
            ($call:expr) => {{
                for _ in 0..2 {
                    black_box($call);
                }
                let t0 = Instant::now();
                for _ in 0..iters {
                    black_box($call);
                }
                fmt_mbps((size as u64) * iters as u64, t0.elapsed().as_secs_f64())
            }};
        }

        // yhash
        let s = time!(yhash_par(&yb, &data, &ys::SerialSpawner));
        let t = time!(yhash_par(&yb, &data, &ys::StdThreadSpawner::new()));
        let r = time!(yhash_par(&yb, &data, &ys::RayonSpawner));
        println!(
            "  yhash     size={:>9}: serial {:>8.1}  std-thread {:>8.1} ({:.2}×)  rayon {:>8.1} ({:.2}×)  MB/s",
            size, s, t, t / s, r, r / s
        );

        // ypsilenti
        let s = time!(ypsi_par(&pb, &data, &ps::SerialSpawner));
        let t = time!(ypsi_par(&pb, &data, &ps::StdThreadSpawner::new()));
        let r = time!(ypsi_par(&pb, &data, &ps::RayonSpawner));
        println!(
            "  ypsilenti size={:>9}: serial {:>8.1}  std-thread {:>8.1} ({:.2}×)  rayon {:>8.1} ({:.2}×)  MB/s",
            size, s, t, t / s, r, r / s
        );
    }
}

#[cfg(not(feature = "mt"))]
fn bench_mt() {
    println!("\n===== 3. MT 스케일링 =====");
    println!("  (build with --features mt 로 활성화)");
}

fn main() {
    println!("######## SIMD / MT 벤치 매트릭스 ########");
    #[cfg(any(feature = "simd", feature = "simd-stable"))]
    println!("# SIMD: ON");
    #[cfg(not(any(feature = "simd", feature = "simd-stable")))]
    println!("# SIMD: off (--features simd, nightly)");
    #[cfg(feature = "mt")]
    println!("# MT:   ON");
    #[cfg(not(feature = "mt"))]
    println!("# MT:   off (--features mt)");

    bench_leaf_compress();
    bench_throughput();
    bench_mt();
    println!();
}
