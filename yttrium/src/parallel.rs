//! 병렬 해시 — Spawner 기반 divide-and-conquer (`feature = "alloc"`; 실제 MT는 "parallel").
//!
//! 입력 전체가 주어진 경우 leaf·부분트리를 병렬 계산. 스트리밍 API는 직렬.
//! TreeBuilder의 binary-counter 트리 형태를 동일 복제 → 직렬 결과와 **bit-exact**.
//! leaf 계산은 `compute_leaf`(feature="simd"면 block-batch SIMD)라 **SIMD와 조합**된다.

use crate::spawner::Spawner;
use crate::{
    compute_internal, compute_leaf, compute_root_from_acc, cv_to_state, split_input_into_blocks,
    BLOCK_BYTES, Digest, Rounds, State, YttriumBuilder, T_MAX,
};
use alloc::vec::Vec;

const PARALLEL_LEAF_THRESHOLD: usize = 8;
const PARALLEL_TREE_THRESHOLD: usize = 8;

/// 병렬 해시 (입력 전체). `SerialSpawner`면 직렬과 동일 결과.
pub fn hash_parallel<S: Spawner + Sync>(builder: &YttriumBuilder, data: &[u8], spawner: &S) -> Digest {
    let (iv, rd) = builder.parts();
    let total_len = data.len() as u64;
    let leaf_size = T_MAX * BLOCK_BYTES;
    // single-leaf fast path (스트리밍은 leaf_size서 flush → strict <)
    if data.len() < leaf_size {
        let leaf = full_leaf(data, 0, iv, rd);
        return compute_root_from_acc(&cv_to_state(&leaf), total_len, 0, iv, rd);
    }
    let nleaves = data.len().div_ceil(leaf_size);
    let digests = par_leaves(data, leaf_size, 0, nleaves, iv, rd, spawner);
    build_root(&digests, total_len, iv, rd, spawner)
}

fn build_root<S: Spawner + Sync>(digests: &[Digest], total_len: u64, iv: &State, rd: &Rounds, spawner: &S) -> Digest {
    let n = digests.len();
    debug_assert!(n >= 1);
    let mut by_level: [Option<Digest>; 64] = [None; 64];
    let mut start = 0usize;
    for level in (0..64u32).rev() {
        if n & (1usize << level) != 0 {
            by_level[level as usize] = Some(perfect_subtree(digests, start, level, iv, rd, spawner));
            start += 1usize << level;
        }
    }
    let mut current: Option<Digest> = None;
    for level in 0u32..64 {
        if let Some(p) = by_level[level as usize] {
            current = Some(match current {
                None => p,
                Some(c) => compute_internal(level + 1, (n as u64) >> (level + 1), &p, &c, iv, rd),
            });
        }
    }
    let d = current.expect("n >= 1");
    compute_root_from_acc(&cv_to_state(&d), total_len, 1, iv, rd)
}

fn perfect_subtree<S: Spawner + Sync>(digests: &[Digest], a: usize, level: u32, iv: &State, rd: &Rounds, spawner: &S) -> Digest {
    if level == 0 {
        return digests[a];
    }
    let half = 1usize << (level - 1);
    let (l, r) = if (1usize << level) >= PARALLEL_TREE_THRESHOLD {
        spawner.join(
            || perfect_subtree(digests, a, level - 1, iv, rd, spawner),
            || perfect_subtree(digests, a + half, level - 1, iv, rd, spawner),
        )
    } else {
        (
            perfect_subtree(digests, a, level - 1, iv, rd, spawner),
            perfect_subtree(digests, a + half, level - 1, iv, rd, spawner),
        )
    };
    compute_internal(level, (a as u64) >> level, &l, &r, iv, rd)
}

/// leaf-index `[pos, pos+count)`의 digest를 병렬 계산. data를 인덱스로 슬라이스(중간 Vec 불요).
fn par_leaves<S: Spawner + Sync>(
    data: &[u8], leaf_size: usize, pos: usize, count: usize, iv: &State, rd: &Rounds, spawner: &S,
) -> Vec<Digest> {
    if count <= PARALLEL_LEAF_THRESHOLD {
        return (0..count)
            .map(|i| {
                let li = pos + i;
                let lo = li * leaf_size;
                let hi = core::cmp::min(lo + leaf_size, data.len());
                full_leaf(&data[lo..hi], li as u64, iv, rd)
            })
            .collect();
    }
    let mid = count / 2;
    let (mut lv, rv) = spawner.join(
        || par_leaves(data, leaf_size, pos, mid, iv, rd, spawner),
        || par_leaves(data, leaf_size, pos + mid, count - mid, iv, rd, spawner),
    );
    lv.extend(rv);
    lv
}

#[inline]
fn full_leaf(input: &[u8], pos: u64, iv: &State, rd: &Rounds) -> Digest {
    let (blocks, n) = split_input_into_blocks(input);
    compute_leaf(&blocks, n, pos, iv, rd)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::spawner::SerialSpawner;

    #[test]
    fn parallel_matches_sequential() {
        let b = YttriumBuilder::unkeyed(Rounds::V8_12_24);
        let leaf = T_MAX * BLOCK_BYTES;
        for &len in &[0usize, 11, leaf - 1, leaf, leaf * 2, leaf * 8, leaf * 16 + 37, 32 * 1024] {
            let data: Vec<u8> = (0..len).map(|i| (i * 7 + 3) as u8).collect();
            let seq = b.hash(&data); // one-shot 직렬
            let par = hash_parallel(&b, &data, &SerialSpawner);
            assert_eq!(seq, par, "len={len}");
        }
    }

    /// 트리 형태 동일성: leaf 1..=40 + 비정렬 꼬리.
    #[test]
    fn tree_shape_all_counts() {
        let b = YttriumBuilder::unkeyed(Rounds::V8_12_24);
        let leaf = T_MAX * BLOCK_BYTES;
        for nl in 1..=40usize {
            for tail in [1usize, 17, leaf / 2] {
                let len = (nl - 1) * leaf + tail.min(leaf);
                let data: Vec<u8> = (0..len).map(|i| (i * 13 + 5) as u8).collect();
                assert_eq!(b.hash(&data), hash_parallel(&b, &data, &SerialSpawner), "nl={nl} tail={tail}");
            }
        }
    }

    #[cfg(feature = "parallel")]
    #[test]
    fn std_thread_matches() {
        use crate::spawner::StdThreadSpawner;
        let b = YttriumBuilder::unkeyed(Rounds::V8_12_24);
        let data = alloc::vec![0x42u8; 64 * 1024];
        assert_eq!(b.hash(&data), hash_parallel(&b, &data, &StdThreadSpawner::new()));
    }
}
