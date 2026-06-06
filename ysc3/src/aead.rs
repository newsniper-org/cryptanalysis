//! YSC3 AEAD (Duplex Sponge). 사양 §3.2.
//!
//! 도메인 분리는 매 단계 별도의 워드를 capacity에 XOR — 구 V10 결함 차단.
//! 인증 태그는 128 비트.
//!
//! 본 모드는 `ysc3x` feature가 활성화될 때만 컴파일된다.

use crate::consts::{domain, STATE_WORDS};
use crate::permutation::permute;
use crate::stream::{Error, Ysc3Variant};
use zeroize::{Zeroize, ZeroizeOnDrop};

/// AEAD 16-바이트 태그.
pub type Tag = [u8; 16];

/// AEAD 객체. 매번 nonce가 새로워야 함 (single-nonce-per-key).
#[derive(Clone, Zeroize, ZeroizeOnDrop)]
pub struct Ysc3Aead<V: Ysc3Variant> {
    initial_state: [u64; STATE_WORDS],
    #[zeroize(skip)]
    _variant: core::marker::PhantomData<V>,
}

impl<V: Ysc3Variant> Ysc3Aead<V> {
    /// 새 AEAD 인스턴스. 키는 capacity에 적재되며 도메인 분리를 거친다.
    pub fn new(key: &[u8]) -> Result<Self, Error> {
        if key.len() != V::KEY_BYTES {
            return Err(Error::BadKeyOrNonceLength);
        }
        let mut state = [0u64; STATE_WORDS];
        // 키를 capacity에 적재.
        let cap_start = V::RATE_WORDS;
        for (i, chunk) in key.chunks_exact(8).enumerate() {
            state[cap_start + i] = u64::from_le_bytes(chunk.try_into().unwrap());
        }
        // AEAD 도메인 분리자.
        state[STATE_WORDS - 1] ^= domain::AEAD
            ^ (V::KEY_BYTES as u64 * 8);
        // 초기화 순열.
        permute(&mut state, V::ROUNDS_INIT);
        Ok(Self {
            initial_state: state,
            _variant: core::marker::PhantomData,
        })
    }

    /// AEAD 암호화. 평문을 in-place로 암호문으로 변환하고 16-바이트 태그를 반환.
    pub fn encrypt(&self, nonce: &[u8], ad: &[u8], buffer: &mut [u8]) -> Result<Tag, Error> {
        if nonce.len() != V::NONCE_BYTES {
            return Err(Error::BadKeyOrNonceLength);
        }
        let mut state = self.initial_state;

        absorb_with_domain::<V>(&mut state, nonce, domain::AEAD); // nonce
        absorb_with_domain::<V>(&mut state, ad, domain::AEAD_AD);

        process_payload::<V>(&mut state, buffer, true);

        state[STATE_WORDS - 1] ^= domain::AEAD_TAG;
        permute(&mut state, V::ROUNDS_BLOCK);
        let mut tag = [0u8; 16];
        tag[..8].copy_from_slice(&state[0].to_le_bytes());
        tag[8..].copy_from_slice(&state[1].to_le_bytes());
        state.zeroize();
        Ok(tag)
    }

    /// AEAD 복호화. 성공 시 buffer가 평문으로 갱신됨. 태그 불일치 시 buffer는 zeroize되고 에러.
    pub fn decrypt(
        &self,
        nonce: &[u8],
        ad: &[u8],
        buffer: &mut [u8],
        expected_tag: &Tag,
    ) -> Result<(), Error> {
        if nonce.len() != V::NONCE_BYTES {
            return Err(Error::BadKeyOrNonceLength);
        }
        let mut state = self.initial_state;

        absorb_with_domain::<V>(&mut state, nonce, domain::AEAD);
        absorb_with_domain::<V>(&mut state, ad, domain::AEAD_AD);

        process_payload::<V>(&mut state, buffer, false);

        state[STATE_WORDS - 1] ^= domain::AEAD_TAG;
        permute(&mut state, V::ROUNDS_BLOCK);
        let mut computed = [0u8; 16];
        computed[..8].copy_from_slice(&state[0].to_le_bytes());
        computed[8..].copy_from_slice(&state[1].to_le_bytes());
        state.zeroize();

        if ct_eq(&computed, expected_tag) {
            Ok(())
        } else {
            buffer.zeroize();
            Err(Error::BadKeyOrNonceLength) // TODO: 별도 AuthError 도입
        }
    }
}

