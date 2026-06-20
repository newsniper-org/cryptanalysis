//! R3 — constant-time 통계 검정 (dudect 방식, valgrind 불필요).
//!
//! keyed 경로(key→IV→mask 유도)의 실행시간이 *비밀 키*에 의존하는지 측정한다.
//! 두 클래스를 교대 측정:
//!   class 0 = 고정 키 K0,  class 1 = 매번 다른(pseudo-random) 키.
//! 같은 공개 입력에 대해 keyed-builder 구성(= 키 흡수 + MASK_DERIVE 순열)을 rdtsc로
//! 계측 → 상위 백분위 crop(인터럽트 outlier 제거) → Welch t-검정.
//! |t| < 4.5 → 누설 미검출(시간이 키에 독립적이라는 경험적 증거).
//! |t| ≥ 4.5 → 잠재적 누설(추가 조사 필요).
//!
//! 주의: dudect는 *통계적 미검출*이지 형식적 CT 증명이 아니다. 정적 감사(§audit)와
//! 함께 본다. target-cpu/opt-level별 재실행 권장.
//!
//! 실행: `cargo run --release --bin ct_dudect`

use std::hint::black_box;
use yhash::YHashBuilder;
use ypsilenti::YpsiBuilder;

#[cfg(target_arch = "x86_64")]
#[inline]
fn cycles<F: FnOnce()>(f: F) -> u64 {
    use core::arch::x86_64::{__rdtscp, _mm_lfence};
    let mut aux = 0u32;
    unsafe {
        _mm_lfence();
        let a = core::arch::x86_64::_rdtsc();
        _mm_lfence();
        f();
        let b = __rdtscp(&mut aux);
        _mm_lfence();
        b - a
    }
}

#[cfg(not(target_arch = "x86_64"))]
#[inline]
fn cycles<F: FnOnce()>(f: F) -> u64 {
    let t0 = std::time::Instant::now();
    f();
    t0.elapsed().as_nanos() as u64
}

/// splitmix64 — 결정적 pseudo-random (random 클래스 키 생성용; 시드 고정).
struct Sm(u64);
impl Sm {
    fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9E3779B97F4A7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58476D1CE4E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D049BB133111EB);
        z ^ (z >> 31)
    }
    fn fill(&mut self, b: &mut [u8]) {
        for c in b.chunks_mut(8) {
            let v = self.next().to_le_bytes();
            c.copy_from_slice(&v[..c.len()]);
        }
    }
}

fn welch_t(a: &[u64], b: &[u64]) -> f64 {
    let m = |x: &[u64]| x.iter().map(|&v| v as f64).sum::<f64>() / x.len() as f64;
    let (ma, mb) = (m(a), m(b));
    let var = |x: &[u64], mu: f64| {
        x.iter().map(|&v| (v as f64 - mu).powi(2)).sum::<f64>() / (x.len() as f64 - 1.0)
    };
    let (va, vb) = (var(a, ma), var(b, mb));
    (ma - mb) / (va / a.len() as f64 + vb / b.len() as f64).sqrt()
}

/// 상위 백분위 crop (interrupt outlier 제거).
fn crop(mut v: Vec<u64>, keep_frac: f64) -> Vec<u64> {
    v.sort_unstable();
    let keep = (v.len() as f64 * keep_frac) as usize;
    v.truncate(keep.max(2));
    v
}

/// `k1_fixed = None`  → class1 = 랜덤 키 (표준 dudect).
/// `k1_fixed = Some` → class1 = 다른 고정 키 (fixed-vs-fixed 대조군: 측정 편향 판별).
fn run_test(
    name: &str,
    k0: &[u8],
    k1_fixed: Option<&[u8]>,
    mut measure: impl FnMut(&[u8]) -> u64,
    rng: &mut Sm,
) {
    const N: usize = 300_000;
    let mut warm = vec![0u8; k0.len()];
    for _ in 0..2000 {
        rng.fill(&mut warm);
        black_box(measure(&warm));
    }
    let (mut c0, mut c1) = (Vec::with_capacity(N / 2), Vec::with_capacity(N / 2));
    let mut rk = vec![0u8; k0.len()];
    for i in 0..N {
        if i & 1 == 0 {
            c0.push(measure(k0)); // 고정 키 K0
        } else {
            match k1_fixed {
                Some(k1) => c1.push(measure(k1)),    // 고정 키 K1 (대조군)
                None => {
                    rng.fill(&mut rk);
                    c1.push(measure(&rk)); // 랜덤 키
                }
            }
        }
    }
    // 여러 crop 비율에서 최대 |t| (dudect 식)
    let mut max_t = 0.0f64;
    for &kf in &[1.0, 0.95, 0.9, 0.8, 0.6] {
        let a = crop(c0.clone(), kf);
        let b = crop(c1.clone(), kf);
        let t = welch_t(&a, &b).abs();
        if t > max_t {
            max_t = t;
        }
    }
    let verdict = if max_t < 4.5 {
        "PASS (누설 미검출)"
    } else {
        "FAIL (잠재 누설)"
    };
    println!("  {name:<34} max|t| = {max_t:8.2}   {verdict}");
}

fn main() {
    println!("===== R3 constant-time dudect (keyed 경로) =====");
    #[cfg(target_arch = "x86_64")]
    println!("(rdtsc 계측, N=300k, 고정키 vs 랜덤키, Welch t, multi-crop max|t|; 임계 4.5)");
    let mut rng = Sm(0x0DDC0FFEEBADF00D);
    let k0 = [0u8; 16];                 // 고정 키 K0 (all-zero)
    let k1 = [0xA5u8; 16];              // 고정 키 K1 (대조군용, 비-제로)

    println!("\n[표준 dudect] class0 = 고정키 K0, class1 = 랜덤키:");
    run_test("yhash keyed-builder", &k0, None,
        |k| cycles(|| { black_box(YHashBuilder::keyed(black_box(k))); }), &mut rng);
    run_test("ypsilenti keyed-builder", &k0, None,
        |k| cycles(|| { black_box(YpsiBuilder::keyed(black_box(k))); }), &mut rng);
    let msg = [0x42u8; 64];
    run_test("yhash keyed-hash (fixed msg)", &k0, None,
        |k| cycles(|| { use std::hash::Hasher;
            let mut h = YHashBuilder::keyed(black_box(k)).build_hasher();
            h.write(black_box(&msg)); black_box(h.finish()); }), &mut rng);
    run_test("ypsilenti keyed-hash (fixed msg)", &k0, None,
        |k| cycles(|| { use std::hash::Hasher;
            let mut h = YpsiBuilder::keyed(black_box(k)).build_hasher();
            h.write(black_box(&msg)); black_box(h.finish()); }), &mut rng);

    println!("\n[대조군 fixed-vs-fixed] class0 = K0, class1 = K1 (둘 다 고정):");
    println!("(코드가 data-oblivious면 두 *고정* 키 간 t도 낮아야 함. 표준 dudect의");
    println!(" 높은 t가 '랜덤=가변입력' 측정편향 때문인지, 실제 키-의존인지 판별.)");
    run_test("yhash keyed-builder  K0|K1", &k0, Some(&k1),
        |k| cycles(|| { black_box(YHashBuilder::keyed(black_box(k))); }), &mut rng);
    run_test("ypsilenti keyed-builder K0|K1", &k0, Some(&k1),
        |k| cycles(|| { black_box(YpsiBuilder::keyed(black_box(k))); }), &mut rng);

    println!("\n참고: dudect는 통계적 미검출(부재 증명 아님). 정적 CT 감사는 CT-AUDIT.md.");
}
