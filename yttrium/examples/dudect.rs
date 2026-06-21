//! dudect식 constant-time 실측 — **가혹 버전**.
//!
//! yttrium은 구성상 CT(데이터 의존 분기·테이블·인덱싱 없음; CT-AUDIT.md §yttrium). 본 하니스는
//! 그 경험적 확인을 *가혹 조건*으로 수행한다:
//!   - **rdtsc** 사이클 카운터(+lfence 직렬화) — Instant보다 정밀.
//!   - **N-sweep**: 누출 있으면 |t|∝√N 증가, 없으면 유계(dudect 핵심 진단).
//!   - **2 경로**: (M) 메시지 fix-vs-random, (K) **키 fix-vs-random**(R_mask 키흡수=진짜 비밀 경로).
//!   - **적대적 클래스**: all-zero vs random, low-HW vs high-HW.
//! |t| < ~4.5(또는 N 증가에도 유계) → 누출 미검출. 정적 감사가 1차 증거.
//!
//! 실행(코어 고정 권장): taskset -c 3 cargo run --release --example dudect -p yttrium

use yttrium::{Rounds, YttriumBuilder};

#[cfg(target_arch = "x86_64")]
#[inline]
fn cycles() -> u64 {
    // lfence로 앞뒤 직렬화 후 rdtsc.
    unsafe {
        core::arch::x86_64::_mm_lfence();
        let t = core::arch::x86_64::_rdtsc();
        core::arch::x86_64::_mm_lfence();
        t
    }
}
#[cfg(not(target_arch = "x86_64"))]
#[inline]
fn cycles() -> u64 {
    use std::time::Instant;
    Instant::now().elapsed().as_nanos() as u64 // fallback
}

fn splitmix(s: &mut u64) -> u64 {
    *s = s.wrapping_add(0x9E3779B97F4A7C15);
    let mut z = *s;
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58476D1CE4E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D049BB133111EB);
    z ^ (z >> 31)
}

/// 크롭(상위 p퍼센타일 스파이크 제거) 후 Welch t.
fn welch_t(a: &[u64], b: &[u64], p: f64) -> f64 {
    let crop = |v: &[u64]| -> Vec<f64> {
        let mut s: Vec<u64> = v.to_vec();
        s.sort_unstable();
        let hi = s[((s.len() as f64) * p) as usize];
        v.iter().filter(|&&x| x <= hi).map(|&x| x as f64).collect()
    };
    let ca = crop(a);
    let cb = crop(b);
    let mean = |v: &[f64]| v.iter().sum::<f64>() / v.len() as f64;
    let var = |v: &[f64], m: f64| v.iter().map(|x| (x - m).powi(2)).sum::<f64>() / (v.len() as f64 - 1.0);
    let (ma, mb) = (mean(&ca), mean(&cb));
    let (va, vb) = (var(&ca, ma), var(&cb, mb));
    (ma - mb) / (va / ca.len() as f64 + vb / cb.len() as f64).sqrt()
}

/// 두 클래스를 인터리브 측정 → 체크포인트별 |t| 보고. measure: 클래스(0/1) → 사이클.
fn run_experiment<F: FnMut(u8) -> u64>(name: &str, n: usize, mut measure: F) {
    // warmup
    for i in 0..20_000 {
        std::hint::black_box(measure((i & 1) as u8));
    }
    let (mut a, mut b) = (Vec::with_capacity(n / 2 + 1), Vec::with_capacity(n / 2 + 1));
    let checkpoints = [50_000usize, 200_000, 500_000, n];
    let mut ci = 0;
    print!("  [{name}] |t| @ N: ");
    for i in 0..n {
        let c = (i & 1) as u8;
        let t = measure(c);
        if c == 0 { a.push(t) } else { b.push(t) }
        if ci < checkpoints.len() && i + 1 == checkpoints[ci] {
            let t90 = welch_t(&a, &b, 0.90);
            print!("{}→{:.2}  ", checkpoints[ci], t90.abs());
            ci += 1;
        }
    }
    let t_strict = welch_t(&a, &b, 0.99); // 약한 크롭(스파이크 더 포함 = 더 가혹)
    println!(
        "\n     최종: |t|(crop90)={:.3}, |t|(crop99,가혹)={:.3} → {}",
        welch_t(&a, &b, 0.90).abs(),
        t_strict.abs(),
        if t_strict.abs() < 4.5 { "누출 미검출 ✓" } else { "유계성 N-sweep 확인 요" }
    );
}

fn main() {
    let n: usize = std::env::args().nth(1).and_then(|s| s.parse().ok()).unwrap_or(2_000_000);
    const LEN: usize = 1024;
    println!("dudect 가혹: rdtsc, N={n}, {LEN}B. |t|이 N 증가에도 유계면 CT 일관.");

    let mut rs = 0xDEADBEEF_12345678u64;
    let fixed = vec![0u8; LEN];
    let mut randbuf = vec![0u8; LEN];
    for c in randbuf.iter_mut() { *c = splitmix(&mut rs) as u8; }
    // 적대적: high-HW (all-ones) vs low-HW (all-zero)
    let ones = vec![0xFFu8; LEN];

    // (M) 메시지 fix(zero) vs random, 고정 키.
    let kb = YttriumBuilder::keyed(b"dudect-secret-key", Rounds::V8_12_24);
    run_experiment("M:zero-vs-rand", n, |c| {
        let msg = if c == 0 { &fixed } else { &randbuf };
        let t0 = cycles();
        let mut h = kb.build_hasher();
        h.update(msg);
        std::hint::black_box(h.finalize());
        cycles().wrapping_sub(t0)
    });

    // (M2) 적대적 Hamming-weight: zero vs ones.
    run_experiment("M:zero-vs-ones(HW)", n, |c| {
        let msg = if c == 0 { &fixed } else { &ones };
        let t0 = cycles();
        let mut h = kb.build_hasher();
        h.update(msg);
        std::hint::black_box(h.finalize());
        cycles().wrapping_sub(t0)
    });

    // (K) 키 fix(zero) vs random — R_mask 키흡수가 비밀 경로. 빌더 생성을 타이밍.
    let fixed_key = [0u8; 16];
    let mut rand_key = [0u8; 16];
    for c in rand_key.iter_mut() { *c = splitmix(&mut rs) as u8; }
    run_experiment("K:zero-vs-rand(키흡수)", n, |c| {
        let key: &[u8] = if c == 0 { &fixed_key } else { &rand_key };
        let t0 = cycles();
        let b = YttriumBuilder::keyed(key, Rounds::V8_12_24);
        std::hint::black_box(b.build_hasher());
        cycles().wrapping_sub(t0)
    });
}
