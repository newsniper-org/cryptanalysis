//! v0.2 스트림 cipher. v0.1과 모드 사양 동일, 순열만 v0.2로 교체.

use crate::consts::{domain, STATE_WORDS};
use crate::permutation::permute;
use zeroize::{Zeroize, ZeroizeOnDrop};

/// 매개변수 집합.
pub trait Ysc4Variant {
    /// 키 바이트 수.
    const KEY_BYTES: usize;
    /// 논스 바이트 수.
    const NONCE_BYTES: usize;
    /// rate 워드 수.
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
pub struct Ysc4_128;
impl Ysc4Variant for Ysc4_128 {
    const KEY_BYTES: usize = 32;
    const NONCE_BYTES: usize = 24;
    const RATE_WORDS: usize = 8;
    const ROUNDS_INIT: usize = 32;
    const ROUNDS_BLOCK: usize = 16;
}

/// 256-비트 보안 매개변수.
#[derive(Clone, Copy, Debug)]
pub struct Ysc4_256;
impl Ysc4Variant for Ysc4_256 {
    const KEY_BYTES: usize = 64;
    const NONCE_BYTES: usize = 24;
    const RATE_WORDS: usize = 4;
    const ROUNDS_INIT: usize = 40;
    const ROUNDS_BLOCK: usize = 20;
}

/// 길이 불일치 등 사용자 에러.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Error {
    /// 키 또는 논스의 길이가 매개변수와 다름.
    BadKeyOrNonceLength,
    /// AEAD 태그 검증 실패.
    AuthenticationFailed,
}

/// 스트림 cipher 상태.
#[derive(Clone, Zeroize, ZeroizeOnDrop)]
pub struct Ysc4Stream<V: Ysc4Variant> {
    state: [u64; STATE_WORDS],
    #[zeroize(skip)]
    _variant: core::marker::PhantomData<V>,
}

impl<V: Ysc4Variant> core::fmt::Debug for Ysc4Stream<V> {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        f.debug_struct("Ysc4Stream").finish_non_exhaustive()
    }
}

impl<V: Ysc4Variant> Ysc4Stream<V> {
    /// 새 스트림 cipher 인스턴스 생성. v0.1과 동일한 초기화 흐름.
    pub fn new(key: &[u8], nonce: &[u8]) -> Result<Self, Error> {
        if key.len() != V::KEY_BYTES || nonce.len() != V::NONCE_BYTES {
            return Err(Error::BadKeyOrNonceLength);
        }
        let mut state = [0u64; STATE_WORDS];

        let cap_start = V::RATE_WORDS;
        for (i, chunk) in key.chunks_exact(8).enumerate() {
            state[cap_start + i] = u64::from_le_bytes(chunk.try_into().unwrap());
        }
        for (i, chunk) in nonce.chunks_exact(8).enumerate() {
            state[i] = u64::from_le_bytes(chunk.try_into().unwrap());
        }
        let domain_word =
            domain::STREAM ^ (V::KEY_BYTES as u64 * 8) ^ ((V::NONCE_BYTES as u64 * 8) << 32);
        state[STATE_WORDS - 1] ^= domain_word;

        permute(&mut state, V::ROUNDS_INIT);

        Ok(Self {
            state,
            _variant: core::marker::PhantomData,
        })
    }

    /// 키스트림 블록 (RATE_BYTES) 생성.
    pub fn keystream_block(&self, i: u64, out: &mut [u8]) {
        debug_assert_eq!(out.len(), V::RATE_BYTES);
        let mut working = self.state;
        working[STATE_WORDS - 2] ^= i;
        permute(&mut working, V::ROUNDS_BLOCK);

        for (j, chunk) in out.chunks_exact_mut(8).enumerate() {
            chunk.copy_from_slice(&working[j].to_le_bytes());
        }

        working.zeroize();
    }

    /// `buffer`를 in-place로 암호화 (또는 복호화).
    pub fn apply_keystream(&self, buffer: &mut [u8], start_block: u64) {
        let mut block = [0u8; 256];
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

/// YSC3 v0.2 128-비트 스트림 cipher.
pub type Ysc4_128Stream = Ysc4Stream<Ysc4_128>;
/// YSC3 v0.2 256-비트 스트림 cipher.
pub type Ysc4_256Stream = Ysc4Stream<Ysc4_256>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn roundtrip_128() {
        let key = [0xAA; 32];
        let nonce = [0xBB; 24];
        let pt = b"YSC3 v0.2 sigma-GLM stream test" as &[u8];
        let mut buf = pt.to_vec();

        let cipher = Ysc4_128Stream::new(&key, &nonce).unwrap();
        cipher.apply_keystream(&mut buf, 0);
        assert_ne!(&buf[..], pt);

        Ysc4_128Stream::new(&key, &nonce)
            .unwrap()
            .apply_keystream(&mut buf, 0);
        assert_eq!(&buf[..], pt);
    }

    #[test]
    fn roundtrip_256() {
        let key = [0xCC; 64];
        let nonce = [0xDD; 24];
        let pt = b"YSC3 v0.2 with 512-bit key" as &[u8];
        let mut buf = pt.to_vec();

        let cipher = Ysc4_256Stream::new(&key, &nonce).unwrap();
        cipher.apply_keystream(&mut buf, 0);
        Ysc4_256Stream::new(&key, &nonce)
            .unwrap()
            .apply_keystream(&mut buf, 0);
        assert_eq!(&buf[..], pt);
    }

    #[test]
    fn seekable_consistency() {
        let key = [1u8; 32];
        let nonce = [2u8; 24];
        let cipher = Ysc4_128Stream::new(&key, &nonce).unwrap();

        let mut buf_long = vec![0u8; 128];
        cipher.apply_keystream(&mut buf_long, 0);

        let mut buf2 = vec![0u8; 64];
        cipher.apply_keystream(&mut buf2, 1);

        assert_eq!(&buf_long[64..], &buf2[..]);
    }
}
