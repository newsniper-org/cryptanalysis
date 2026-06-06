//! YSC5 도메인 분리자 및 상수. SPEC §8.

/// 상태 워드 수.
pub const STATE_WORDS: usize = 16;
/// 상태 바이트 수.
pub const STATE_BYTES: usize = STATE_WORDS * 8;

/// 도메인 분리자 (8바이트 LE-u64).
pub mod domain {
    /// Stream cipher 모드.
    pub const STREAM: u64 = u64::from_le_bytes(*b"YSC5-STM");
    /// AEAD 모드 (초기 키 setup).
    pub const AEAD: u64 = u64::from_le_bytes(*b"YSC5-AEA");
    /// AEAD 흡수 단계: AD.
    pub const AEAD_AD: u64 = u64::from_le_bytes(*b"YSC5-AD\0");
    /// AEAD 흡수 단계: CT.
    pub const AEAD_CT: u64 = u64::from_le_bytes(*b"YSC5-CT\0");
    /// AEAD 태그 도메인.
    pub const AEAD_TAG: u64 = u64::from_le_bytes(*b"YSC5-TAG");
    /// XOF.
    pub const XOF: u64 = u64::from_le_bytes(*b"YSC5-XOF");
    /// MAC.
    pub const MAC: u64 = u64::from_le_bytes(*b"YSC5-MAC");
    /// 압축 → 확장 전이 도메인.
    pub const EXPAND: u64 = u64::from_le_bytes(*b"YSC5-EXP");
}
