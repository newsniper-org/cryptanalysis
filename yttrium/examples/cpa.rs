//! 전력 side-channel (CPA) — **Rust 레퍼런스 구현 직접 공격** (Python 재모델 X).
//!
//! `yttrium::sca`로 *실제* keyed 경로가 계산하는 비밀-의존 중간값을 받아 HW-leakage 모델로
//! CPA를 건다. (A) 첫 중간값 sᵢ=blockᵢ⊕mask 의 한 바이트 누출 → mask 바이트 복구.
//! (C) 대조군: 비선형 t=F(S) 바이트 per-byte CPA → 실패(yttrium은 per-byte 비선형 타깃 부재).
//!
//! ★ 귀속(feedback): 이건 HW-leakage **시뮬레이션**(실 CPU 측정 아님→하드웨어 버그 ④ 무관).
//! (A) 성공 = **미보호 구현**의 선형 XOR-with-secret 누출(unmasked AES와 동일, generic) — yttrium
//! **프리미티브 결함 아님.** 대응 = boolean masking(구현 의무).
//!
//! 실행: cargo run --release --example cpa -p yttrium

use yttrium::{sca, Rounds, YttriumBuilder, BLOCK_BYTES, STATE_WORDS};

fn hw(x: u8) -> f64 {
    x.count_ones() as f64
}

// splitmix64 (결정적, 외부 의존 X)
fn sm(s: &mut u64) -> u64 {
    *s = s.wrapping_add(0x9E3779B97F4A7C15);
    let mut z = *s;
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58476D1CE4E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D049BB133111EB);
    z ^ (z >> 31)
}

/// leak = +HW + noise 모델 → **부호 있는** Pearson corr 최대 = 복구(보수 모호성 해소).
fn cpa(known: &[u8], leak: &[f64], model: impl Fn(u8, u8) -> f64) -> (u8, f64, f64) {
    let n = leak.len() as f64;
    let lm = leak.iter().sum::<f64>() / n;
    let lc: Vec<f64> = leak.iter().map(|&x| x - lm).collect();
    let ld = lc.iter().map(|x| x * x).sum::<f64>().sqrt();
    let mut corrs = [0f64; 256];
    for cand in 0..256u16 {
        let pred: Vec<f64> = known.iter().map(|&b| model(b, cand as u8)).collect();
        let pm = pred.iter().sum::<f64>() / n;
        let pc: Vec<f64> = pred.iter().map(|x| x - pm).collect();
        let pd = pc.iter().map(|x| x * x).sum::<f64>().sqrt();
        let cov: f64 = pc.iter().zip(&lc).map(|(a, b)| a * b).sum();
        corrs[cand as usize] = if pd > 0.0 && ld > 0.0 { cov / (pd * ld) } else { 0.0 };
    }
    let best = (0..256).max_by(|&a, &b| corrs[a].partial_cmp(&corrs[b]).unwrap()).unwrap();
    let mut sorted = corrs;
    sorted.sort_by(|a, b| b.partial_cmp(a).unwrap());
    (best as u8, corrs[best], sorted[0] - sorted[1])
}

fn gauss(s: &mut u64, sigma: f64) -> f64 {
    // Box-Muller
    let u1 = ((sm(s) >> 11) as f64 / (1u64 << 53) as f64).max(1e-12);
    let u2 = (sm(s) >> 11) as f64 / (1u64 << 53) as f64;
    (-2.0 * u1.ln()).sqrt() * (2.0 * std::f64::consts::PI * u2).cos() * sigma
}

fn rand_block(s: &mut u64) -> [u8; BLOCK_BYTES] {
    let mut b = [0u8; BLOCK_BYTES];
    for c in b.iter_mut() {
        *c = sm(s) as u8;
    }
    b
}

