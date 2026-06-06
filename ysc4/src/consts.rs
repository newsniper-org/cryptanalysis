//! YSC3 v0.2 상수.

/// 상태 워드 수.
pub const STATE_WORDS: usize = 16;
/// 상태 바이트 수.
pub const STATE_BYTES: usize = STATE_WORDS * 8;

/// 라운드 상수. v0.1과 동일 — √p (p = 소수)에서 추출.
pub const RC: [u64; 16] = [
    0x6A09E667F3BCC908, 0xBB67AE8584CAA73B, 0x3C6EF372FE94F82B, 0xA54FF53A5F1D36F1,
    0x510E527FADE682D1, 0x9B05688C2B3E6C1F, 0x1F83D9ABFB41BD6B, 0x5BE0CD19137E2179,
    0xCBBB9D5DC1059ED8, 0x629A292A367CD507, 0x9159015A3070DD17, 0x152FECD8F70E5939,
    0x67332667FFC00B31, 0x8EB44A8768581511, 0xDB0C2E0D64F98FA7, 0x47B5481DBEFA4FA4,
];

/// 워드 순열 `P[i] = (5i + 7) mod 16` — 단일 16-cycle.
pub const P: [usize; STATE_WORDS] = [
    7, 12, 1, 6, 11, 0, 5, 10, 15, 4, 9, 14, 3, 8, 13, 2,
];

/// F 함수의 회전 상수.
pub const F_ROT_A: u32 = 13;
/// F 함수의 회전 상수.
pub const F_ROT_B: u32 = 37;
/// F 함수의 회전 상수.
pub const F_ROT_C: u32 = 5;
/// F 함수의 회전 상수.
pub const F_ROT_D: u32 = 23;

/// 도메인 분리자 (v0.1과 동일).
pub mod domain {
    /// Stream cipher.
    pub const STREAM: u64 = u64::from_le_bytes(*b"YSC3-STM");
    /// AEAD.
    pub const AEAD: u64 = u64::from_le_bytes(*b"YSC3-AEA");
    /// AEAD AD.
    pub const AEAD_AD: u64 = u64::from_le_bytes(*b"YSC3-AD\0");
    /// AEAD CT.
    pub const AEAD_CT: u64 = u64::from_le_bytes(*b"YSC3-CT\0");
    /// AEAD TAG.
    pub const AEAD_TAG: u64 = u64::from_le_bytes(*b"YSC3-TAG");
    /// XOF.
    pub const XOF: u64 = u64::from_le_bytes(*b"YSC3-XOF");
    /// MAC.
    pub const MAC: u64 = u64::from_le_bytes(*b"YSC3-MAC");
}