fn ct_eq(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    let mut acc = 0u8;
    for (&x, &y) in a.iter().zip(b.iter()) {
        acc |= x ^ y;
    }
    acc == 0
}

fn absorb_with_domain<V: Ysc3Variant>(state: &mut [u64; STATE_WORDS], data: &[u8], dom: u64) {
    // 도메인 마커 주입.
    state[STATE_WORDS - 1] ^= dom;
    // RATE 단위로 흡수.
    let rate = V::RATE_BYTES;
    let mut chunks = data.chunks_exact(rate);
    for chunk in chunks.by_ref() {
        for (i, word) in chunk.chunks_exact(8).enumerate() {
            state[i] ^= u64::from_le_bytes(word.try_into().unwrap());
        }
        permute(state, V::ROUNDS_BLOCK);
    }
    let rem = chunks.remainder();
    // 항상 최종 패딩 블록 (SHA-3 식 multi-rate).
    let mut last = [0u8; 256];
    debug_assert!(rate <= last.len());
    last[..rem.len()].copy_from_slice(rem);
    last[rem.len()] = 0x01;
    last[rate - 1] |= 0x80;
    for i in 0..(rate / 8) {
        state[i] ^= u64::from_le_bytes(last[i * 8..(i + 1) * 8].try_into().unwrap());
    }
    permute(state, V::ROUNDS_BLOCK);
}

fn process_payload<V: Ysc3Variant>(
    state: &mut [u64; STATE_WORDS],
    buffer: &mut [u8],
    encrypting: bool,
) {
    let rate = V::RATE_BYTES;
    let mut ks = [0u8; 256];
    debug_assert!(rate <= ks.len());

    let mut offset = 0usize;
    while offset < buffer.len() {
        // 키스트림 생성: 순열 후 rate 절반 추출.
        permute(state, V::ROUNDS_BLOCK);
        for i in 0..(rate / 8) {
            ks[i * 8..(i + 1) * 8].copy_from_slice(&state[i].to_le_bytes());
        }
        let take = core::cmp::min(rate, buffer.len() - offset);
        // 흡수 단계: 도메인 마커 한 번만 (블록 단위가 아닌 페이로드 전체에 대해).
        if offset == 0 {
            state[STATE_WORDS - 1] ^= domain::AEAD_CT;
        }
        // CT 흡수: 암호문 (encrypting: XOR 결과)을 rate에 XOR. duplex 흐름.
        for k in 0..take {
            let pt_or_ct = buffer[offset + k];
            let other = pt_or_ct ^ ks[k];   // encrypting이면 ct, 아니면 pt.
            let ct_byte = if encrypting { other } else { pt_or_ct };
            // ct_byte를 state의 rate에 XOR.
            let word_idx = k / 8;
            let byte_idx = k % 8;
            let mut bytes = state[word_idx].to_le_bytes();
            bytes[byte_idx] ^= ct_byte;
            state[word_idx] = u64::from_le_bytes(bytes);
            // 출력은 평/암 그대로.
            buffer[offset + k] = other;
        }
        offset += take;
    }
    ks.zeroize();
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::stream::Ysc3_128;

    #[test]
    fn aead_roundtrip() {
        let aead = Ysc3Aead::<Ysc3_128>::new(&[0xAA; 32]).unwrap();
        let nonce = [0xBB; 24];
        let ad = b"associated data";
        let pt = b"the quick brown fox jumps over the lazy dog" as &[u8];
        let mut buf = pt.to_vec();

        let tag = aead.encrypt(&nonce, ad, &mut buf).unwrap();
        assert_ne!(&buf[..], pt);

        aead.decrypt(&nonce, ad, &mut buf, &tag).unwrap();
        assert_eq!(&buf[..], pt);
    }

    #[test]
    fn aead_tag_tamper_fails() {
        let aead = Ysc3Aead::<Ysc3_128>::new(&[0x11; 32]).unwrap();
        let nonce = [0x22; 24];
        let ad = b"";
        let mut buf = b"secret".to_vec();
        let mut tag = aead.encrypt(&nonce, ad, &mut buf).unwrap();
        tag[0] ^= 1;
        assert!(aead.decrypt(&nonce, ad, &mut buf, &tag).is_err());
        // 실패 시 buffer는 zeroize.
        assert_eq!(buf, vec![0u8; "secret".len()]);
    }
}
