//! YHasher — streaming hash API.
//!
//! 무-heap 디자인: 모든 buffer는 fixed-size. ≤ SINGLE_LEAF_LIMIT 입력은 fast-path.

use crate::consts::{domain, rounds, BLOCK_BYTES, MAX_TREE_DEPTH, STATE_WORDS, T_MAX};
use crate::leaf::{compute_leaf, split_input_into_blocks};
use crate::perm::{cv_to_state, derive_mask, State};
use crate::tree::{compute_root_from_acc, root_from_single_leaf, TreeBuilder};
use zeroize::{Zeroize, ZeroizeOnDrop};

/// 256-bit chaining value / digest.
pub type Digest = [u8; 32];

/// YHasher seed (keyed or unkeyed) builder.
///
/// `BuildHasher` 호환 — HashMap에서 `with_hasher(YHashBuilder::new(...))` 사용 가능.
#[derive(Clone, Zeroize, ZeroizeOnDrop)]
pub struct YHashBuilder {
    iv: State,
}

impl YHashBuilder {
    /// Keyed builder. `key`는 임의 길이지만 보통 16 byte (128-bit).
    pub fn keyed(key: &[u8]) -> Self {
        let mut iv_state = [0u64; STATE_WORDS];
        iv_state[STATE_WORDS - 1] = domain::KEYED;
        // 키를 capacity에 적재 (≤ STATE_BYTES). 더 길면 wrap.
        for (i, chunk) in key.chunks(8).enumerate() {
            if i >= STATE_WORDS - 1 {
                break;
            }
            let mut buf = [0u8; 8];
            buf[..chunk.len()].copy_from_slice(chunk);
            iv_state[i] ^= u64::from_le_bytes(buf);
        }
        ysc4::permutation::permute(&mut iv_state, rounds::MASK_DERIVE);
        Self { iv: iv_state }
    }

    /// Unkeyed builder (fixed NUMS IV).
    pub fn unkeyed() -> Self {
        let mut iv_state = [0u64; STATE_WORDS];
        iv_state[STATE_WORDS - 1] = domain::UNKEYED;
        ysc4::permutation::permute(&mut iv_state, rounds::MASK_DERIVE);
        Self { iv: iv_state }
    }

    /// 새 hasher.
    pub fn build_hasher(&self) -> YHasher {
        YHasher::new(&self.iv)
    }

    /// 내부 IV 참조 (parallel 모듈에서 사용).
    #[cfg(feature = "alloc")]
    #[inline]
    pub(crate) fn iv_ref(&self) -> &State {
        &self.iv
    }
}

impl Default for YHashBuilder {
    fn default() -> Self {
        Self::unkeyed()
    }
}

impl core::hash::BuildHasher for YHashBuilder {
    type Hasher = YHasher;
    fn build_hasher(&self) -> YHasher {
        YHashBuilder::build_hasher(self)
    }
}

/// YHash incremental hasher.
///
/// Stack-only state. Fast path: ≤ SINGLE_LEAF_LIMIT (1024 byte) → 단일 leaf,
/// 그 이상 → tree mode (depth ≤ MAX_TREE_DEPTH = 32).
#[derive(Clone)]
pub struct YHasher {
    iv: State,
    /// 단일-leaf path 누적용 buffer (T_MAX 블록 = 1024 byte).
    leaf_buf: [u8; T_MAX * BLOCK_BYTES],
    /// `leaf_buf`의 valid byte 수.
    leaf_buf_len: usize,
    /// tree mode 활성화 시 TreeBuilder.
    tree: TreeBuilder,
    /// tree mode 활성화 시 true (= overflow 발생).
    in_tree_mode: bool,
    /// 전체 입력 길이 (root encoding용).
    total_len: u64,
}

impl Drop for YHasher {
    fn drop(&mut self) {
        self.iv.zeroize();
        self.leaf_buf.zeroize();
        // TreeBuilder는 자체 Drop으로 처리
    }
}

impl YHasher {
    /// 내부적으로 사용 — IV로부터 새 hasher.
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

