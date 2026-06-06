//! Farfalle 골격 — KeySetup, Compress, Transition, Expand. SPEC §6.
//!
//! 입력 블록 크기 = 상태 크기 = 128 바이트 (1024 비트). 출력 블록 크기 = rate (matches SPEC).
//! 압축은 *블록 누적*이므로 incremental 가능.

use crate::consts::{domain, STATE_WORDS};
use crate::roll::roll;
use ysc4::permutation::permute;
use zeroize::{Zeroize, ZeroizeOnDrop};

/// 매개변수 집합 (SPEC §4).
pub trait Ysc5Variant {
    /// 키 바이트 수.
    const KEY_BYTES: usize;
    /// 논스 바이트 수.
    const NONCE_BYTES: usize;
    /// 입력 블록 바이트 수 (= 상태 크기 = 128).
    const BLOCK_BYTES: usize = 128;
    /// 출력 rate 바이트 수.
    const RATE_BYTES: usize;
    /// 출력 rate 워드 수.
    const RATE_WORDS: usize;
    /// 압축 라운드 (p_b).
    const ROUNDS_B: usize;
    /// 초기 키 확장 라운드 (p_c).
    const ROUNDS_C: usize;
    /// 전이 라운드 (p_d).
    const ROUNDS_D: usize;
    /// 확장 라운드 (p_e).
    const ROUNDS_E: usize;
    /// AEAD 태그 바이트 수.
    const TAG_BYTES: usize;
}

/// 128-비트 보안 매개변수.
#[derive(Clone, Copy, Debug)]
pub struct Ysc5_128;
impl Ysc5Variant for Ysc5_128 {
    const KEY_BYTES: usize = 32;
    const NONCE_BYTES: usize = 24;
    const RATE_BYTES: usize = 64;
    const RATE_WORDS: usize = 8;
    const ROUNDS_B: usize = 12;
    const ROUNDS_C: usize = 24;
    const ROUNDS_D: usize = 8;
    const ROUNDS_E: usize = 12;
    const TAG_BYTES: usize = 16;
}

/// 256-비트 보안 매개변수.
#[derive(Clone, Copy, Debug)]
pub struct Ysc5_256;
impl Ysc5Variant for Ysc5_256 {
    const KEY_BYTES: usize = 64;
    const NONCE_BYTES: usize = 24;
    const RATE_BYTES: usize = 32;
    const RATE_WORDS: usize = 4;
    const ROUNDS_B: usize = 16;
    const ROUNDS_C: usize = 32;
    const ROUNDS_D: usize = 12;
    const ROUNDS_E: usize = 16;
    const TAG_BYTES: usize = 32;
}

/// 사용자 에러.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Error {
    /// 키 또는 논스 길이 불일치.
    BadKeyOrNonceLength,
    /// AEAD 인증 실패.
    AuthenticationFailed,
}

/// KeySetup: 키 → 마스크 시드. SPEC §6.2.
///
/// `state ← LoadKeyToCapacity(K) ⊕ DomainSep(STREAM, |K|); state ← p_c(state)`
pub fn key_setup<V: Ysc5Variant>(key: &[u8], domain_sep: u64) -> Result<[u64; STATE_WORDS], Error> {
    if key.len() != V::KEY_BYTES {
        return Err(Error::BadKeyOrNonceLength);
    }
    let mut state = [0u64; STATE_WORDS];

    // 키를 capacity 절반에 적재 (= state[RATE_WORDS..])
    let cap_start = V::RATE_WORDS;
    for (i, chunk) in key.chunks_exact(8).enumerate() {
        state[cap_start + i] = u64::from_le_bytes(chunk.try_into().unwrap());
    }

    // 도메인 + 길이 마커
    let domain_word = domain_sep
        ^ (V::KEY_BYTES as u64 * 8)
        ^ ((V::NONCE_BYTES as u64 * 8) << 32);
    state[STATE_WORDS - 1] ^= domain_word;

    // p_c 적용
    permute(&mut state, V::ROUNDS_C);
    Ok(state)
}

