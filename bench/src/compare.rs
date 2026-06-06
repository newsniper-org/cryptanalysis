//! YSC3 vs YSC4 vs YSC5 비교 측정.
//!
//! - 사양상 FHE 비용 (AND 카운트, 깊이)
//! - 키스트림 생성 wall-clock (10만 블록)
//! - 1비트 차분 avalanche
//! - affinity 위반량

use cipher::{KeyIvInit, StreamCipher};
use std::time::Instant;

// ---- Avalanche ----

fn avalanche_ysc3() -> u32 {
    let mut a = [0u64; 16];
    let mut b = [0u64; 16];
    a[7] = 0xDEAD_BEEF_CAFE_BABE;
    b[7] = a[7] ^ 1;
    ysc3::permutation::permute(&mut a, 12);
    ysc3::permutation::permute(&mut b, 12);
    a.iter().zip(b.iter()).map(|(x, y)| (x ^ y).count_ones()).sum()
}

fn avalanche_ysc4() -> u32 {
    let mut a = [0u64; 16];
    let mut b = [0u64; 16];
    a[7] = 0xDEAD_BEEF_CAFE_BABE;
    b[7] = a[7] ^ 1;
    ysc4::permutation::permute(&mut a, 16);
    ysc4::permutation::permute(&mut b, 16);
    a.iter().zip(b.iter()).map(|(x, y)| (x ^ y).count_ones()).sum()
}

// ---- Affinity violation ----

fn affinity_helper(permute: impl Fn(&mut [u64; 16], usize), rounds: usize) -> u32 {
    let mut x = [0u64; 16];
    let mut y = [0u64; 16];
    for i in 0..16 {
        x[i] = 0x9E37_79B9_7F4A_7C15u64.wrapping_mul(i as u64 + 1);
        y[i] = 0xC6BC_2796_92B5_C323u64.wrapping_mul(i as u64 + 7);
    }
    let z: [u64; 16] = core::array::from_fn(|i| x[i] ^ y[i]);
    let mut px = x;
    let mut py = y;
    let mut pz = z;
    let mut p0 = [0u64; 16];
    permute(&mut px, rounds);
    permute(&mut py, rounds);
    permute(&mut pz, rounds);
    permute(&mut p0, rounds);
    (0..16).map(|i| (px[i] ^ py[i] ^ pz[i] ^ p0[i]).count_ones()).sum()
}

fn affinity_violation_ysc3() -> u32 {
    affinity_helper(|s, r| ysc3::permutation::permute(s, r), 12)
}

fn affinity_violation_ysc4() -> u32 {
    affinity_helper(|s, r| ysc4::permutation::permute(s, r), 16)
}

// ---- Throughput ----

fn bench_ysc3_keystream(blocks: u64) -> std::time::Duration {
    let cipher = ysc3::stream::Ysc3_128Stream::new(&[0x55; 32], &[0x66; 24]).unwrap();
    let mut buf = vec![0u8; 64];
    let t0 = Instant::now();
    for i in 0..blocks {
        cipher.keystream_block(i, &mut buf);
    }
    t0.elapsed()
}

fn bench_ysc4_keystream(blocks: u64) -> std::time::Duration {
    let cipher = ysc4::stream::Ysc4_128Stream::new(&[0x55; 32], &[0x66; 24]).unwrap();
    let mut buf = vec![0u8; 64];
    let t0 = Instant::now();
    for i in 0..blocks {
        cipher.keystream_block(i, &mut buf);
    }
    t0.elapsed()
}

fn bench_ysc5_keystream(blocks: u64) -> std::time::Duration {
    let mut cipher = ysc5::Ysc5_128StreamCipher::new(&[0x55; 32].into(), &[0x66; 24].into());
    let mut buf = vec![0u8; (blocks * 64) as usize];
    let t0 = Instant::now();
    cipher.apply_keystream(&mut buf);
    t0.elapsed()
}

fn main() {
    println!("=== YSC3 (GFN sponge) vs YSC4 (σ-GLM sponge) vs YSC5 (σ-GLM Farfalle) ===\n");

    println!("--- 사양상 FHE 비용 (블록당 AND 게이트) ---");
    println!("  YSC3 (R=12): 12,288 AND/block, 깊이 48");
    println!("  YSC4 (R=16): 2,048  AND/block, 깊이 16");
    println!("  YSC5 (R=12): 1,536  AND/block, 깊이 12  (Farfalle = 블록간 *병렬*)");

    println!("\n--- avalanche (1비트 → 출력 차분 비트 수, 이상치 ~512) ---");
    println!("  YSC3 (12라운드): {} / 1024", avalanche_ysc3());
    println!("  YSC4 (16라운드): {} / 1024", avalanche_ysc4());
    println!("  YSC5 (= YSC4 순열 재사용)");

    println!("\n--- affinity 위반량 (P가 affine이면 0) ---");
    println!("  YSC3 (12라운드): {} / 1024", affinity_violation_ysc3());
    println!("  YSC4 (16라운드): {} / 1024", affinity_violation_ysc4());

    println!("\n--- 소프트웨어 처리량 (10만 블록 keystream 생성) ---");
    let blocks = 100_000u64;
    let t3 = bench_ysc3_keystream(blocks);
    let t4 = bench_ysc4_keystream(blocks);
    let t5 = bench_ysc5_keystream(blocks);
    let bytes = blocks * 64;
    println!(
        "  YSC3: {:>8.2} ms ({:>7.2} MB/s)",
        t3.as_secs_f64() * 1000.0,
        bytes as f64 / t3.as_secs_f64() / 1e6
    );
    println!(
        "  YSC4: {:>8.2} ms ({:>7.2} MB/s)",
        t4.as_secs_f64() * 1000.0,
        bytes as f64 / t4.as_secs_f64() / 1e6
    );
    println!(
        "  YSC5: {:>8.2} ms ({:>7.2} MB/s)",
        t5.as_secs_f64() * 1000.0,
        bytes as f64 / t5.as_secs_f64() / 1e6
    );

    println!("\n--- 종합 ---");
    println!("  YSC3 (GFN sponge)         : 가장 빠른 소프트웨어 처리량 (SIMD 친화)");
    println!("  YSC4 (σ-GLM sponge)       : FHE 비용 1/6, 순차 처리");
    println!("  YSC5 (σ-GLM Farfalle)     : FHE 비용 동일, *blocks 간 병렬* + incremental");
}
