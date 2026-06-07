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

// ============ 1. 순열 micro-bench ============

fn bench_permutation() {
    println!("\n===== 1. 순열 micro-bench (scalar vs SIMD) =====");
    let iters = 5_000_000usize;
    let rounds = 12usize;

    // ---- ysc4 (yhash core): 16×u64 = 1024-bit ----
    {
        let mut st = [0u64; ysc4::consts::STATE_WORDS];
        st[0] = 0x0123_4567_89AB_CDEF;
        st[7] = 0xDEAD_BEEF_CAFE_BABE;

        // scalar
        let mut s = st;
        for _ in 0..10_000 {
            ysc4::permutation::permute_scalar(&mut s, rounds);
        }
        let t0 = Instant::now();
        for _ in 0..iters {
            ysc4::permutation::permute_scalar(black_box(&mut s), rounds);
        }
        let scalar_ns = t0.elapsed().as_nanos() as f64 / iters as f64;
        black_box(s);
        print!("  ysc4 perm (1024-bit, R={}): scalar {:>7.1} ns", rounds, scalar_ns);

        #[cfg(feature = "simd")]
        {
            let mut s = st;
            for _ in 0..10_000 {
                ysc4::permutation_simd::permute_simd(&mut s, rounds);
            }
            let t0 = Instant::now();
            for _ in 0..iters {
                ysc4::permutation_simd::permute_simd(black_box(&mut s), rounds);
            }
            let simd_ns = t0.elapsed().as_nanos() as f64 / iters as f64;
            black_box(s);
            print!("  |  SIMD {:>7.1} ns  ({:.2}× speedup)", simd_ns, scalar_ns / simd_ns);
        }
        #[cfg(not(feature = "simd"))]
        print!("  |  SIMD (build with --features simd on nightly)");
        println!();
    }

    // ---- ypsilenti: 8×u32 = 256-bit ----
    {
        let mut st = [0u32; ypsilenti::consts::STATE_WORDS];
        st[0] = 0xDEAD_BEEF;
        st[3] = 0xCAFE_BABE;

        let mut s = st;
        for _ in 0..10_000 {
            ypsilenti::perm::permute_scalar(&mut s, rounds);
        }
        let t0 = Instant::now();
        for _ in 0..iters {
            ypsilenti::perm::permute_scalar(black_box(&mut s), rounds);
        }
        let scalar_ns = t0.elapsed().as_nanos() as f64 / iters as f64;
        black_box(s);
        print!("  ypsi perm ( 256-bit, R={}): scalar {:>7.1} ns", rounds, scalar_ns);

        #[cfg(feature = "simd")]
        {
            let mut s = st;
            for _ in 0..10_000 {
                ypsilenti::perm_simd::permute_simd(&mut s, rounds);
            }
            let t0 = Instant::now();
            for _ in 0..iters {
                ypsilenti::perm_simd::permute_simd(black_box(&mut s), rounds);
            }
            let simd_ns = t0.elapsed().as_nanos() as f64 / iters as f64;
            black_box(s);
            print!("  |  SIMD {:>7.1} ns  ({:.2}× speedup)", simd_ns, scalar_ns / simd_ns);
        }
        #[cfg(not(feature = "simd"))]
        print!("  |  SIMD (build with --features simd on nightly)");
        println!();
    }

    #[cfg(feature = "simd")]
    println!("  (이 빌드는 SIMD 경로 활성화 — 전체 해시 throughput도 SIMD 적용됨)");
}

// ============ 2. 전체 해시 throughput (streaming, 직렬) ============

fn bench_throughput() {
    use std::hash::Hasher;
    println!("\n===== 2. 전체 해시 throughput (streaming 직렬) =====");
    #[cfg(feature = "simd")]
    println!("  [SIMD build]");
    #[cfg(not(feature = "simd"))]
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
        let t = time!(yhash_par(&yb, &data, &ys::StdThreadSpawner));
        let r = time!(yhash_par(&yb, &data, &ys::RayonSpawner));
        println!(
            "  yhash     size={:>9}: serial {:>8.1}  std-thread {:>8.1} ({:.2}×)  rayon {:>8.1} ({:.2}×)  MB/s",
            size, s, t, t / s, r, r / s
        );

        // ypsilenti
        let s = time!(ypsi_par(&pb, &data, &ps::SerialSpawner));
        let t = time!(ypsi_par(&pb, &data, &ps::StdThreadSpawner));
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
    #[cfg(feature = "simd")]
    println!("# SIMD: ON");
    #[cfg(not(feature = "simd"))]
    println!("# SIMD: off (--features simd, nightly)");
    #[cfg(feature = "mt")]
    println!("# MT:   ON");
    #[cfg(not(feature = "mt"))]
    println!("# MT:   off (--features mt)");

    bench_permutation();
    bench_throughput();
    bench_mt();
    println!();
}
