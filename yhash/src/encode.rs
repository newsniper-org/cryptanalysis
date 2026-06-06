//! Tree-position encoding. SPEC §2.
//!
//! Y1 (Isabelle): encode는 단사. 본 모듈은 그 단사성을 *구현 차원에서* 보장.
//!
//! Layout (16 byte):
//!   byte 0:    level_byte (0x00 LEAF / 0x01 INTERNAL / 0xFF ROOT)
//!   byte 1:    level_l_byte (internal 전용, level number)
//!   byte 2-3:  reserved (0)
//!   byte 4-11: pos (u64 LE)
//!   byte 12-15: idx (u32 LE)

use crate::consts::LevelTag;

/// Mask seed: 16 byte (= encode 결과).
pub type MaskSeed = [u8; 16];

/// SPEC §2 encode 함수.
#[inline]
pub fn encode(level: LevelTag, pos: u64, idx: u32) -> MaskSeed {
    let mut out = [0u8; 16];
    out[0] = level.byte();
    out[1] = level.level() as u8;
    // out[2..4] = 0
    out[4..12].copy_from_slice(&pos.to_le_bytes());
    out[12..16].copy_from_slice(&idx.to_le_bytes());
    out
}

/// maskMid: leaf/internal/root의 종결 mask seed.
///
/// Y3 (Isabelle): maskMid가 level tag로 도메인 분리됨을 형식 증명.
#[inline]
pub fn mask_mid(level: LevelTag, pos: u64) -> MaskSeed {
    encode(level, pos, crate::consts::T_MAX as u32)
}

/// Root의 maskMid는 길이와 트리 모양을 인코딩.
///
/// Sakura-style: root encoding이 길이 및 shape를 포함하지 않으면 second-preimage 공격 가능.
#[inline]
pub fn root_mask_mid(total_len: u64, shape_hash: u32) -> MaskSeed {
    let mut out = encode(LevelTag::Root, total_len, shape_hash);
    // 첫 byte는 0xFF (ROOT). 4..12에 length, 12..16에 shape_hash.
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn encode_distinct_levels() {
        let leaf = encode(LevelTag::Leaf, 0, 0);
        let internal = encode(LevelTag::Internal(1), 0, 0);
        let root = encode(LevelTag::Root, 0, 0);
        assert_ne!(leaf, internal);
        assert_ne!(leaf, root);
        assert_ne!(internal, root);
    }

    #[test]
    fn encode_distinct_positions() {
        let a = encode(LevelTag::Leaf, 0, 0);
        let b = encode(LevelTag::Leaf, 1, 0);
        let c = encode(LevelTag::Leaf, 0, 1);
        assert_ne!(a, b);
        assert_ne!(a, c);
        assert_ne!(b, c);
    }

    #[test]
    fn encode_internal_levels_distinct() {
        let l1 = encode(LevelTag::Internal(1), 0, 0);
        let l2 = encode(LevelTag::Internal(2), 0, 0);
        assert_ne!(l1, l2);
    }

    #[test]
    fn mask_mid_uses_t_max() {
        let mm = mask_mid(LevelTag::Leaf, 0);
        let m_first = encode(LevelTag::Leaf, 0, 0);
        let m_last = encode(LevelTag::Leaf, 0, (crate::consts::T_MAX - 1) as u32);
        // maskMid는 일반 블록 인덱스와 분리 (idx = T_MAX)
        assert_ne!(mm, m_first);
        assert_ne!(mm, m_last);
    }
}
