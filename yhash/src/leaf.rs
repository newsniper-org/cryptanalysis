//! Leaf 노드 압축. SPEC §4.1.
//!
//! Leaf: `Acc = ⊕_j P(x_j ⊕ mask(LEAF, pos, j), R_b)`,
//! `digest = trunc_n(P(Acc ⊕ maskMid(LEAF, pos), R_c))`.

use crate::consts::{rounds, LevelTag, BLOCK_BYTES, STATE_WORDS, T_MAX};
use crate::encode::{encode, mask_mid};
use crate::perm::{compress_block, derive_mask, finalize, truncate_cv, State};

/// Leaf 노드 계산 (full input ≤ T_MAX × BLOCK_BYTES).
///
/// `blocks`는 padding 된 1024-bit 블록 sequence. 각 블록 128 byte.
/// `n` = 블록 수 (`≤ T_MAX`).
///
/// 반환: 32-byte chaining value.
pub fn compute_leaf(
    blocks: &[[u8; BLOCK_BYTES]],
    n: usize,
    pos: u64,
    iv: &State,
) -> [u8; 32] {
    debug_assert!(n <= T_MAX);
    debug_assert!(n <= blocks.len());

    let mut acc = [0u64; STATE_WORDS];
    for j in 0..n {
        let seed = encode(LevelTag::Leaf, pos, j as u32);
        let mask = derive_mask(&seed, iv);
        let y = compress_block(&blocks[j], &mask, rounds::LEAF);
        for i in 0..STATE_WORDS {
            acc[i] ^= y[i];
        }
    }

    let mm_seed = mask_mid(LevelTag::Leaf, pos);
    let mm = derive_mask(&mm_seed, iv);
    let final_state = finalize(&acc, &mm);
    truncate_cv(&final_state)
}

/// Multi-rate padding. 마지막 (혹은 유일한) 부분 블록에 적용.
///
/// `input.len() < BLOCK_BYTES`. 출력: 128-byte 블록 (input || 0x01 || zeros || 0x80).
pub fn pad_partial_block(input: &[u8]) -> [u8; BLOCK_BYTES] {
    debug_assert!(input.len() < BLOCK_BYTES);
    let mut block = [0u8; BLOCK_BYTES];
    block[..input.len()].copy_from_slice(input);
    block[input.len()] = 0x01;
    block[BLOCK_BYTES - 1] |= 0x80;
    block
}

/// 입력 슬라이스를 ≤ T_MAX 블록으로 분할 + 마지막 부분 블록 padding.
///
/// 반환: `(blocks_buf, n)` — `blocks_buf[0..n]`이 유효한 블록.
pub fn split_input_into_blocks(input: &[u8]) -> ([[u8; BLOCK_BYTES]; T_MAX], usize) {
    let mut blocks = [[0u8; BLOCK_BYTES]; T_MAX];
    let full_blocks = input.len() / BLOCK_BYTES;
    let rem = input.len() % BLOCK_BYTES;

    debug_assert!(full_blocks <= T_MAX);

    for j in 0..full_blocks {
        blocks[j].copy_from_slice(&input[j * BLOCK_BYTES..(j + 1) * BLOCK_BYTES]);
    }

    let n = if rem > 0 || full_blocks == 0 {
        // 부분 블록 padding (또는 빈 입력 → 1개 padding 블록)
        debug_assert!(full_blocks < T_MAX);
        blocks[full_blocks] = pad_partial_block(&input[full_blocks * BLOCK_BYTES..]);
        full_blocks + 1
    } else {
        full_blocks
    };

    (blocks, n)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn dummy_iv() -> State {
        let mut s = [0u64; STATE_WORDS];
        s[15] = crate::consts::domain::UNKEYED;
        ysc4::permutation::permute(&mut s, rounds::MASK_DERIVE);
        s
    }

    #[test]
    fn leaf_deterministic() {
        let iv = dummy_iv();
        let (blocks, n) = split_input_into_blocks(b"hello world");
        let d1 = compute_leaf(&blocks, n, 0, &iv);
        let d2 = compute_leaf(&blocks, n, 0, &iv);
        assert_eq!(d1, d2);
    }

    #[test]
    fn leaf_distinct_input() {
        let iv = dummy_iv();
        let (b1, n1) = split_input_into_blocks(b"hello");
        let (b2, n2) = split_input_into_blocks(b"world");
        assert_ne!(compute_leaf(&b1, n1, 0, &iv), compute_leaf(&b2, n2, 0, &iv));
    }

    #[test]
    fn leaf_distinct_position() {
        let iv = dummy_iv();
        let (blocks, n) = split_input_into_blocks(b"same");
        assert_ne!(compute_leaf(&blocks, n, 0, &iv), compute_leaf(&blocks, n, 1, &iv));
    }

    #[test]
    fn split_empty_input() {
        let (_blocks, n) = split_input_into_blocks(&[]);
        assert_eq!(n, 1); // empty도 padding 블록 1개
    }

    #[test]
    fn split_exact_block() {
        let input = [0xAA; BLOCK_BYTES];
        let (blocks, n) = split_input_into_blocks(&input);
        assert_eq!(n, 1);
        assert_eq!(blocks[0], input);
    }
}
