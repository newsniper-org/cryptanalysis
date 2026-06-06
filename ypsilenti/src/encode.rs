//! Tree-position encoding (Y1' 형식 검증).
//!
//! Layout (16 byte):
//!   byte 0:    level_byte
//!   byte 1:    level_l_byte
//!   byte 2-3:  reserved (0)
//!   byte 4-11: pos (u64 LE)
//!   byte 12-15: idx (u32 LE)

use crate::consts::LevelTag;

pub type MaskSeed = [u8; 16];

#[inline]
pub fn encode(level: LevelTag, pos: u64, idx: u32) -> MaskSeed {
    let mut out = [0u8; 16];
    out[0] = level.byte();
    out[1] = level.level() as u8;
    out[4..12].copy_from_slice(&pos.to_le_bytes());
    out[12..16].copy_from_slice(&idx.to_le_bytes());
    out
}

#[inline]
pub fn mask_mid(level: LevelTag, pos: u64) -> MaskSeed {
    encode(level, pos, crate::consts::T_MAX as u32)
}

#[inline]
pub fn root_mask_mid(total_len: u64, shape_hash: u32) -> MaskSeed {
    encode(LevelTag::Root, total_len, shape_hash)
}
