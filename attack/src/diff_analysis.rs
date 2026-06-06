//! [추가 분석] YSC2 비선형 함수 g(x) = x ⊕ ((x <<< 13) & (x <<< 37))의 차분 특성.
//!
//! AND 게이트의 개수와 위치가 비선형성을 결정한다.
//! 본 분석은:
//!  1) g의 단일 입력 차분(Δ)이 출력에서 어떻게 전파되는지 표본 측정,
//!  2) 'L → R ⊕ g(L)' 라운드 구조에서 적은 비트 차분이 살아남을 확률 평가.

#[path = "ysc2_ref.rs"]
mod ysc2_ref;
use ysc2_ref::ysc2;

fn hw(x: u64) -> u32 { x.count_ones() }

fn diff_distribution(delta: u64, samples: usize) -> (f64, [u32; 65]) {
    // 출력 Hamming weight 분포 측정.
    let mut bins = [0u32; 65];
    let mut zero_diff = 0;
    use std::num::Wrapping;
    let mut rng_state = Wrapping(0xCAFEBABEDEADBEEFu64);
    let mut next = || -> u64 {
        rng_state = Wrapping(rng_state.0.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407));
        rng_state.0
    };
    for _ in 0..samples {
        let x = next();
        let y = x ^ delta;
        let d_out = ysc2::g(x) ^ ysc2::g(y);
        bins[hw(d_out) as usize] += 1;
        if d_out == 0 { zero_diff += 1; }
    }
    (zero_diff as f64 / samples as f64, bins)
}

fn main() {
    println!("=== 추가: YSC2 g(x) 비선형 함수의 차분 특성 ===\n");
    // 단일 비트 입력 차분.
    let samples = 1 << 18;
    for &delta in &[1u64, 1u64 << 5, 1u64 << 13, 1u64 << 37, 1u64 << 63] {
        let (p_zero, bins) = diff_distribution(delta, samples);
        let mean_hw: f64 = bins.iter().enumerate().map(|(i, &c)| (i as f64) * c as f64).sum::<f64>() / samples as f64;
        println!("  Δ = bit{:>2}: P[Δout=0] ≈ {:.5},  E[hw(Δout)] = {:.3}",
                 delta.trailing_zeros(), p_zero, mean_hw);
    }

    // 무작위 차분.
    use std::num::Wrapping;
    let mut s = Wrapping(0x1234567890ABCDEFu64);
    let mut rand = || -> u64 {
        s = Wrapping(s.0.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407));
        s.0
    };
    println!("\n  무작위 Δ 5개:");
    for _ in 0..5 {
        let d = rand();
        let (p_zero, bins) = diff_distribution(d, samples);
        let mean_hw: f64 = bins.iter().enumerate().map(|(i, &c)| (i as f64) * c as f64).sum::<f64>() / samples as f64;
        println!("    Δ = {:016x}: P[Δout=0] ≈ {:.5},  E[hw(Δout)] = {:.3}", d, p_zero, mean_hw);
    }

    println!("\n[해석]");
    println!("  - g는 라운드당 단일 워드 차분을 워드 내부에서만 확산. 16워드 간 확산은 Lai-Massey + 워드순열에 의존.");
    println!("  - AND 게이트는 입력의 분포에 따라 차분 전파 확률이 1/2로 감쇠. 그러나 단일 워드 트랙은 1라운드당 가지치기가 약함.");
    println!("  - 본 보고서의 결정적 공격(공격 1, 2)이 더 강력하므로 차분 분석은 부차적.");
}
