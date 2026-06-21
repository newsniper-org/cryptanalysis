//! yttrium 순열 — Level-B SIMD (inter-block batch). `feature = "simd"`.
//!
//! 독립 블록 BATCH(=T_MAX=8)개를 lane에 실어 동일 라운드를 lane-병렬 적용(SoA).
//! 수평 연산(fold)은 라운드 밖. 백엔드: 안정 `wide::u32x8`.
//! scalar `permute`와 **lane별 bit-exact**(아래 `batch_leaf_matches_scalar`).

use super::{rc, EPS_PLUS, F_ROT, P_PI, REDUCTION, ROT_A, ROT_B, SIG_K, STATE_WORDS};
use wide::u32x8;

pub const BATCH: usize = 8;

#[inline(always)]
fn shl(v: u32x8, k: u32) -> u32x8 {
    v << u32x8::splat(k)
}
#[inline(always)]
fn shr(v: u32x8, k: u32) -> u32x8 {
    v >> u32x8::splat(k)
}
#[inline(always)]
fn rotl(v: u32x8, k: u32) -> u32x8 {
    shl(v, k) | shr(v, 32 - k)
}
#[inline(always)]
fn rotr(v: u32x8, k: u32) -> u32x8 {
    rotl(v, 32 - k)
}

#[inline(always)]
fn f_v(s: u32x8) -> u32x8 {
    let mut acc = s;
    acc ^= rotl(s, F_ROT[0].0) & rotl(s, F_ROT[0].1);
    acc ^= rotl(s, F_ROT[1].0) & rotl(s, F_ROT[1].1);
    acc ^= rotl(s, F_ROT[2].0) & rotl(s, F_ROT[2].1);
    acc
}

#[inline(always)]
fn alpha_v(y: u32x8) -> u32x8 {
    let mask = u32x8::splat(0) - shr(y, 31); // 0 또는 0xFFFF_FFFF
    shl(y, 1) ^ (mask & u32x8::splat(REDUCTION))
}
#[inline(always)]
fn alpha_pow_v(mut y: u32x8, k: u32) -> u32x8 {
    for _ in 0..k {
        y = alpha_v(y);
    }
    y
}

/// BATCH개 독립 상태(SoA)에 yttrium 라운드 `rounds`회. scalar와 lane별 일치.
#[inline]
fn permute_batch(soa: &mut [u32x8; STATE_WORDS], rounds: usize) {
    for r in 0..rounds {
        soa[r % STATE_WORDS] ^= u32x8::splat(rc(r)); // ι (비반복 RC, 레인 r%8)
        let mut xp = [u32x8::splat(0); STATE_WORDS];
        for i in 0..STATE_WORDS {
            xp[i] = rotl(soa[i], ROT_A); // x'_i = ROTL_α
        }
        let mut s = u32x8::splat(0); // 영합 S = Σ ε_i x'_i
        for i in 0..STATE_WORDS {
            if EPS_PLUS[i] {
                s += xp[i];
            } else {
                s -= xp[i];
            }
        }
        let t = f_v(s);
        for i in 0..STATE_WORDS {
            soa[i] = alpha_pow_v(rotr(xp[i] + t, ROT_B), SIG_K[i]); // ARX + σ
        }
        let old = *soa; // π
        for i in 0..STATE_WORDS {
            soa[i] = old[P_PI[i]];
        }
    }
}

/// Leaf의 n개 블록(≤BATCH) mask-derive + compress 후 acc(XOR) 반환. scalar와 bit-exact.
#[inline]
pub fn compute_leaf_acc(
    blocks: &[[u8; 32]],
    seeds: &[[u8; 16]],
    n: usize,
    iv: &[u32; STATE_WORDS],
    r_mask: usize,
    r_b: usize,
) -> [u32; STATE_WORDS] {
    debug_assert!(n <= BATCH);
    let mut md = [[0u32; BATCH]; STATE_WORDS];
    for (i, row) in md.iter_mut().enumerate() {
        *row = [iv[i]; BATCH];
    }
    for j in 0..n {
        for i in 0..4 {
            md[i][j] ^= u32::from_le_bytes(seeds[j][i * 4..i * 4 + 4].try_into().unwrap());
        }
    }
    let mut m: [u32x8; STATE_WORDS] = core::array::from_fn(|i| u32x8::from(md[i]));
    permute_batch(&mut m, r_mask);

    let mut bl = [[0u32; BATCH]; STATE_WORDS];
    for j in 0..n {
        for i in 0..STATE_WORDS {
            bl[i][j] = u32::from_le_bytes(blocks[j][i * 4..i * 4 + 4].try_into().unwrap());
        }
    }
    let mut c: [u32x8; STATE_WORDS] = core::array::from_fn(|i| u32x8::from(bl[i]) ^ m[i]);
    permute_batch(&mut c, r_b);

    let mut acc = [0u32; STATE_WORDS];
    for i in 0..STATE_WORDS {
        let lanes = c[i].to_array();
        let mut w = 0u32;
        for &l in lanes.iter().take(n) {
            w ^= l;
        }
        acc[i] = w;
    }
    acc
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{compress_block, derive_mask, encode, LevelTag, Rounds};

    /// batch leaf acc가 scalar 경로와 bit-exact (활성 백엔드).
    #[test]
    fn batch_leaf_matches_scalar() {
        let iv: [u32; STATE_WORDS] =
            core::array::from_fn(|i| 0x9E37_79B9u32 ^ (i as u32).wrapping_mul(0x101));
        let rd = Rounds::V8_12_24;
        for n in 1..=BATCH {
            let blocks: [[u8; 32]; BATCH] =
                core::array::from_fn(|j| core::array::from_fn(|b| (j * 13 + b * 7 + 1) as u8));
            let seeds: [[u8; 16]; BATCH] =
                core::array::from_fn(|j| encode(LevelTag::Leaf, 0, j as u32));
            let mut want = [0u32; STATE_WORDS];
            for j in 0..n {
                let mask = derive_mask(&seeds[j], &iv, rd.r_mask);
                let y = compress_block(&blocks[j], &mask, rd.r_b);
                for i in 0..STATE_WORDS {
                    want[i] ^= y[i];
                }
            }
            let got = compute_leaf_acc(&blocks, &seeds, n, &iv, rd.r_mask, rd.r_b);
            assert_eq!(got, want, "n={n}");
        }
    }
}
