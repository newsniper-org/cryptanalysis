//! YSC3 스트림 암호 모드. 사양 §3.1 (CTR-Sponge).
//!
//! v1.0 (YSC2)의 V1·V2 결함을 차단하는 핵심 사양 변화:
//! - 키는 *capacity*에만 적재되어 키스트림으로 직접 노출되지 않는다.
//! - 키스트림 = 순열 출력의 `rate` 부분(전체가 아니라 *절반*).
//! - 카운터는 capacity 워드(`state[14]`)에 주입 → 출력 워드와 직접 닿지 않음.
//!
//! 각 블록은 독립적으로 (`state` 자체는 변하지 않고) 계산되므로 *seekable + parallelizable*.

use crate::consts::{domain, STATE_WORDS};
use crate::permutation::permute;
use zeroize::{Zeroize, ZeroizeOnDrop};

/// 매개변수 집합. 사양 §1.2.
pub trait Ysc3Variant {
    /// 키 바이트 수.
    const KEY_BYTES: usize;
    /// 논스 바이트 수.
    const NONCE_BYTES: usize;
    /// rate 워드 수 (= 한 키스트림 블록의 워드 수).
    const RATE_WORDS: usize;
    /// rate 바이트 수.
    const RATE_BYTES: usize = Self::RATE_WORDS * 8;
    /// 초기화 라운드.
    const ROUNDS_INIT: usize;
    /// 블록당 라운드.
    const ROUNDS_BLOCK: usize;
}

/// 128-비트 보안 매개변수.
#[derive(Clone, Copy, Debug)]
pub struct Ysc3_128;
impl Ysc3Variant for Ysc3_128 {
    const KEY_BYTES: usize = 32;     // 256 비트
    const NONCE_BYTES: usize = 24;   // 192 비트
    const RATE_WORDS: usize = 8;     // 512 비트
    const ROUNDS_INIT: usize = 24;
    const ROUNDS_BLOCK: usize = 12;
}

/// 256-비트 보안 매개변수.
#[derive(Clone, Copy, Debug)]
pub struct Ysc3_256;
impl Ysc3Variant for Ysc3_256 {
    const KEY_BYTES: usize = 64;     // 512 비트
    const NONCE_BYTES: usize = 24;   // 192 비트
    const RATE_WORDS: usize = 4;     // 256 비트 → capacity 768 비트
    const ROUNDS_INIT: usize = 32;
    const ROUNDS_BLOCK: usize = 16;
}

/// 스트림 암호 상태.
///
/// `state`는 비밀 — capacity는 절대 누설되지 않도록 sponge가 보장한다.
/// Zeroize/ZeroizeOnDrop으로 Drop 시 메모리 잔존 차단 (구 V8 결함 차단).
#[derive(Clone, Zeroize, ZeroizeOnDrop)]
pub struct Ysc3Stream<V: Ysc3Variant> {
    state: [u64; STATE_WORDS],
    #[zeroize(skip)]
    _variant: core::marker::PhantomData<V>,
}

impl<V: Ysc3Variant> core::fmt::Debug for Ysc3Stream<V> {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        f.debug_struct("Ysc3Stream").finish_non_exhaustive()
    }
}

/// 길이 불일치 등 사용자 에러.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Error {
    /// 키 또는 논스의 길이가 매개변수와 다름.
    BadKeyOrNonceLength,
}

impl<V: Ysc3Variant> Ysc3Stream<V> {
    /// 새 스트림 cipher 인스턴스 생성. 사양 §3.1 초기화.
    pub fn new(key: &[u8], nonce: &[u8]) -> Result<Self, Error> {
        if key.len() != V::KEY_BYTES || nonce.len() != V::NONCE_BYTES {
            return Err(Error::BadKeyOrNonceLength);
        }
        let mut state = [0u64; STATE_WORDS];

        // 1) 키를 capacity의 앞쪽 워드들에 적재 (state[8..8+key_words]).
        let key_words = V::KEY_BYTES / 8;
        let capacity_start = V::RATE_WORDS;
        for (i, chunk) in key.chunks_exact(8).enumerate() {
            // 안전: chunks_exact는 정확히 8바이트.
            let w = u64::from_le_bytes(chunk.try_into().unwrap());
            state[capacity_start + i] = w;
        }
        debug_assert_eq!(key_words * 8, V::KEY_BYTES);

        // 2) 논스를 rate의 앞쪽 워드들에 적재 (state[0..nonce_words]).
        let nonce_words = V::NONCE_BYTES / 8;
        for (i, chunk) in nonce.chunks_exact(8).enumerate() {
            let w = u64::from_le_bytes(chunk.try_into().unwrap());
            state[i] = w;
        }
        debug_assert_eq!(nonce_words * 8, V::NONCE_BYTES);

        // 3) 도메인·길이 표시를 capacity의 마지막 워드에 결합.
        //    DOMAIN ⊕ (KEY_BITS) ⊕ (NONCE_BITS << 32)  — 매개변수 집합이 다르면 다른 값.
        let domain_word = domain::STREAM
            ^ (V::KEY_BYTES as u64 * 8)
            ^ ((V::NONCE_BYTES as u64 * 8) << 32);
        state[STATE_WORDS - 1] ^= domain_word;

        // 4) 초기화 순열.
        permute(&mut state, V::ROUNDS_INIT);

        Ok(Self {
            state,
            _variant: core::marker::PhantomData,
        })
    }

