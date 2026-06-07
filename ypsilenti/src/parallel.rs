//! 병렬 해시 — Spawner 기반 divide-and-conquer.
//!
//! 입력 전체가 한 번에 주어진 경우 leaf 단위로 병렬 계산.
//! `streaming update/finalize` API는 직렬 유지.

use crate::consts::{BLOCK_BYTES, T_MAX};
use crate::hasher::{Digest, YpsiBuilder};
use crate::leaf::{compute_leaf, split_input_into_blocks};
use crate::perm::State;
use crate::spawner::Spawner;
use crate::tree::{root_from_single_leaf, TreeBuilder};
use alloc::vec::Vec;

/// 임계값 — 이보다 작은 leaf 수는 직렬로.
/// 8 leaves = 2 KiB 입력.
const PARALLEL_LEAF_THRESHOLD: usize = 8;

/// 병렬 해시 — 입력 전체가 주어진 경우.
///
/// `spawner`가 `SerialSpawner`면 직렬 실행과 동일 결과.
/// `Send + Sync` 가정: `iv: &State`는 Sync ([u32; 8]).
pub fn hash_parallel<S: Spawner + Sync>(
    builder: &YpsiBuilder,
    data: &[u8],
    spawner: &S,
) -> Digest {
    let iv = builder.iv_ref();
    let total_len = data.len() as u64;

    // Single-leaf fast path — leaf_size 미만이면 tree 모드에 들어가지 않음.
    // 정확히 leaf_size면 sequential update가 tree 모드로 전환하므로 동일하게 처리.
    let leaf_size = T_MAX * BLOCK_BYTES;
    if data.len() < leaf_size {
        let leaf_digest = compute_full_leaf(data, 0, iv);
        return root_from_single_leaf(&leaf_digest, total_len, iv);
    }

    // Split into leaves
    let leaves: Vec<&[u8]> = data.chunks(leaf_size).collect();
    let leaf_digests = parallel_compute_leaves(&leaves, 0, iv, spawner);

    // Build tree sequentially (TreeBuilder logic)
    let mut tree = TreeBuilder::new();
    for digest in leaf_digests {
        tree.push_leaf(digest, iv);
    }
    tree.finalize(total_len, iv)
}

fn parallel_compute_leaves<S: Spawner + Sync>(
    leaves: &[&[u8]],
    pos_offset: u64,
    iv: &State,
    spawner: &S,
) -> Vec<[u8; 16]> {
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

fn compute_full_leaf(input: &[u8], pos: u64, iv: &State) -> [u8; 16] {
    let (blocks, n) = split_input_into_blocks(input);
    compute_leaf(&blocks, n, pos, iv)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::spawner::SerialSpawner;

    #[test]
    fn parallel_serial_matches_sequential() {
        let builder = YpsiBuilder::unkeyed();
        let inputs: &[&[u8]] = &[
            b"",
            b"hello world",
            &[0u8; 256][..],          // exactly 1 leaf
            &[0xAAu8; 512][..],       // 2 leaves
            &[0x55u8; 2048][..],      // 8 leaves
            &[0xFFu8; 4096][..],      // 16 leaves
            &[0x33u8; 32 * 1024][..], // 128 leaves
        ];
        for data in inputs {
            let mut h = builder.build_hasher();
            h.update(data);
            let seq = h.finalize();
            let par = hash_parallel(&builder, data, &SerialSpawner);
            assert_eq!(seq, par, "len={}", data.len());
        }
    }

    #[cfg(feature = "std-thread")]
    #[test]
    fn parallel_std_thread_matches_sequential() {
        use crate::spawner::StdThreadSpawner;
        let builder = YpsiBuilder::unkeyed();
        let data = vec![0x42u8; 64 * 1024];
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
        let builder = YpsiBuilder::unkeyed();
        let data = vec![0x99u8; 128 * 1024];
        let mut h = builder.build_hasher();
        h.update(&data);
        let seq = h.finalize();
        let par = hash_parallel(&builder, &data, &RayonSpawner);
        assert_eq!(seq, par);
    }
}
