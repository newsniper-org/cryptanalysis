//! Tree-mode YHash (큰 입력). SPEC §4.2, §4.3.
//!
//! Internal 노드: 2 children digest를 mask하여 합성.
//! Root: 길이 + tree shape를 maskMid에 인코딩.
//!
//! 모든 buffer는 fixed-size, no-heap.

use crate::consts::{rounds, LevelTag, BLOCK_BYTES, MAX_TREE_DEPTH, STATE_WORDS};
use crate::encode::{encode, mask_mid, root_mask_mid};
use crate::perm::{compress_block, cv_to_state, derive_mask, finalize, truncate_cv, State};

/// Internal 노드 계산: 2 children digest 합성. SPEC §4.2.
///
/// `Acc = P(d_L ⊕ mask(l,pos,0), R_int) ⊕ P(d_R ⊕ mask(l,pos,1), R_int)`
/// `digest = trunc(P(Acc ⊕ maskMid(l,pos), R_c))`.
pub fn compute_internal(
    level: u32,
    pos: u64,
    d_l: &[u8; 32],
    d_r: &[u8; 32],
    iv: &State,
) -> [u8; 32] {
    // d_L, d_R을 각각 state로 변환 (rate=32-byte 사용, 나머지 0)
    let block_l = pad_cv_to_block(d_l);
    let block_r = pad_cv_to_block(d_r);

    let seed_l = encode(LevelTag::Internal(level), pos, 0);
    let seed_r = encode(LevelTag::Internal(level), pos, 1);
    let mask_l = derive_mask(&seed_l, iv);
    let mask_r = derive_mask(&seed_r, iv);

    let y_l = compress_block(&block_l, &mask_l, rounds::INTERNAL);
    let y_r = compress_block(&block_r, &mask_r, rounds::INTERNAL);

    let mut acc = [0u64; STATE_WORDS];
    for i in 0..STATE_WORDS {
        acc[i] = y_l[i] ^ y_r[i];
    }

    let mm_seed = mask_mid(LevelTag::Internal(level), pos);
    let mm = derive_mask(&mm_seed, iv);
    let final_state = finalize(&acc, &mm);
    truncate_cv(&final_state)
}

/// Root 노드 계산. SPEC §4.3.
///
/// `Acc = (internal compression of root children)`
/// `digest = trunc(P(Acc ⊕ rootMaskMid(len, shape), R_c))`.
///
/// Single-leaf 경우 (children 없음): `Acc = leaf_digest as state`.
pub fn compute_root_from_acc(acc: &State, total_len: u64, shape_hash: u32, iv: &State) -> [u8; 32] {
    let mm_seed = root_mask_mid(total_len, shape_hash);
    let mm = derive_mask(&mm_seed, iv);
    let final_state = finalize(acc, &mm);
    truncate_cv(&final_state)
}

/// Root digest를 single-leaf 경우로부터.
pub fn root_from_single_leaf(leaf_digest: &[u8; 32], total_len: u64, iv: &State) -> [u8; 32] {
    // shape_hash = 0 (single leaf 표시)
    let acc = cv_to_state(leaf_digest);
    compute_root_from_acc(&acc, total_len, 0, iv)
}

/// 32-byte CV를 128-byte block으로 패딩 (앞 32 byte = CV, 나머지 = 0, 단 마지막에 0x80 마커).
#[inline]
fn pad_cv_to_block(cv: &[u8; 32]) -> [u8; BLOCK_BYTES] {
    let mut block = [0u8; BLOCK_BYTES];
    block[..32].copy_from_slice(cv);
    block[32] = 0x01; // 도메인 분리 마커
    block[BLOCK_BYTES - 1] |= 0x80;
    block
}

/// Stack-only tree-builder state.
///
/// 이진 트리의 *왼쪽 spine*만 유지하면 충분 — 새 leaf 도착 시 같은 레벨의
/// pending left와 합쳐 internal node를 만들고 위로 올라간다.
#[derive(Clone, Debug)]
pub struct TreeBuilder {
    /// `pending[l]`이 Some → level `l`에 보류된 left digest.
    pending: [Option<[u8; 32]>; MAX_TREE_DEPTH],
    /// 다음 leaf의 position.
    next_leaf_pos: u64,
}

impl TreeBuilder {
    /// 다음 leaf의 position을 외부에서 조회.
    #[inline]
    pub fn next_leaf_pos(&self) -> u64 {
        self.next_leaf_pos
    }
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
    /// 새 빌더.
    pub fn new() -> Self {
        Self::default()
    }

    /// 새 leaf digest를 트리에 추가. 같은 레벨의 pending과 합쳐 위로 carry-up.
    pub fn push_leaf(&mut self, leaf_digest: [u8; 32], iv: &State) {
        let mut digest = leaf_digest;
        let mut level: u32 = 0;
        loop {
            let lvl_idx = level as usize;
            debug_assert!(lvl_idx < MAX_TREE_DEPTH, "tree depth exceeded");
            match self.pending[lvl_idx].take() {
                None => {
                    self.pending[lvl_idx] = Some(digest);
                    break;
                }
                Some(left) => {
                    // 합성: position은 이전 결과
                    let pos = self.next_leaf_pos >> (level + 1);
                    let new_level = level + 1;
                    digest = compute_internal(new_level, pos, &left, &digest, iv);
                    level = new_level;
                }
            }
        }
        self.next_leaf_pos += 1;
    }

    /// 최종 root digest. 남은 pending들을 우측으로 비대칭 합성.
    pub fn finalize(mut self, total_len: u64, iv: &State) -> [u8; 32] {
        // 비대칭 트리: 우측에서 좌측으로 collapse
        let mut current: Option<[u8; 32]> = None;
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
                // Root finalize: encode length
                let acc = cv_to_state(&d);
                compute_root_from_acc(&acc, total_len, 1 /* shape: tree */, iv)
            }
            None => {
                // empty input — never happens in practice (leaf always pushed)
                let acc = [0u64; STATE_WORDS];
                compute_root_from_acc(&acc, 0, 0, iv)
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::consts::domain;

    fn dummy_iv() -> State {
        let mut s = [0u64; STATE_WORDS];
        s[15] = domain::UNKEYED;
        ysc4::permutation::permute(&mut s, rounds::MASK_DERIVE);
        s
    }

    #[test]
    fn internal_deterministic() {
        let iv = dummy_iv();
        let d_l = [0xAA; 32];
        let d_r = [0xBB; 32];
        let a = compute_internal(1, 0, &d_l, &d_r, &iv);
        let b = compute_internal(1, 0, &d_l, &d_r, &iv);
        assert_eq!(a, b);
    }

    #[test]
    fn internal_asymmetric() {
        let iv = dummy_iv();
        let d_l = [0xAA; 32];
        let d_r = [0xBB; 32];
        // (d_L, d_R)과 (d_R, d_L) 순서가 다른 결과 — Sakura ordering
        assert_ne!(
            compute_internal(1, 0, &d_l, &d_r, &iv),
            compute_internal(1, 0, &d_r, &d_l, &iv)
        );
    }
}