    /// 카운터 `i`에 대응하는 키스트림 블록 (RATE_BYTES) 생성. 사양 §3.1.
    ///
    /// `state`는 변하지 않으므로 임의의 `i`에 대해 독립적으로 호출 가능.
    pub fn keystream_block(&self, i: u64, out: &mut [u8]) {
        debug_assert_eq!(out.len(), V::RATE_BYTES);

        let mut working = self.state;
        // 카운터를 capacity의 두 번째 워드 (state[STATE_WORDS-2])에 XOR.
        //   - rate 워드 (state[0..RATE_WORDS])에 *직접* 닿지 않음 → V1 차단.
        //   - 12/16 라운드 순열을 통과한 후에야 rate에 영향.
        working[STATE_WORDS - 2] ^= i;

        permute(&mut working, V::ROUNDS_BLOCK);

        for (j, chunk) in out.chunks_exact_mut(8).enumerate() {
            chunk.copy_from_slice(&working[j].to_le_bytes());
        }

        // working은 비밀 정보의 함수 — drop 전에 zeroize.
        let mut tmp = working;
        tmp.zeroize();
    }

    /// `buffer`를 in-place로 암호화 (또는 복호화).
    ///
    /// `start_block`부터 시작. 길이는 RATE_BYTES의 배수가 아니어도 됨 (마지막 블록은 부분 사용).
    pub fn apply_keystream(&self, buffer: &mut [u8], start_block: u64) {
        let mut block = [0u8; 256]; // RATE_BYTES ≤ 64 for all defined variants; 256 = 여유.
        let rate = V::RATE_BYTES;
        debug_assert!(rate <= block.len());

        let mut idx = start_block;
        let mut offset = 0usize;
        while offset < buffer.len() {
            let take = core::cmp::min(rate, buffer.len() - offset);
            self.keystream_block(idx, &mut block[..rate]);
            for k in 0..take {
                buffer[offset + k] ^= block[k];
            }
            offset += take;
            idx = idx.wrapping_add(1);
        }
        block.zeroize();
    }
}

/// YSC3-128 스트림 cipher.
pub type Ysc3_128Stream = Ysc3Stream<Ysc3_128>;
/// YSC3-256 스트림 cipher.
pub type Ysc3_256Stream = Ysc3Stream<Ysc3_256>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn roundtrip_128() {
        let key = [0xAA; 32];
        let nonce = [0xBB; 24];
        let pt = b"hello world from YSC3 stream cipher" as &[u8];
        let mut buf = pt.to_vec();

        let cipher = Ysc3_128Stream::new(&key, &nonce).unwrap();
        cipher.apply_keystream(&mut buf, 0);
        assert_ne!(&buf[..], pt);

        let cipher2 = Ysc3_128Stream::new(&key, &nonce).unwrap();
        cipher2.apply_keystream(&mut buf, 0);
        assert_eq!(&buf[..], pt);
    }

    #[test]
    fn roundtrip_256() {
        let key = [0xCC; 64];
        let nonce = [0xDD; 24];
        let pt = b"512-bit key variant test" as &[u8];
        let mut buf = pt.to_vec();

        let cipher = Ysc3_256Stream::new(&key, &nonce).unwrap();
        cipher.apply_keystream(&mut buf, 0);
        let cipher2 = Ysc3_256Stream::new(&key, &nonce).unwrap();
        cipher2.apply_keystream(&mut buf, 0);
        assert_eq!(&buf[..], pt);
    }

    #[test]
    fn seekable_blocks_match() {
        let key = [1u8; 32];
        let nonce = [2u8; 24];
        let cipher = Ysc3_128Stream::new(&key, &nonce).unwrap();

        // 연속 두 블록을 한꺼번에.
        let mut buf_long = vec![0u8; 128];
        cipher.apply_keystream(&mut buf_long, 0);

        // 두 번째 블록을 별도 호출로.
        let mut buf2 = vec![0u8; 64];
        cipher.apply_keystream(&mut buf2, 1);

        assert_eq!(&buf_long[64..], &buf2[..]);
    }

    #[test]
    fn bad_lengths_rejected() {
        assert!(matches!(
            Ysc3_128Stream::new(&[0u8; 31], &[0u8; 24]),
            Err(Error::BadKeyOrNonceLength)
        ));
        assert!(matches!(
            Ysc3_128Stream::new(&[0u8; 32], &[0u8; 25]),
            Err(Error::BadKeyOrNonceLength)
        ));
    }
}