/// 입력 블록을 상태 크기 (= 128 byte = 16 워드)로 로드.
///
/// `block.len() <= 128`. 빈 곳은 0으로 채워짐 (multi-rate padding은 호출자가 처리).
fn load_block(block: &[u8]) -> [u64; STATE_WORDS] {
    debug_assert!(block.len() <= STATE_WORDS * 8);
    let mut out = [0u64; STATE_WORDS];
    for (i, chunk) in block.chunks(8).enumerate() {
        let mut buf = [0u8; 8];
        buf[..chunk.len()].copy_from_slice(chunk);
        out[i] = u64::from_le_bytes(buf);
    }
    out
}

/// Compress의 *incremental* 상태.
///
/// Farfalle의 핵심 장점: 압축은 결합법칙적 XOR-누적이므로 *블록 단위로 append* 가능.
#[derive(Clone, Zeroize, ZeroizeOnDrop)]
pub struct Compressor<V: Ysc5Variant> {
    /// 누적기 Y.
    accum: [u64; STATE_WORDS],
    /// 현재 mask = γ^(block_count)(seed).
    mask: [u64; STATE_WORDS],
    /// 처리한 블록 수.
    block_count: u64,
    /// seed 백업 (transition용).
    #[zeroize(skip)]
    _variant: core::marker::PhantomData<V>,
}

impl<V: Ysc5Variant> Compressor<V> {
    /// 새 압축기. `seed` = key_setup의 출력.
    pub fn new(seed: &[u64; STATE_WORDS]) -> Self {
        Self {
            accum: [0u64; STATE_WORDS],
            mask: *seed,
            block_count: 0,
            _variant: core::marker::PhantomData,
        }
    }

    /// 블록 하나 흡수. `block.len() == V::BLOCK_BYTES`.
    pub fn absorb_block(&mut self, block: &[u8]) {
        debug_assert_eq!(block.len(), V::BLOCK_BYTES);
        let m = load_block(block);

        // x = M_i ⊕ mask_i
        let mut x = [0u64; STATE_WORDS];
        for i in 0..STATE_WORDS {
            x[i] = m[i] ^ self.mask[i];
        }

        // x ← p_b(x)
        permute(&mut x, V::ROUNDS_B);

        // Y ⊕= x
        for i in 0..STATE_WORDS {
            self.accum[i] ^= x[i];
        }

        // mask ← γ(mask)
        roll(&mut self.mask);
        self.block_count = self.block_count.wrapping_add(1);
    }

    /// 임의 길이 데이터 흡수 (multi-rate padding 자동).
    pub fn absorb(&mut self, mut data: &[u8]) {
        let bsz = V::BLOCK_BYTES;
        while data.len() >= bsz {
            self.absorb_block(&data[..bsz]);
            data = &data[bsz..];
        }
        // 마지막 부분 블록 (padding 적용)
        let mut last = [0u8; 128];
        debug_assert!(bsz <= last.len());
        last[..data.len()].copy_from_slice(data);
        last[data.len()] = 0x01;
        last[bsz - 1] |= 0x80;
        self.absorb_block(&last[..bsz]);
    }

    /// 현재까지의 압축 결과 Y와 사용된 마지막 mask를 반환 (incremental clone용).
    pub fn snapshot(&self) -> ([u64; STATE_WORDS], [u64; STATE_WORDS], u64) {
        (self.accum, self.mask, self.block_count)
    }

    /// Y와 끝-mask를 소비. (transition으로 넘기기.)
    pub fn finish(self) -> ([u64; STATE_WORDS], [u64; STATE_WORDS]) {
        (self.accum, self.mask)
    }
}

/// Transition: Y → Y'. SPEC §6.4.
///
/// `Y' = p_d(Y) ⊕ end_mask ⊕ DOMAIN_EXPAND`
pub fn transition<V: Ysc5Variant>(
    y: &[u64; STATE_WORDS],
    end_mask: &[u64; STATE_WORDS],
) -> [u64; STATE_WORDS] {
    let mut y_prime = *y;
    permute(&mut y_prime, V::ROUNDS_D);
    for i in 0..STATE_WORDS {
        y_prime[i] ^= end_mask[i];
    }
    y_prime[STATE_WORDS - 1] ^= domain::EXPAND;
    y_prime
}