fn main() {
    let kb = YttriumBuilder::keyed(b"yttrium-sca-secret-key", Rounds::V8_12_24);
    // 실제 비밀: leaf(pos0,idx0) mask. 공격 타깃 = mask 워드0의 바이트0.
    let real_mask = sca::leaf_mask(&kb, 0, 0);
    let secret_byte = (real_mask[0] & 0xFF) as u8;
    let mut rs = 0xC0FFEE_1234_5678u64;

    println!("== (A) CPA on sᵢ=blockᵢ⊕mask (Rust 실 구현 sca::leaf_intermediate) ==");
    println!("   타깃: mask[0] 바이트0 = {secret_byte:#04x} (공격자 미지)");
    for &sigma in &[0.5f64, 1.0, 2.0, 4.0] {
        let m = 6000usize;
        let mut known = Vec::with_capacity(m);
        let mut leak = Vec::with_capacity(m);
        for _ in 0..m {
            let blk = rand_block(&mut rs);
            let s = sca::leaf_intermediate(&kb, &blk, 0, 0); // 실 구현 중간값
            let sbyte = (s[0] & 0xFF) as u8; // 디바이스가 leak하는 바이트
            known.push(blk[0]); // 공격자 아는 값(block 워드0 바이트0)
            leak.push(hw(sbyte) + gauss(&mut rs, sigma));
        }
        let (rec, c, gap) = cpa(&known, &leak, |b, k| hw(b ^ k));
        let ok = if rec == secret_byte { "✓복구" } else { "✗" };
        println!("   σ={sigma:>3}: 복구={rec:#04x} {ok}  corr={c:.3} gap={gap:.3}");
    }

    println!("\n== (B) 트레이스 수 효과 (σ=2.0) ==");
    for &m in &[200usize, 800, 3000, 12000] {
        let mut known = Vec::with_capacity(m);
        let mut leak = Vec::with_capacity(m);
        for _ in 0..m {
            let blk = rand_block(&mut rs);
            let s = sca::leaf_intermediate(&kb, &blk, 0, 0);
            known.push(blk[0]);
            leak.push(hw((s[0] & 0xFF) as u8) + gauss(&mut rs, 2.0));
        }
        let (rec, c, _) = cpa(&known, &leak, |b, k| hw(b ^ k));
        println!("   M={m:>5}: 복구={rec:#04x} {}  corr={c:.3}", if rec == secret_byte { "✓" } else { "✗" });
    }

    println!("\n== (C) 대조군: 비선형 t=F(S) 바이트에 per-byte CPA (yttrium 추가 DPA 타깃 부재) ==");
    {
        let m = 12000usize;
        let mut known = Vec::with_capacity(m);
        let mut leak = Vec::with_capacity(m);
        for _ in 0..m {
            let blk = rand_block(&mut rs); // 전바이트 랜덤(다른 레인도 변화)
            let s = sca::leaf_intermediate(&kb, &blk, 0, 0);
            let t = sca::first_round_t(&s); // 실 구현 라운드0 t=F(S)
            known.push(blk[0]); // 공격자: block 바이트0만 가설
            leak.push(((t & 0xFF) as u8).count_ones() as f64 + gauss(&mut rs, 2.0));
        }
        let (rec, c, _) = cpa(&known, &leak, |b, k| hw(b ^ k));
        println!("   per-byte CPA on t=F(S): 복구={rec:#04x} corr={c:.3} → {} (전레인 비선형 혼합으로 분리 불가)",
                 if c.abs() < 0.05 { "실패(기대)" } else { "조사요" });
    }

    let _ = STATE_WORDS;
    println!("\n== 귀속(정직) ==");
    println!("  (A)(B) 성공 = 실 구현의 **미보호 선형 block⊕mask 누출**(generic, unmasked AES와 동일).");
    println!("  → 원인=구현(마스킹 미적용), NOT 프리미티브, NOT 하드웨어(HW-leakage 시뮬).");
    println!("  (C) 실패 = yttrium S-box 없음+영합 전레인혼합 → per-byte 비선형 DPA 타깃 부재.");
    println!("  복구 대상은 per-position mask이지 key 아님(mask→key=P_y 역상 256-bit preimage).");
}
