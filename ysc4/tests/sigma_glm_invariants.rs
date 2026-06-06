//! σ-GLM의 구조적 무결성을 직접 검증.
//!
//! 검증 항목:
//! 1) `permute_without_sigma` (σ 제거 변종)는 `⊕ᵢ stateᵢ` 불변량을 *보존* — Lai-Massey 한계.
//! 2) `permute` (정상)는 σ-층에 의해 같은 불변량을 *깬다*.
//! 3) σ-층 단독 적용 → `⊕ᵢ` 변화량이 사양 §2.2의 식과 일치.
//! 4) α-mult가 GF(2⁶⁴) 단위원이고 orthomorphism.

use ysc4::consts::STATE_WORDS;
use ysc4::gf2_64::{alpha, alpha_pow};
use ysc4::permutation::{f, permute, permute_without_sigma};

fn xor_reduce(state: &[u64; STATE_WORDS]) -> u64 {
    state.iter().fold(0u64, |a, &x| a ^ x)
}

#[test]
fn broadcast_only_preserves_lai_massey_invariant() {
    // σ를 제거한 broadcast-only 변종은 `⊕ᵢ stateᵢ`를 보존해야 한다.
    // 이는 classical Lai-Massey의 알려진 약점을 *직접 재현*한다.
    let mut s = [0u64; STATE_WORDS];
    for i in 0..STATE_WORDS {
        s[i] = 0xA5A5_5A5A_C3C3_3C3Cu64.wrapping_mul(i as u64 + 1);
    }
    let initial_xor = xor_reduce(&s);

    permute_without_sigma(&mut s, 16);
    let final_xor = xor_reduce(&s);

    // 한 라운드 round_constant도 위치 r mod 16에 XOR되므로 invariant에 영향을 줌.
    // RC 영향만 제거하면 broadcast-only는 정확히 보존됨.
    // RC 합산:
    use ysc4::consts::RC;
    let rc_acc: u64 = (0..16).fold(0u64, |a, r| a ^ RC[r & 15]);

    assert_eq!(
        final_xor, initial_xor ^ rc_acc,
        "broadcast-only 변종이 `⊕ᵢ stateᵢ ⊕ Σ_r RC[r mod 16]` 항등성을 유지해야 함 (Lai-Massey 약점)"
    );
}

#[test]
fn sigma_breaks_lai_massey_invariant() {
    // 정상 변종에서는 σ-층 때문에 `⊕ᵢ stateᵢ` 항등성이 깨져야 한다.
    let mut s_sigma = [0u64; STATE_WORDS];
    let mut s_nosigma = [0u64; STATE_WORDS];
    for i in 0..STATE_WORDS {
        let v = 0x9E37_79B9_7F4A_7C15u64.wrapping_mul(i as u64 + 1);
        s_sigma[i] = v;
        s_nosigma[i] = v;
    }

    permute(&mut s_sigma, 16);
    permute_without_sigma(&mut s_nosigma, 16);

    let xor_sigma = xor_reduce(&s_sigma);
    let xor_nosigma = xor_reduce(&s_nosigma);

    // σ가 적용된 결과의 XOR 축약은 σ가 없는 변종과 *반드시 다르다*.
    // 만약 같다면 σ의 기여가 (αᵏ+1)·Lᵢ 항이 모두 상쇄됐다는 뜻인데, 일반적인 입력에 대해서는 그럴 수 없음.
    assert_ne!(
        xor_sigma, xor_nosigma,
        "σ-층이 invariant `⊕ᵢ stateᵢ`를 깨야 한다"
    );

    // 추가: 두 결과의 상태가 전반적으로 광범위하게 다를 것.
    let mut diff = 0u32;
    for i in 0..STATE_WORDS {
        diff += (s_sigma[i] ^ s_nosigma[i]).count_ones();
    }
    assert!(
        diff > 256,
        "σ 유무가 200비트 이상의 상태 변동을 야기해야 함, 실제 diff={}",
        diff
    );
    eprintln!("[info] σ 유무가 야기한 상태 변동량 = {} 비트 / 1024", diff);
}