    /// 메시지 흡수. 임의 길이 가능.
    pub fn update(&mut self, mut data: &[u8]) {
        self.total_len = self.total_len.wrapping_add(data.len() as u64);

        // (1) tree mode이면 leaf_buf가 가득 차는 대로 leaf finalize → tree.push_leaf.
        // (2) tree mode가 아니지만 leaf_buf가 가득 차면 첫 leaf만들고 tree mode로 전환.

        while !data.is_empty() {
            let space = T_MAX * BLOCK_BYTES - self.leaf_buf_len;
            let take = core::cmp::min(space, data.len());
            self.leaf_buf[self.leaf_buf_len..self.leaf_buf_len + take]
                .copy_from_slice(&data[..take]);
            self.leaf_buf_len += take;
            data = &data[take..];

            if self.leaf_buf_len == T_MAX * BLOCK_BYTES {
                // leaf 가득 → flush as full leaf
                self.flush_leaf_to_tree();
            }
        }
    }

    /// 현재 leaf_buf의 데이터로 leaf digest 계산 후 tree에 push.
    fn flush_leaf_to_tree(&mut self) {
        let n_bytes = self.leaf_buf_len;
        let leaf_pos = self.tree.next_leaf_pos();
        let leaf_digest = compute_full_leaf(&self.leaf_buf[..n_bytes], leaf_pos, &self.iv);
        self.tree.push_leaf(leaf_digest, &self.iv);
        self.leaf_buf_len = 0;
        self.in_tree_mode = true;
    }

    /// 최종 digest 계산 (consumes self).
    pub fn finalize(mut self) -> Digest {
        if !self.in_tree_mode {
            // Single-leaf fast path
            let leaf_digest = compute_full_leaf(&self.leaf_buf[..self.leaf_buf_len], 0, &self.iv);
            root_from_single_leaf(&leaf_digest, self.total_len, &self.iv)
        } else {
            // 남은 leaf_buf가 있으면 추가
            if self.leaf_buf_len > 0 {
                self.flush_leaf_to_tree();
            }
            self.tree.clone().finalize(self.total_len, &self.iv)
        }
    }

    /// 64-bit 출력 (HashMap용).
    pub fn finalize_u64(self) -> u64 {
        let d = self.finalize();
        u64::from_le_bytes(d[0..8].try_into().unwrap())
    }
}

/// Helper: leaf 입력 → 32-byte CV.
fn compute_full_leaf(input: &[u8], pos: u64, iv: &State) -> Digest {
    let (blocks, n) = split_input_into_blocks(input);
    compute_leaf(&blocks, n, pos, iv)
}

// ---- core::hash::Hasher 구현 ----

impl core::hash::Hasher for YHasher {
    fn write(&mut self, bytes: &[u8]) {
        self.update(bytes);
    }
    fn finish(&self) -> u64 {
        // core::hash::Hasher는 &self이므로 clone해서 finalize
        let cloned = self.clone();
        cloned.finalize_u64()
    }
}


#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn deterministic() {
        let builder = YHashBuilder::unkeyed();
        let mut h1 = builder.build_hasher();
        h1.update(b"hello");
        let d1 = h1.finalize();

        let mut h2 = builder.build_hasher();
        h2.update(b"hello");
        let d2 = h2.finalize();

        assert_eq!(d1, d2);
    }

    #[test]
    fn distinct_input() {
        let builder = YHashBuilder::unkeyed();
        let mut h1 = builder.build_hasher();
        h1.update(b"hello");
        let mut h2 = builder.build_hasher();
        h2.update(b"world");
        assert_ne!(h1.finalize(), h2.finalize());
    }

    #[test]
    fn keyed_vs_unkeyed() {
        let mut h1 = YHashBuilder::unkeyed().build_hasher();
        h1.update(b"data");
        let mut h2 = YHashBuilder::keyed(b"secret").build_hasher();
        h2.update(b"data");
        assert_ne!(h1.finalize(), h2.finalize());
    }

    #[test]
    fn keyed_distinct_keys() {
        let mut h1 = YHashBuilder::keyed(b"key1").build_hasher();
        h1.update(b"data");
        let mut h2 = YHashBuilder::keyed(b"key2").build_hasher();
        h2.update(b"data");
        assert_ne!(h1.finalize(), h2.finalize());
    }

    #[test]
    fn incremental_matches_oneshot() {
        let builder = YHashBuilder::unkeyed();
        let mut h1 = builder.build_hasher();
        h1.update(b"hello world");
        let d1 = h1.finalize();

        let mut h2 = builder.build_hasher();
        h2.update(b"hello ");
        h2.update(b"world");
        let d2 = h2.finalize();

        assert_eq!(d1, d2);
    }
}
