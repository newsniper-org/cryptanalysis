//! YHash leaf 압축 — Level B SIMD (inter-block batch).
//!
//! ysc4의 batch 순열을 사용해 leaf의 n개 블록 mask-derive + compress를 lane-병렬로
//! 수행한다. scalar 경로와 비트단위 일치.
//!
//! 백엔드:
//! - `nightly-portable-simd` → `core::simd::Simd<u64, 8>` (8-lane, 1 batch)
//! - `stable-portable-simd`  → `wide::u64x4` (4-lane, leaf 8블록을 ≤2 chunk)
//!
//! u64는 wide 최대 폭이 4-lane이라 stable은 4개씩 나눠 처리한다.

use crate::consts::STATE_WORDS;
use crate::perm::State;

#[cfg(feature = "nightly-portable-simd")]
pub use nightly::compute_leaf_acc;

#[cfg(all(feature = "stable-portable-simd", not(feature = "nightly-portable-simd")))]
pub use stable::compute_leaf_acc;

// ---- nightly: core::simd Simd<u64, 8> (8-lane, 단일 batch) ----

#[cfg(feature = "nightly-portable-simd")]
mod nightly {
    use super::{State, STATE_WORDS};
    use core::simd::num::SimdUint;
    use core::simd::Simd;
    use ysc4::permutation_simd::{permute_batch, Vu64, BATCH};

    /// Leaf의 n개 블록(≤BATCH)을 batch로 mask-derive + compress → `acc`.
    pub fn compute_leaf_acc(
        blocks: &[[u8; 128]],
        seeds: &[[u8; 16]],
        n: usize,
        iv: &State,
        mask_rounds: usize,
        leaf_rounds: usize,
    ) -> State {
        debug_assert!(n <= BATCH);

        let mut md = [[0u64; BATCH]; STATE_WORDS];
        for (i, row) in md.iter_mut().enumerate() {
            *row = [iv[i]; BATCH];
        }
        for j in 0..n {
            md[0][j] ^= u64::from_le_bytes(seeds[j][0..8].try_into().unwrap());
            md[1][j] ^= u64::from_le_bytes(seeds[j][8..16].try_into().unwrap());
        }
        let mut m: [Vu64; STATE_WORDS] = core::array::from_fn(|i| Vu64::from_array(md[i]));
        permute_batch(&mut m, mask_rounds);

        let mut bl = [[0u64; BATCH]; STATE_WORDS];
        for j in 0..n {
            for i in 0..STATE_WORDS {
                bl[i][j] = u64::from_le_bytes(blocks[j][i * 8..i * 8 + 8].try_into().unwrap());
            }
        }
        let mut c: [Vu64; STATE_WORDS] = core::array::from_fn(|i| Vu64::from_array(bl[i]) ^ m[i]);
        permute_batch(&mut c, leaf_rounds);

        let mut active = [0u64; BATCH];
        for a in active.iter_mut().take(n) {
            *a = u64::MAX;
        }
        let act = Simd::<u64, BATCH>::from_array(active);
        let mut acc = [0u64; STATE_WORDS];
        for i in 0..STATE_WORDS {
            acc[i] = (c[i] & act).reduce_xor();
        }
        acc
    }
}

// ---- stable: wide::u64x4 (4-lane, leaf 8블록을 ≤2 chunk) ----

#[cfg(all(feature = "stable-portable-simd", not(feature = "nightly-portable-simd")))]
mod stable {
    use super::{State, STATE_WORDS};
    use wide::u64x4;
    use ysc4::permutation_simd::permute_batch_wide;

    const W: usize = 4;

    /// 4-lane chunk(`cnt` ≤ 4) 하나를 처리해 `acc`에 누적.
    fn process_chunk(
        blocks: &[[u8; 128]],
        seeds: &[[u8; 16]],
        start: usize,
        cnt: usize,
        iv: &State,
        mask_rounds: usize,
        leaf_rounds: usize,
        acc: &mut State,
    ) {
        let mut md = [[0u64; W]; STATE_WORDS];
        for (i, row) in md.iter_mut().enumerate() {
            *row = [iv[i]; W];
        }
        for jj in 0..cnt {
            let j = start + jj;
            md[0][jj] ^= u64::from_le_bytes(seeds[j][0..8].try_into().unwrap());
            md[1][jj] ^= u64::from_le_bytes(seeds[j][8..16].try_into().unwrap());
        }
        let mut m: [u64x4; STATE_WORDS] = core::array::from_fn(|i| u64x4::from(md[i]));
        permute_batch_wide(&mut m, mask_rounds);

        let mut bl = [[0u64; W]; STATE_WORDS];
        for jj in 0..cnt {
            let j = start + jj;
            for i in 0..STATE_WORDS {
                bl[i][jj] = u64::from_le_bytes(blocks[j][i * 8..i * 8 + 8].try_into().unwrap());
            }
        }
        let mut c: [u64x4; STATE_WORDS] = core::array::from_fn(|i| u64x4::from(bl[i]) ^ m[i]);
        permute_batch_wide(&mut c, leaf_rounds);

        for i in 0..STATE_WORDS {
            let lanes = c[i].to_array();
            for &l in lanes.iter().take(cnt) {
                acc[i] ^= l;
            }
        }
    }

    /// Leaf의 n개 블록을 4개씩 나눠 batch 처리 → `acc`.
    pub fn compute_leaf_acc(
        blocks: &[[u8; 128]],
        seeds: &[[u8; 16]],
        n: usize,
        iv: &State,
        mask_rounds: usize,
        leaf_rounds: usize,
    ) -> State {
        let mut acc = [0u64; STATE_WORDS];
        let mut start = 0;
        while start < n {
            let cnt = (n - start).min(W);
            process_chunk(
                blocks, seeds, start, cnt, iv, mask_rounds, leaf_rounds, &mut acc,
            );
            start += cnt;
        }
        acc
    }
}