/// Expand의 *incremental* 상태. squeeze 호출 사이에 부분 블록 버퍼링.
#[derive(Clone, Zeroize, ZeroizeOnDrop)]
pub struct Expander<V: Ysc5Variant> {
    /// 현재 mask = γ^j(Y').
    mask: [u64; STATE_WORDS],
    /// 현재 사출 블록 (full rate). 처음에는 비어 있음.
    buf: [u8; 64],
    /// 다음 출력할 buf의 위치. `buf_pos == rate`이면 새 블록 squeeze 필요.
    buf_pos: usize,
    /// 처리한 블록 수 (j).
    block_idx: u64,
    #[zeroize(skip)]
    _variant: core::marker::PhantomData<V>,
}

impl<V: Ysc5Variant> Expander<V> {
    /// 새 확장기. `y_prime` = transition의 출력.
    pub fn new(y_prime: &[u64; STATE_WORDS]) -> Self {
        Self {
            mask: *y_prime,
            buf: [0u8; 64],
            buf_pos: V::RATE_BYTES, // 처음엔 비어 있어 첫 호출에 refresh 발생
            block_idx: 0,
            _variant: core::marker::PhantomData,
        }
    }

    /// 새 블록을 mask로부터 squeeze하여 buf에 채운다.
    fn refresh_buf(&mut self) {
        let mut z = self.mask;
        permute(&mut z, V::ROUNDS_E);
        for (i, chunk) in self.buf[..V::RATE_BYTES].chunks_exact_mut(8).enumerate() {
            chunk.copy_from_slice(&z[i].to_le_bytes());
        }
        roll(&mut self.mask);
        self.block_idx = self.block_idx.wrapping_add(1);
        self.buf_pos = 0;
        z.zeroize();
    }

    /// 완전한 블록 하나 squeeze. `out.len() == V::RATE_BYTES`.
    /// 호출 전에 buf가 정확히 align되어 있어야 함 (`buf_pos == 0` 또는 `== rate`).
    pub fn squeeze_block(&mut self, out: &mut [u8]) {
        debug_assert_eq!(out.len(), V::RATE_BYTES);
        debug_assert!(self.buf_pos == 0 || self.buf_pos == V::RATE_BYTES,
                      "squeeze_block은 block-aligned 상태에서만 호출");
        self.refresh_buf();
        out.copy_from_slice(&self.buf[..V::RATE_BYTES]);
        self.buf_pos = V::RATE_BYTES;
    }

    /// 임의 길이 출력. squeeze 호출 간에 부분 블록 보존.
    pub fn squeeze(&mut self, out: &mut [u8]) {
        let rate = V::RATE_BYTES;
        let mut offset = 0usize;
        while offset < out.len() {
            if self.buf_pos >= rate {
                self.refresh_buf();
            }
            let avail = rate - self.buf_pos;
            let take = core::cmp::min(avail, out.len() - offset);
            out[offset..offset + take]
                .copy_from_slice(&self.buf[self.buf_pos..self.buf_pos + take]);
            self.buf_pos += take;
            offset += take;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn key_setup_deterministic() {
        let k1 = key_setup::<Ysc5_128>(&[0x42; 32], domain::STREAM).unwrap();
        let k2 = key_setup::<Ysc5_128>(&[0x42; 32], domain::STREAM).unwrap();
        assert_eq!(k1, k2);
    }

    #[test]
    fn key_setup_different_keys_diverge() {
        let k1 = key_setup::<Ysc5_128>(&[0x42; 32], domain::STREAM).unwrap();
        let k2 = key_setup::<Ysc5_128>(&[0x43; 32], domain::STREAM).unwrap();
        assert_ne!(k1, k2);
    }

    #[test]
    fn key_setup_bad_length() {
        assert_eq!(
            key_setup::<Ysc5_128>(&[0u8; 31], domain::STREAM),
            Err(Error::BadKeyOrNonceLength)
        );
    }

    #[test]
    fn compress_expand_basic() {
        let seed = key_setup::<Ysc5_128>(&[0xAA; 32], domain::STREAM).unwrap();
        let mut c = Compressor::<Ysc5_128>::new(&seed);
        c.absorb(b"hello world");
        let (y, end_mask) = c.finish();
        let y_prime = transition::<Ysc5_128>(&y, &end_mask);
        let mut e = Expander::<Ysc5_128>::new(&y_prime);
        let mut out = [0u8; 128];
        e.squeeze(&mut out);
        // 출력이 0이 아니고 패턴 없음
        assert!(out.iter().any(|&b| b != 0));
    }
}
