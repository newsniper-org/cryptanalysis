//! ypsilenti Hasher API.

use crate::consts::{domain, rounds, BLOCK_BYTES, STATE_WORDS, T_MAX};
use crate::leaf::{compute_leaf, split_input_into_blocks};
use crate::perm::{permute, State};
use crate::tree::{root_from_single_leaf, TreeBuilder};
use zeroize::Zeroize;

/// 128-bit digest.
pub type Digest = [u8; 16];

#[derive(Clone)]
pub struct YpsiBuilder {
    iv: State,
}

impl YpsiBuilder {
    pub fn keyed(key: &[u8]) -> Self {
        let mut iv_state = [0u32; STATE_WORDS];
        // 도메인 + key (≤ 24 byte = 6 워드)
        let dom_bytes = domain::KEYED.to_le_bytes();
        iv_state[STATE_WORDS - 1] = u32::from_le_bytes(dom_bytes[0..4].try_into().unwrap());
        iv_state[STATE_WORDS - 2] = u32::from_le_bytes(dom_bytes[4..8].try_into().unwrap());

        for (i, chunk) in key.chunks(4).enumerate() {
            if i >= STATE_WORDS - 2 {
                break;
            }
            let mut buf = [0u8; 4];
            buf[..chunk.len()].copy_from_slice(chunk);
            iv_state[i] ^= u32::from_le_bytes(buf);
        }
        permute(&mut iv_state, rounds::MASK_DERIVE);
        Self { iv: iv_state }
    }

    pub fn unkeyed() -> Self {
        let mut iv_state = [0u32; STATE_WORDS];
        let dom_bytes = domain::UNKEYED.to_le_bytes();
        iv_state[STATE_WORDS - 1] = u32::from_le_bytes(dom_bytes[0..4].try_into().unwrap());
        iv_state[STATE_WORDS - 2] = u32::from_le_bytes(dom_bytes[4..8].try_into().unwrap());
        permute(&mut iv_state, rounds::MASK_DERIVE);
        Self { iv: iv_state }
    }

    pub fn build_hasher(&self) -> YpsiHasher {
        YpsiHasher::new(&self.iv)
    }

    #[cfg(feature = "alloc")]
    #[inline]
    pub(crate) fn iv_ref(&self) -> &State {
        &self.iv
    }
}

impl Default for YpsiBuilder {
    fn default() -> Self {
        Self::unkeyed()
    }
}

impl Drop for YpsiBuilder {
    fn drop(&mut self) {
        self.iv.zeroize();
    }
}

impl core::hash::BuildHasher for YpsiBuilder {
    type Hasher = YpsiHasher;
    fn build_hasher(&self) -> YpsiHasher {
        YpsiBuilder::build_hasher(self)
    }
}

#[derive(Clone)]
pub struct YpsiHasher {
    iv: State,
    leaf_buf: [u8; T_MAX * BLOCK_BYTES],
    leaf_buf_len: usize,
    tree: TreeBuilder,
    in_tree_mode: bool,
    total_len: u64,
}

impl YpsiHasher {
    pub(crate) fn new(iv: &State) -> Self {
        Self {
            iv: *iv,
            leaf_buf: [0u8; T_MAX * BLOCK_BYTES],
            leaf_buf_len: 0,
            tree: TreeBuilder::new(),
            in_tree_mode: false,
            total_len: 0,
        }
    }

    pub fn update(&mut self, mut data: &[u8]) {
        self.total_len = self.total_len.wrapping_add(data.len() as u64);
        while !data.is_empty() {
            let space = T_MAX * BLOCK_BYTES - self.leaf_buf_len;
            let take = core::cmp::min(space, data.len());
            self.leaf_buf[self.leaf_buf_len..self.leaf_buf_len + take]
                .copy_from_slice(&data[..take]);
            self.leaf_buf_len += take;
            data = &data[take..];
            if self.leaf_buf_len == T_MAX * BLOCK_BYTES {
                self.flush_leaf_to_tree();
            }
        }
    }

    fn flush_leaf_to_tree(&mut self) {
        let n_bytes = self.leaf_buf_len;
        let leaf_pos = self.tree.next_leaf_pos();
        let leaf_digest = compute_full_leaf(&self.leaf_buf[..n_bytes], leaf_pos, &self.iv);
        self.tree.push_leaf(leaf_digest, &self.iv);
        self.leaf_buf_len = 0;
        self.in_tree_mode = true;
    }

    pub fn finalize(mut self) -> Digest {
        if !self.in_tree_mode {
            let leaf_digest = compute_full_leaf(&self.leaf_buf[..self.leaf_buf_len], 0, &self.iv);
            root_from_single_leaf(&leaf_digest, self.total_len, &self.iv)
        } else {
            if self.leaf_buf_len > 0 {
                self.flush_leaf_to_tree();
            }
            self.tree.clone().finalize(self.total_len, &self.iv)
        }
    }

    pub fn finalize_u64(self) -> u64 {
        let d = self.finalize();
        u64::from_le_bytes(d[0..8].try_into().unwrap())
    }
}

fn compute_full_leaf(input: &[u8], pos: u64, iv: &State) -> Digest {
    let (blocks, n) = split_input_into_blocks(input);
    compute_leaf(&blocks, n, pos, iv)
}

impl Drop for YpsiHasher {
    fn drop(&mut self) {
        self.iv.zeroize();
        self.leaf_buf.zeroize();
    }
}

impl core::hash::Hasher for YpsiHasher {
    fn write(&mut self, bytes: &[u8]) {
        self.update(bytes);
    }
    fn finish(&self) -> u64 {
        self.clone().finalize_u64()
    }
}
