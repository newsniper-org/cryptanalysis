//! YHash leaf 압축 — Level B SIMD (inter-block batch). nightly 전용.
//!
//! ysc4의 `permute_batch`(SoA, `Simd<u64, BATCH>`)를 사용해 leaf의 n개 블록
//! mask-derive + compress를 lane-병렬로 수행한다. scalar 경로와 비트단위 일치.

use crate::consts::STATE_WORDS;
use crate::perm::State;
use core::simd::num::SimdUint;
use core::simd::Simd;
use ysc4::permutation_simd::{permute_batch, Vu64, BATCH};

/// Leaf의 n개 블록을 batch로 mask-derive + compress 하여 `acc` 반환.
///
/// `blocks[0..n]`, `seeds[0..n]` 유효 (`seeds` = per-block `encode` 16-byte).
/// scalar(`derive_mask` → `compress_block` → XOR 누적)와 결과 동일.
pub fn compute_leaf_acc(
    blocks: &[[u8; 128]],
    seeds: &[[u8; 16]],
    n: usize,
    iv: &State,
    mask_rounds: usize,
    leaf_rounds: usize,
) -> State {
    debug_assert!(n <= BATCH);

    // --- mask derive (SoA): md[i] lane j = iv[i] ⊕ (seed_j word i, i<2) ---
    let mut md = [[0u64; BATCH]; STATE_WORDS];
    for (i, row) in md.iter_mut().enumerate() {
        *row = [iv[i]; BATCH];
    }
    for j in 0..n {
        let w0 = u64::from_le_bytes(seeds[j][0..8].try_into().unwrap());
        let w1 = u64::from_le_bytes(seeds[j][8..16].try_into().unwrap());
        md[0][j] ^= w0;
        md[1][j] ^= w1;
    }
    let mut m: [Vu64; STATE_WORDS] = core::array::from_fn(|i| Vu64::from_array(md[i]));
    permute_batch(&mut m, mask_rounds);

    // --- compress (SoA): c_in[i] = block_word ⊕ mask ---
    let mut bl = [[0u64; BATCH]; STATE_WORDS];
    for j in 0..n {
        for i in 0..STATE_WORDS {
            bl[i][j] = u64::from_le_bytes(blocks[j][i * 8..i * 8 + 8].try_into().unwrap());
        }
    }
    let mut c: [Vu64; STATE_WORDS] = core::array::from_fn(|i| Vu64::from_array(bl[i]) ^ m[i]);
    permute_batch(&mut c, leaf_rounds);

    // --- fold lanes 0..n into acc (라운드 밖, word당 1회 수평 reduce) ---
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
