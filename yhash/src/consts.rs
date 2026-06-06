//! YHash 상수. SPEC §1.

/// 상태 워드 수 (= ysc4 상태).
pub const STATE_WORDS: usize = 16;
/// 상태 바이트 수 = 128 (1024 비트).
pub const STATE_BYTES: usize = STATE_WORDS * 8;

/// 블록 바이트 수 = state size (Farfalle 표준).
pub const BLOCK_BYTES: usize = STATE_BYTES;
/// 블록 워드 수.
pub const BLOCK_WORDS: usize = STATE_WORDS;

/// Chaining value (truncated digest) 바이트 수 = 32 (256 비트).
pub const CV_BYTES: usize = 32;
/// CV 워드 수.
pub const CV_WORDS: usize = CV_BYTES / 8;

/// Leaf 노드의 최대 블록 수.
pub const T_MAX: usize = 8;

/// Single-leaf fast path의 입력 한계 = T_MAX × BLOCK_BYTES.
pub const SINGLE_LEAF_LIMIT: usize = T_MAX * BLOCK_BYTES;

/// 트리 깊이 한계 (fixed-size buffer). 1 GB input ≤ 22 레벨.
pub const MAX_TREE_DEPTH: usize = 32;

/// 라운드 수.
pub mod rounds {
    /// Leaf 블록 압축.
    pub const LEAF: usize = 8;
    /// Internal 노드 압축.
    pub const INTERNAL: usize = 8;
    /// Leaf finalize / root finalize.
    pub const FINALIZE: usize = 12;
    /// Mask seed derivation (1회용, init).
    pub const MASK_DERIVE: usize = 24;
}

/// 도메인 분리자 (8바이트 LE-u64, SPEC §2).
pub mod domain {
    /// keyed-mode IV 도메인.
    pub const KEYED: u64 = u64::from_le_bytes(*b"YHash-K\0");
    /// unkeyed-mode IV 도메인.
    pub const UNKEYED: u64 = u64::from_le_bytes(*b"YHash-U\0");
}

/// Level tag (encode 함수 입력, SPEC §2).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LevelTag {
    /// Leaf node.
    Leaf,
    /// Internal node at level `l` (≥ 1).
    Internal(u32),
    /// Root node.
    Root,
}

impl LevelTag {
    /// 도메인 분리 byte (Sakura coding).
    #[inline]
    pub fn byte(self) -> u8 {
        match self {
            LevelTag::Leaf => 0x00,
            LevelTag::Internal(_) => 0x01,
            LevelTag::Root => 0xFF,
        }
    }

    /// Internal level (`l`), Leaf/Root에 대해서는 0.
    #[inline]
    pub fn level(self) -> u32 {
        match self {
            LevelTag::Internal(l) => l,
            _ => 0,
        }
    }
}
