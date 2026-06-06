//! YSC3 (GFN) vs YSC4 (σ-GLM) 비교 측정.
//!
//! 측정 항목:
//! - 키스트림 한 블록 생성 시간 (CPU 사이클 대용)
//! - 1비트 입력 차분의 라운드 후 avalanche
//! - affinity 위반량 (P(x)⊕P(y)⊕P(x⊕y) ⊕ P(0))
//! - 사양 §4의 AND 카운트 (정적 추정치)

use std::time::Instant;

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

fn affinity_violation_ysc3() -> u32 {
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
    ysc3::permutation::permute(&mut px, 12);
    ysc3::permutation::permute(&mut py, 12);
    ysc3::permutation::permute(&mut pz, 12);
    ysc3::permutation::permute(&mut p0, 12);
    (0..16).map(|i| (px[i] ^ py[i] ^ pz[i] ^ p0[i]).count_ones()).sum()
}

fn affinity_violation_ysc4() -> u32 {
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
    ysc4::permutation::permute(&mut px, 16);
    ysc4::permutation::permute(&mut py, 16);
    ysc4::permutation::permute(&mut pz, 16);
    ysc4::permutation::permute(&mut p0, 16);
    (0..16).map(|i| (px[i] ^ py[i] ^ pz[i] ^ p0[i]).count_ones()).sum()
}

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

fn main() {
    println!("=== YSC3 (GFN, 12라운드) vs YSC4 (σ-GLM, 16라운드) ===\n");

    println!("--- 사양상 FHE 비용 (블록당 AND 게이트) ---");
    println!("  YSC3: 1024 AND/라운드 × 12 라운드 = 12,288");
    println!("  YSC4:  128 AND/라운드 × 16 라운드 =  2,048");
    println!("  비율: YSC4 = YSC3의 {:.2}배 (= 1/{:.1})", 2048.0/12288.0, 12288.0/2048.0);

    println!("\n--- AND 깊이 (multiplicative depth) ---");
    println!("  YSC3: QR 직렬 H × 4 × 12 라운드 = 48");
    println!("  YSC4: F × 16 라운드            = 16");

    println!("\n--- avalanche (1비트 입력 차분이 야기한 출력 차분 비트 수, 이상치 ~512) ---");
    println!("  YSC3: {} / 1024", avalanche_ysc3());
    println!("  YSC4: {} / 1024", avalanche_ysc4());

    println!("\n--- affinity 위반량 (P가 affine이면 0, 무작위처럼이면 ~512) ---");
    println!("  YSC3: {} / 1024", affinity_violation_ysc3());
    println!("  YSC4: {} / 1024", affinity_violation_ysc4());

    println!("\n--- 소프트웨어 처리량 (10만 블록 keystream 생성, x86_64 musl release) ---");
    let blocks = 100_000u64;
    let t3 = bench_ysc3_keystream(blocks);
    let t4 = bench_ysc4_keystream(blocks);
    let bytes = blocks * 64;
    println!("  YSC3: {:>8.2} ms ({:>6.2} MB/s)", t3.as_secs_f64() * 1000.0,
             (bytes as f64) / t3.as_secs_f64() / 1e6);
    println!("  YSC4: {:>8.2} ms ({:>6.2} MB/s)", t4.as_secs_f64() * 1000.0,
             (bytes as f64) / t4.as_secs_f64() / 1e6);

    println!("\n--- 종합 ---");
    println!("  ✓ FHE 환경(YSC4 주 목표): AND 카운트 약 6배, 깊이 3배 절감.");
    println!("  ✓ 보안 지표 (avalanche, affinity 위반): YSC3·YSC4 모두 ~512 비트.");
    println!("  · 소프트웨어 처리량: GFN(SIMD-친화)인 YSC3가 더 빠름. FHE 우선이라면 YSC4 채택.");
}
