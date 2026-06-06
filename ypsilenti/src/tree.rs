//! Tree mode (큰 입력). yhash와 동일 구조.

use crate::consts::{rounds, LevelTag, BLOCK_BYTES, MAX_TREE_DEPTH, STATE_WORDS};
use crate::encode::{encode, mask_mid, root_mask_mid};
use crate::perm::{compress_block, cv_to_state, derive_mask, finalize, truncate_cv, State};

pub fn compute_internal(
    level: u32,
    pos: u64,
    d_l: &[u8; 16],
    d_r: &[u8; 16],
    iv: &State,
) -> [u8; 16] {
    let block_l = pad_cv_to_block(d_l);
    let block_r = pad_cv_to_block(d_r);

    let seed_l = encode(LevelTag::Internal(level), pos, 0);
    let seed_r = encode(LevelTag::Internal(level), pos, 1);
    let mask_l = derive_mask(&seed_l, iv);
    let mask_r = derive_mask(&seed_r, iv);

    let y_l = compress_block(&block_l, &mask_l, rounds::INTERNAL);
    let y_r = compress_block(&block_r, &mask_r, rounds::INTERNAL);

    let mut acc = [0u32; STATE_WORDS];
    for i in 0..STATE_WORDS {
        acc[i] = y_l[i] ^ y_r[i];
    }

    let mm_seed = mask_mid(LevelTag::Internal(level), pos);
    let mm = derive_mask(&mm_seed, iv);
    let final_state = finalize(&acc, &mm);
    truncate_cv(&final_state)
}

pub fn compute_root_from_acc(acc: &State, total_len: u64, shape_hash: u32, iv: &State) -> [u8; 16] {
    let mm_seed = root_mask_mid(total_len, shape_hash);
    let mm = derive_mask(&mm_seed, iv);
    let final_state = finalize(acc, &mm);
    truncate_cv(&final_state)
}

pub fn root_from_single_leaf(leaf_digest: &[u8; 16], total_len: u64, iv: &State) -> [u8; 16] {
    let acc = cv_to_state(leaf_digest);
    compute_root_from_acc(&acc, total_len, 0, iv)
}

#[inline]
fn pad_cv_to_block(cv: &[u8; 16]) -> [u8; BLOCK_BYTES] {
    let mut block = [0u8; BLOCK_BYTES];
    block[..16].copy_from_slice(cv);
    block[16] = 0x01;
    block[BLOCK_BYTES - 1] |= 0x80;
    block
}

#[derive(Clone, Debug)]
pub struct TreeBuilder {
    pending: [Option<[u8; 16]>; MAX_TREE_DEPTH],
    next_leaf_pos: u64,
}

impl Default for TreeBuilder {
    fn default() -> Self {
        Self {
            pending: [None; MAX_TREE_DEPTH],
            next_leaf_pos: 0,
        }
    }
}

impl TreeBuilder {
    pub fn new() -> Self {
        Self::default()
    }

    #[inline]
    pub fn next_leaf_pos(&self) -> u64 {
        self.next_leaf_pos
    }

    pub fn push_leaf(&mut self, leaf_digest: [u8; 16], iv: &State) {
        let mut digest = leaf_digest;
        let mut level: u32 = 0;
        loop {
            let lvl_idx = level as usize;
            debug_assert!(lvl_idx < MAX_TREE_DEPTH);
            match self.pending[lvl_idx].take() {
                None => {
                    self.pending[lvl_idx] = Some(digest);
                    break;
                }
                Some(left) => {
                    let pos = self.next_leaf_pos >> (level + 1);
                    let new_level = level + 1;
                    digest = compute_internal(new_level, pos, &left, &digest, iv);
                    level = new_level;
                }
            }
        }
        self.next_leaf_pos += 1;
    }

    pub fn finalize(mut self, total_len: u64, iv: &State) -> [u8; 16] {
        let mut current: Option<[u8; 16]> = None;
        for level in 0..MAX_TREE_DEPTH {
            match (self.pending[level].take(), current) {
                (None, c) => current = c,
                (Some(p), None) => current = Some(p),
                (Some(p), Some(c)) => {
                    let pos = self.next_leaf_pos >> (level as u32 + 1);
                    current = Some(compute_internal(level as u32 + 1, pos, &p, &c, iv));
                }
            }
        }
        match current {
            Some(d) => {
                let acc = cv_to_state(&d);
                compute_root_from_acc(&acc, total_len, 1, iv)
            }
            None => {
                let acc = [0u32; STATE_WORDS];
                compute_root_from_acc(&acc, 0, 0, iv)
            }
        }
    }
}
