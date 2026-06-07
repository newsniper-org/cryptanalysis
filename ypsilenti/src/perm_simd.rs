//! ypsilenti 순열 — Level B SIMD (inter-block batch). nightly 전용.
//!
//! Level A(상태 8워드를 한 벡터에)는 매 라운드 수평 `reduce_xor` + σ-층 lane
//! 추출 때문에 scalar보다 느렸다. **Level B는 독립 블록 BATCH개를 lane에 실어**
//! *동일 연산을 lane-병렬*로 적용한다. 수평 연산은 라운드 루프 밖(최종 fold)에만.
//!
//! - SoA 레이아웃: `soa[i]` 는 `Simd<u32, BATCH>` — 모든 lane(=블록)의 word `i`.
//! - F·σ(α-곱)·broadcast·RC·π 전부 lane-wise. 추출/삽입 없음.
//!
//! stable SIMD는 미구현 (해당 빌드는 scalar leaf 사용).

use crate::consts::{F_ROT_A, F_ROT_B, F_ROT_C, F_ROT_D, P_PI, RC, STATE_WORDS};
use crate::gf32::REDUCTION;
use crate::perm::State;
use core::simd::{num::SimdUint, Simd};

/// SIMD batch 폭 = T_MAX (leaf 당 최대 블록 수).
pub const BATCH: usize = 8;
type V = Simd<u32, BATCH>;

#[inline(always)]
fn rotl(v: V, k: u32) -> V {
    (v << V::splat(k)) | (v >> V::splat(32 - k))
}

#[inline(always)]
fn f_v(s: V) -> V {
    s ^ (rotl(s, F_ROT_A) & rotl(s, F_ROT_B)) ^ (rotl(s, F_ROT_C) & rotl(s, F_ROT_D))
}

#[inline(always)]
fn alpha_v(y: V) -> V {
    let msb = y >> V::splat(31); // lane: 0 또는 1
    let mask = V::splat(0) - msb; // lane: 0 또는 0xFFFF_FFFF
    (y << V::splat(1)) ^ (mask & V::splat(REDUCTION))
}

#[inline(always)]
fn alpha_pow_v(mut y: V, k: u32) -> V {
    for _ in 0..k {
        y = alpha_v(y);
    }
    y
}

/// BATCH개 독립 상태(SoA)에 `rounds` 라운드 적용. scalar `permute`와 lane별 일치.
#[inline]
pub fn permute_batch(soa: &mut [V; STATE_WORDS], rounds: usize) {
    for r in 0..rounds {
        let pos = r & 7;
        soa[pos] ^= V::splat(RC[pos]);

        let mut s = soa[0];
        for i in 1..STATE_WORDS {
            s ^= soa[i];
        }
        let t = f_v(s);
        for w in soa.iter_mut() {
            *w ^= t;
        }

        soa[0] = alpha_pow_v(soa[0], 1);
        soa[4] = alpha_pow_v(soa[4], 3);

        let old = *soa;
        for i in 0..STATE_WORDS {
            soa[i] = old[P_PI[i]];
        }
    }
}

/// Leaf의 n개 블록을 batch로 mask-derive + compress 하여 `acc` 반환.
///
/// scalar 경로(`derive_mask` → `compress_block` → XOR 누적)와 비트단위로 일치.
/// `blocks[0..n]`, `seeds[0..n]` 유효 (`seeds` = per-block `encode` 16-byte).
pub fn compute_leaf_acc(
    blocks: &[[u8; 32]],
    seeds: &[[u8; 16]],
    n: usize,
    iv: &State,
    mask_rounds: usize,
    leaf_rounds: usize,
) -> State {
    debug_assert!(n <= BATCH);

    // --- mask derive (SoA): md[i] lane j = iv[i] ⊕ (seed_j word i, i<4) ---
    let mut md = [[0u32; BATCH]; STATE_WORDS];
    for (i, row) in md.iter_mut().enumerate() {
        *row = [iv[i]; BATCH];
    }
    for j in 0..n {
        for i in 0..4 {
            let w = u32::from_le_bytes(seeds[j][i * 4..i * 4 + 4].try_into().unwrap());
            md[i][j] ^= w;
        }
    }
    let mut m: [V; STATE_WORDS] = core::array::from_fn(|i| V::from_array(md[i]));
    permute_batch(&mut m, mask_rounds);

    // --- compress (SoA): c_in[i] = block_word ⊕ mask ---
    let mut bl = [[0u32; BATCH]; STATE_WORDS];
    for j in 0..n {
        for i in 0..STATE_WORDS {
            bl[i][j] = u32::from_le_bytes(blocks[j][i * 4..i * 4 + 4].try_into().unwrap());
        }
    }
    let mut c: [V; STATE_WORDS] = core::array::from_fn(|i| V::from_array(bl[i]) ^ m[i]);
    permute_batch(&mut c, leaf_rounds);

    // --- fold lanes 0..n into acc (라운드 밖, word당 1회 수평 reduce) ---
    let mut active = [0u32; BATCH];
    for a in active.iter_mut().take(n) {
        *a = u32::MAX;
    }
    let act = V::from_array(active);
    let mut acc = [0u32; STATE_WORDS];
    for i in 0..STATE_WORDS {
        acc[i] = (c[i] & act).reduce_xor();
    }
    acc
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::perm::permute_scalar;

    #[test]
    fn batch_matches_scalar() {
        // 8개 독립 상태를 만들어 scalar permute와 batch permute 결과 비교.
        let mut states = [[0u32; STATE_WORDS]; BATCH];
        for (j, st) in states.iter_mut().enumerate() {
            for (i, w) in st.iter_mut().enumerate() {
                *w = (0x1000_0001u32)
                    .wrapping_mul((j as u32 + 1).wrapping_mul(i as u32 + 7))
                    .wrapping_add(0xDEAD_0000 ^ (j as u32) << 8 ^ i as u32);
            }
        }
        for &rounds in &[1usize, 4, 6, 8] {
            // scalar
            let mut want = states;
            for st in want.iter_mut() {
                permute_scalar(st, rounds);
            }
            // batch (SoA transpose)
            let mut soa: [V; STATE_WORDS] =
                core::array::from_fn(|i| V::from_array(core::array::from_fn(|j| states[j][i])));
            permute_batch(&mut soa, rounds);
            let got: [[u32; STATE_WORDS]; BATCH] =
                core::array::from_fn(|j| core::array::from_fn(|i| soa[i].to_array()[j]));
            assert_eq!(got, want, "rounds={}", rounds);
        }
    }
}
