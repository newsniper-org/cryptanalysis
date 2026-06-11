//! 병렬 해시 — Spawner 기반 divide-and-conquer.
//!
//! 입력 전체가 한 번에 주어진 경우 leaf 단위로 병렬 계산.
//! streaming `update`/`finalize` API는 직렬 유지.

use crate::consts::{BLOCK_BYTES, T_MAX};
use crate::hasher::{Digest, YHashBuilder};
use crate::leaf::{compute_leaf, split_input_into_blocks};
use crate::perm::{cv_to_state, State};
use crate::spawner::Spawner;
use crate::tree::{compute_internal, compute_root_from_acc, root_from_single_leaf};
use alloc::vec::Vec;

/// 임계값 — 이보다 작은 leaf 수는 직렬로. 8 leaves = 8 KiB 입력.
const PARALLEL_LEAF_THRESHOLD: usize = 8;

/// 트리 빌드에서 spawn 임계값 (이 leaf 수 이상의 부분트리만 병렬).
const PARALLEL_TREE_THRESHOLD: usize = 8;

/// 병렬 해시 — 입력 전체가 주어진 경우.
///
/// `spawner`가 `SerialSpawner`면 직렬 실행과 동일 결과 (streaming API와도 일치).
pub fn hash_parallel<S: Spawner + Sync>(
    builder: &YHashBuilder,
    data: &[u8],
    spawner: &S,
) -> Digest {
    let iv = builder.iv_ref();
    let total_len = data.len() as u64;

    // Single-leaf fast path — leaf_size 미만이면 tree 모드에 들어가지 않음.
    // 정확히 leaf_size면 streaming update가 tree 모드로 전환하므로 동일하게 처리.
    let leaf_size = T_MAX * BLOCK_BYTES;
    if data.len() < leaf_size {
        let leaf_digest = compute_full_leaf(data, 0, iv);
        return root_from_single_leaf(&leaf_digest, total_len, iv);
    }

    // Split into leaves
    let leaves: Vec<&[u8]> = data.chunks(leaf_size).collect();
    let leaf_digests = parallel_compute_leaves(&leaves, 0, iv, spawner);

    // Build tree in parallel (TreeBuilder의 binary-counter 형태를 동일 복제).
    build_root(&leaf_digests, total_len, iv, spawner)
}

/// 리프 digest들로부터 root를 병렬로 빌드. `TreeBuilder::push_leaf`+`finalize`와
/// 동일한 트리 형태(=동일 (level,pos) 인자)를 재귀로 복제하므로 결과가 일치한다.
fn build_root<S: Spawner + Sync>(
    digests: &[[u8; 32]],
    total_len: u64,
    iv: &State,
    spawner: &S,
) -> Digest {
    let n = digests.len();
    debug_assert!(n >= 1);

    // set bit(level)마다 완전 부분트리 digest. leaf 블록은 high→low로 배치.
    let mut by_level: [Option<[u8; 32]>; 64] = [None; 64];
    let mut start = 0usize;
    for level in (0..64u32).rev() {
        if n & (1usize << level) != 0 {
            by_level[level as usize] = Some(perfect_subtree(digests, start, level, iv, spawner));
            start += 1usize << level;
        }
    }

    // finalize와 동일하게 low→high fold (상위 블록이 LEFT, 누적이 RIGHT).
    let mut current: Option<[u8; 32]> = None;
    for level in 0u32..64 {
        if let Some(p) = by_level[level as usize] {
            current = Some(match current {
                None => p,
                Some(c) => compute_internal(level + 1, (n as u64) >> (level + 1), &p, &c, iv),
            });
        }
    }
    let d = current.expect("n >= 1");
    let acc = cv_to_state(&d);
    compute_root_from_acc(&acc, total_len, 1, iv)
}

