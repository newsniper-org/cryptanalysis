//! YSC3 상수. 사양 §1을 1:1로 옮긴다.

/// 상태 워드 수 (16 × `u64` = 1024비트).
pub const STATE_WORDS: usize = 16;
/// 상태 바이트 수.
pub const STATE_BYTES: usize = STATE_WORDS * 8;

/// QR 회전 상수. NORX64에서 차용.
pub const R0: u32 = 8;
/// QR 회전 상수.
pub const R1: u32 = 19;
/// QR 회전 상수.
pub const R2: u32 = 40;
/// QR 회전 상수.
pub const R3: u32 = 63;

/// 라운드 상수. ⌊2^64 · {√pᵣ}⌋, `pᵣ = r`번째 소수.
/// SHA-256/SHA-512 IV와 동일 출처 (`nothing-up-my-sleeve`).
pub const RC: [u64; 16] = [
    0x6A09E667F3BCC908, // √2
    0xBB67AE8584CAA73B, // √3
    0x3C6EF372FE94F82B, // √5
    0xA54FF53A5F1D36F1, // √7
    0x510E527FADE682D1, // √11
    0x9B05688C2B3E6C1F, // √13
    0x1F83D9ABFB41BD6B, // √17
    0x5BE0CD19137E2179, // √19
    0xCBBB9D5DC1059ED8, // √23
    0x629A292A367CD507, // √29
    0x9159015A3070DD17, // √31
    0x152FECD8F70E5939, // √37
    0x67332667FFC00B31, // √41
    0x8EB44A8768581511, // √43
    0xDB0C2E0D64F98FA7, // √47
    0x47B5481DBEFA4FA4, // √53
];

/// 도메인 분리자 (8바이트 LE-u64). 사양 §1.5.
pub mod domain {
    /// Stream cipher 키스트림.
    pub const STREAM: u64 = u64::from_le_bytes(*b"YSC3-STM");
    /// AEAD.
    pub const AEAD: u64 = u64::from_le_bytes(*b"YSC3-AEA");
    /// AEAD 흡수 단계: AD.
    pub const AEAD_AD: u64 = u64::from_le_bytes(*b"YSC3-AD\0");
    /// AEAD 흡수 단계: CT.
    pub const AEAD_CT: u64 = u64::from_le_bytes(*b"YSC3-CT\0");
    /// AEAD 최종 태그.
    pub const AEAD_TAG: u64 = u64::from_le_bytes(*b"YSC3-TAG");
    /// Hash/XOF.
    pub const XOF: u64 = u64::from_le_bytes(*b"YSC3-XOF");
    /// MAC.
    pub const MAC: u64 = u64::from_le_bytes(*b"YSC3-MAC");
}