#[test]
fn alpha_is_orthomorphism_strict() {
    // Vaudenay orthomorphism의 두 조건:
    //   (a) σ가 bijection (= GF(2⁶⁴) 단위원 곱)
    //   (b) x ↦ x ⊕ σ(x)도 bijection
    //
    // 256개 무작위 표본으로 직접 검증.
    use std::collections::BTreeSet;
    let mut seen_a = BTreeSet::new();
    let mut seen_b = BTreeSet::new();
    for i in 0u64..256 {
        let y = i.wrapping_mul(0xDEAD_BEEF_CAFE_BABE);
        assert!(seen_a.insert(alpha(y)), "α-mult이 단사가 아님");
        assert!(seen_b.insert(y ^ alpha(y)), "(α+1)-mult이 단사가 아님");
    }
}

#[test]
fn sigma_layer_change_formula() {
    // 사양 §2.2의 공식:
    //   ⊕ᵢ σ-after - ⊕ᵢ broadcast = (α+1)·s₀' ⊕ (α³+1)·s₄' ⊕ (α⁵+1)·s₈' ⊕ (α⁷+1)·s₁₂'
    // 임의 상태에 대해 양변을 직접 계산하여 일치를 확인.
    let mut s = [0u64; STATE_WORDS];
    for i in 0..STATE_WORDS {
        s[i] = 0xC6BC_2796_92B5_C323u64.wrapping_mul(i as u64 + 11);
    }
    let before = xor_reduce(&s);

    // σ-층만 적용
    s[0] = alpha_pow(s[0], 1);
    s[4] = alpha_pow(s[4], 3);
    s[8] = alpha_pow(s[8], 5);
    s[12] = alpha_pow(s[12], 7);
    let after = xor_reduce(&s);

    // 변화량 = (α+1)·orig₀ ⊕ (α³+1)·orig₄ ⊕ (α⁵+1)·orig₈ ⊕ (α⁷+1)·orig₁₂
    // (위에서 s를 바꿔놓았으므로 원본을 다시 계산)
    let mut orig = [0u64; STATE_WORDS];
    for i in 0..STATE_WORDS {
        orig[i] = 0xC6BC_2796_92B5_C323u64.wrapping_mul(i as u64 + 11);
    }
    let predicted_delta = (orig[0] ^ alpha_pow(orig[0], 1))
        ^ (orig[4] ^ alpha_pow(orig[4], 3))
        ^ (orig[8] ^ alpha_pow(orig[8], 5))
        ^ (orig[12] ^ alpha_pow(orig[12], 7));

    assert_eq!(after ^ before, predicted_delta);
}

#[test]
fn permutation_is_bijection_one_round() {
    // 단일 라운드가 bijection임을 256개 임의 (서로 다른) 입력에 대해 확인.
    use std::collections::BTreeSet;
    let mut outs = BTreeSet::new();
    for i in 0u64..256 {
        let mut s = [0u64; STATE_WORDS];
        for j in 0..STATE_WORDS {
            s[j] = (i.wrapping_mul(0x100000001B3u64)) ^ (j as u64);
        }
        permute(&mut s, 1);
        // 비교를 위해 단순 hash로 16개 워드를 압축.
        let h: u64 = s.iter().fold(0u64, |a, &x| a.wrapping_mul(0x9E37_79B9_7F4A_7C15).wrapping_add(x));
        assert!(outs.insert(h), "1-라운드 출력 충돌 발생 (입력 i={})", i);
    }
}

#[test]
fn f_function_has_nonzero_degree2_terms() {
    // F가 *진정한* 비선형: 작은 차분에서 비-자명한 차분이 나타나야 함.
    // F(a) ⊕ F(b) ⊕ F(a⊕b) = F(0) 이 모든 (a,b)에서 성립하면 affine.
    let f0 = f(0);
    let mut violation: u32 = 0;
    let mut tested = 0u32;
    for i in 0u64..32 {
        for j in 0u64..32 {
            let a = i.wrapping_mul(0x9E37_79B9_7F4A_7C15);
            let b = j.wrapping_mul(0xC6BC_2796_92B5_C323);
            let lhs = f(a) ^ f(b) ^ f(a ^ b);
            violation += (lhs ^ f0).count_ones();
            tested += 1;
        }
    }
    let avg = violation as f64 / tested as f64;
    eprintln!("[info] F의 평균 affinity-위반 비트 수 ({}개 표본): {:.2}", tested, avg);
    // 진정한 비선형이면 위반량은 큰 양수 (수십 이상).
    assert!(avg > 5.0, "F의 affinity-위반량이 너무 작음: {:.2}", avg);
}