/// 리프 `[a, a+2^level)` (a는 2^level 배수)를 덮는 완전 이진 부분트리 digest.
/// push_leaf가 만드는 노드와 동일하게 `compute_internal(level, a>>level, …)`.
fn perfect_subtree<S: Spawner + Sync>(
    digests: &[[u8; 32]],
    a: usize,
    level: u32,
    iv: &State,
    spawner: &S,
) -> [u8; 32] {
    if level == 0 {
        return digests[a];
    }
    let half = 1usize << (level - 1);
    let (l, r) = if (1usize << level) >= PARALLEL_TREE_THRESHOLD {
        spawner.join(
            || perfect_subtree(digests, a, level - 1, iv, spawner),
            || perfect_subtree(digests, a + half, level - 1, iv, spawner),
        )
    } else {
        (
            perfect_subtree(digests, a, level - 1, iv, spawner),
            perfect_subtree(digests, a + half, level - 1, iv, spawner),
        )
    };
    compute_internal(level, (a as u64) >> level, &l, &r, iv)
}

fn parallel_compute_leaves<S: Spawner + Sync>(
    leaves: &[&[u8]],
    pos_offset: u64,
    iv: &State,
    spawner: &S,
) -> Vec<[u8; 32]> {
    if leaves.len() <= PARALLEL_LEAF_THRESHOLD {
        return leaves
            .iter()
            .enumerate()
            .map(|(i, l)| compute_full_leaf(l, pos_offset + i as u64, iv))
            .collect();
    }
    let mid = leaves.len() / 2;
    let (left, right) = leaves.split_at(mid);
    let (mut lv, rv) = spawner.join(
        || parallel_compute_leaves(left, pos_offset, iv, spawner),
        || parallel_compute_leaves(right, pos_offset + mid as u64, iv, spawner),
    );
    lv.extend(rv);
    lv
}

fn compute_full_leaf(input: &[u8], pos: u64, iv: &State) -> [u8; 32] {
    let (blocks, n) = split_input_into_blocks(input);
    compute_leaf(&blocks, n, pos, iv)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::spawner::SerialSpawner;
    use alloc::vec;

    #[test]
    fn parallel_serial_matches_sequential() {
        let builder = YHashBuilder::unkeyed();
        let inputs: &[&[u8]] = &[
            b"",
            b"hello world",
            &[0u8; 1024][..],          // exactly 1 leaf
            &[0xAAu8; 2048][..],       // 2 leaves
            &[0x55u8; 8192][..],       // 8 leaves
            &[0xFFu8; 16384][..],      // 16 leaves
            &[0x33u8; 128 * 1024][..], // 128 leaves
        ];
        for data in inputs {
            let mut h = builder.build_hasher();
            h.update(data);
            let seq = h.finalize();
            let par = hash_parallel(&builder, data, &SerialSpawner);
            assert_eq!(seq, par, "len={}", data.len());
        }
    }

    /// 트리 형태 동일성: leaf 수 1..=40 + 비정렬 꼬리까지 전수 검증.
    #[test]
    fn parallel_tree_shape_all_leaf_counts() {
        let builder = YHashBuilder::unkeyed();
        let leaf_size = T_MAX * BLOCK_BYTES;
        for n_leaves in 1..=40usize {
            for tail in [0usize, 1, 17, leaf_size / 2] {
                let len = (n_leaves - 1) * leaf_size + leaf_size.min(tail.max(1)) + tail;
                let data: alloc::vec::Vec<u8> = (0..len).map(|i| (i * 7 + 3) as u8).collect();
                let mut h = builder.build_hasher();
                h.update(&data);
                let seq = h.finalize();
                let par = hash_parallel(&builder, &data, &SerialSpawner);
                assert_eq!(seq, par, "n_leaves={} tail={} len={}", n_leaves, tail, len);
            }
        }
    }

    #[cfg(feature = "std-thread")]
    #[test]
    fn parallel_std_thread_matches_sequential() {
        use crate::spawner::StdThreadSpawner;
        let builder = YHashBuilder::unkeyed();
        let data = vec![0x42u8; 256 * 1024];
        let mut h = builder.build_hasher();
        h.update(&data);
        let seq = h.finalize();
        let par = hash_parallel(&builder, &data, &StdThreadSpawner::new());
        assert_eq!(seq, par);
    }

    #[cfg(feature = "rayon")]
    #[test]
    fn parallel_rayon_matches_sequential() {
        use crate::spawner::RayonSpawner;
        let builder = YHashBuilder::unkeyed();
        let data = vec![0x99u8; 512 * 1024];
        let mut h = builder.build_hasher();
        h.update(&data);
        let seq = h.finalize();
        let par = hash_parallel(&builder, &data, &RayonSpawner);
        assert_eq!(seq, par);
    }
}
