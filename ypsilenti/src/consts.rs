//! ypsilenti 상수. SPEC §1, §5.

pub const STATE_WORDS: usize = 8;
pub const STATE_BYTES: usize = STATE_WORDS * 4;  // 32

pub const BLOCK_BYTES: usize = STATE_BYTES;
pub const CV_BYTES: usize = 16;  // 128-bit chaining value

pub const T_MAX: usize = 8;
pub const MAX_TREE_DEPTH: usize = 32;

/// F 회전 상수 (u32 friendly).
pub const F_ROT_A: u32 = 7;
pub const F_ROT_B: u32 = 17;
pub const F_ROT_C: u32 = 3;
pub const F_ROT_D: u32 = 13;

/// 워드 순열 P[i] = (5i + 7) mod 8.
pub const P_PI: [usize; STATE_WORDS] = [7, 4, 1, 6, 3, 0, 5, 2];

/// 라운드 상수. SHA-256 IV의 처음 8개 word를 NUMS 차용.
pub const RC: [u32; STATE_WORDS] = [
    0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A,
    0x510E527F, 0x9B05688C, 0x1F83D9AB, 0x5BE0CD19,
];

pub mod rounds {
    pub const LEAF: usize = 4;
    pub const INTERNAL: usize = 4;
    pub const FINALIZE: usize = 6;
    pub const MASK_DERIVE: usize = 8;
}

pub mod domain {
    pub const KEYED: u64 = u64::from_le_bytes(*b"YPSI-K\0\0");
    pub const UNKEYED: u64 = u64::from_le_bytes(*b"YPSI-U\0\0");
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LevelTag {
    Leaf,
    Internal(u32),
    Root,
}

impl LevelTag {
    #[inline]
    pub fn byte(self) -> u8 {
        match self {
            LevelTag::Leaf => 0x00,
            LevelTag::Internal(_) => 0x01,
            LevelTag::Root => 0xFF,
        }
    }
    #[inline]
    pub fn level(self) -> u32 {
        match self {
            LevelTag::Internal(l) => l,
            _ => 0,
        }
    }
}
