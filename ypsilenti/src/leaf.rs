//! Leaf 노드 (yhash와 동일 구조, 작은 단위로).

use crate::consts::{rounds, LevelTag, BLOCK_BYTES, T_MAX};
use crate::encode::{encode, mask_mid};
use crate::perm::{derive_mask, finalize, truncate_cv, State};
#[cfg(not(ypsi_simd_any))]
use crate::consts::STATE_WORDS;
#[cfg(not(ypsi_simd_any))]
use crate::perm::compress_block;

pub fn compute_leaf(
    blocks: &[[u8; BLOCK_BYTES]],
    n: usize,
    pos: u64,
    iv: &State,
) -> [u8; 16] {
    debug_assert!(n <= T_MAX);

    // Level B SIMD: n개 블록의 mask-derive + compress를 batch (nightly/stable).
    #[cfg(ypsi_simd_any)]
    let acc = {
        let mut seeds = [[0u8; 16]; T_MAX];
        for (j, s) in seeds.iter_mut().enumerate().take(n) {
            *s = encode(LevelTag::Leaf, pos, j as u32);
        }
        crate::perm_simd::compute_leaf_acc(
            blocks, &seeds, n, iv, rounds::MASK_DERIVE, rounds::LEAF,
        )
    };
    #[cfg(not(ypsi_simd_any))]
    let acc = {
        let mut acc = [0u32; STATE_WORDS];
        for j in 0..n {
            let seed = encode(LevelTag::Leaf, pos, j as u32);
            let mask = derive_mask(&seed, iv);
            let y = compress_block(&blocks[j], &mask, rounds::LEAF);
            for i in 0..STATE_WORDS {
                acc[i] ^= y[i];
            }
        }
        acc
    };

    let mm_seed = mask_mid(LevelTag::Leaf, pos);
    let mm = derive_mask(&mm_seed, iv);
    let final_state = finalize(&acc, &mm);
    truncate_cv(&final_state)
}

pub fn pad_partial_block(input: &[u8]) -> [u8; BLOCK_BYTES] {
    debug_assert!(input.len() < BLOCK_BYTES);
    let mut block = [0u8; BLOCK_BYTES];
    block[..input.len()].copy_from_slice(input);
    block[input.len()] = 0x01;
    block[BLOCK_BYTES - 1] |= 0x80;
    block
}

pub fn split_input_into_blocks(input: &[u8]) -> ([[u8; BLOCK_BYTES]; T_MAX], usize) {
    let mut blocks = [[0u8; BLOCK_BYTES]; T_MAX];
    let full_blocks = input.len() / BLOCK_BYTES;
    let rem = input.len() % BLOCK_BYTES;

    debug_assert!(full_blocks <= T_MAX);

    for j in 0..full_blocks {
        blocks[j].copy_from_slice(&input[j * BLOCK_BYTES..(j + 1) * BLOCK_BYTES]);
    }

    let n = if rem > 0 || full_blocks == 0 {
        debug_assert!(full_blocks < T_MAX);
        blocks[full_blocks] = pad_partial_block(&input[full_blocks * BLOCK_BYTES..]);
        full_blocks + 1
    } else {
        full_blocks
    };

    (blocks, n)
}
