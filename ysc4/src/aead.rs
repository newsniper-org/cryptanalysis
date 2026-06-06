//! v0.2 AEAD. v0.1과 동일한 duplex sponge 흐름, 순열만 v0.2.

use crate::consts::{domain, STATE_WORDS};
use crate::permutation::permute;
use crate::stream::{Error, Ysc4Variant};
use zeroize::{Zeroize, ZeroizeOnDrop};

/// AEAD 태그.
pub type Tag = [u8; 16];

/// AEAD 객체.
#[derive(Clone, Zeroize, ZeroizeOnDrop)]
pub struct Ysc4Aead<V: Ysc4Variant> {
    initial_state: [u64; STATE_WORDS],
    #[zeroize(skip)]
    _variant: core::marker::PhantomData<V>,
}

impl<V: Ysc4Variant> Ysc4Aead<V> {
    /// 새 AEAD.
    pub fn new(key: &[u8]) -> Result<Self, Error> {
        if key.len() != V::KEY_BYTES {
            return Err(Error::BadKeyOrNonceLength);
        }
        let mut state = [0u64; STATE_WORDS];
        let cap_start = V::RATE_WORDS;
        for (i, chunk) in key.chunks_exact(8).enumerate() {
            state[cap_start + i] = u64::from_le_bytes(chunk.try_into().unwrap());
        }
        state[STATE_WORDS - 1] ^= domain::AEAD ^ (V::KEY_BYTES as u64 * 8);
        permute(&mut state, V::ROUNDS_INIT);
        Ok(Self {
            initial_state: state,
            _variant: core::marker::PhantomData,
        })
    }

    /// AEAD 암호화.
    pub fn encrypt(&self, nonce: &[u8], ad: &[u8], buffer: &mut [u8]) -> Result<Tag, Error> {
        if nonce.len() != V::NONCE_BYTES {
            return Err(Error::BadKeyOrNonceLength);
        }
        let mut state = self.initial_state;
        absorb::<V>(&mut state, nonce, domain::AEAD);
        absorb::<V>(&mut state, ad, domain::AEAD_AD);
        payload::<V>(&mut state, buffer, true);
        state[STATE_WORDS - 1] ^= domain::AEAD_TAG;
        permute(&mut state, V::ROUNDS_BLOCK);
        let mut tag = [0u8; 16];
        tag[..8].copy_from_slice(&state[0].to_le_bytes());
        tag[8..].copy_from_slice(&state[1].to_le_bytes());
        state.zeroize();
        Ok(tag)
    }

    /// AEAD 복호화.
    pub fn decrypt(
        &self,
        nonce: &[u8],
        ad: &[u8],
        buffer: &mut [u8],
        expected: &Tag,
    ) -> Result<(), Error> {
        if nonce.len() != V::NONCE_BYTES {
            return Err(Error::BadKeyOrNonceLength);
        }
        let mut state = self.initial_state;
        absorb::<V>(&mut state, nonce, domain::AEAD);
        absorb::<V>(&mut state, ad, domain::AEAD_AD);
        payload::<V>(&mut state, buffer, false);
        state[STATE_WORDS - 1] ^= domain::AEAD_TAG;
        permute(&mut state, V::ROUNDS_BLOCK);
        let mut computed = [0u8; 16];
        computed[..8].copy_from_slice(&state[0].to_le_bytes());
        computed[8..].copy_from_slice(&state[1].to_le_bytes());
        state.zeroize();
        if ct_eq(&computed, expected) {
            Ok(())
        } else {
            buffer.zeroize();
            Err(Error::AuthenticationFailed)
        }
    }
}

fn ct_eq(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    a.iter().zip(b.iter()).fold(0u8, |acc, (&x, &y)| acc | (x ^ y)) == 0
}

fn absorb<V: Ysc4Variant>(state: &mut [u64; STATE_WORDS], data: &[u8], dom: u64) {
    state[STATE_WORDS - 1] ^= dom;
    let rate = V::RATE_BYTES;
    let mut chunks = data.chunks_exact(rate);
    for chunk in chunks.by_ref() {
        for (i, word) in chunk.chunks_exact(8).enumerate() {
            state[i] ^= u64::from_le_bytes(word.try_into().unwrap());
        }
        permute(state, V::ROUNDS_BLOCK);
    }
    let rem = chunks.remainder();
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

fn payload<V: Ysc4Variant>(state: &mut [u64; STATE_WORDS], buffer: &mut [u8], encrypting: bool) {
    let rate = V::RATE_BYTES;
    let mut ks = [0u8; 256];
    debug_assert!(rate <= ks.len());
    let mut offset = 0usize;
    while offset < buffer.len() {
        permute(state, V::ROUNDS_BLOCK);
        for i in 0..(rate / 8) {
            ks[i * 8..(i + 1) * 8].copy_from_slice(&state[i].to_le_bytes());
        }
        let take = core::cmp::min(rate, buffer.len() - offset);
        if offset == 0 {
            state[STATE_WORDS - 1] ^= domain::AEAD_CT;
        }
        for k in 0..take {
            let val = buffer[offset + k];
            let other = val ^ ks[k];
            let ct_byte = if encrypting { other } else { val };
            let word_idx = k / 8;
            let byte_idx = k % 8;
            let mut bytes = state[word_idx].to_le_bytes();
            bytes[byte_idx] ^= ct_byte;
            state[word_idx] = u64::from_le_bytes(bytes);
            buffer[offset + k] = other;
        }
        offset += take;
    }
    ks.zeroize();
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::stream::Ysc4_128;

    #[test]
    fn aead_roundtrip() {
        let a = Ysc4Aead::<Ysc4_128>::new(&[0xAA; 32]).unwrap();
        let nonce = [0xBB; 24];
        let ad = b"ad";
        let pt = b"v0.2 sigma-GLM duplex AEAD test message";
        let mut buf = pt.to_vec();
        let tag = a.encrypt(&nonce, ad, &mut buf).unwrap();
        assert_ne!(&buf[..], pt);
        a.decrypt(&nonce, ad, &mut buf, &tag).unwrap();
        assert_eq!(&buf[..], pt);
    }

    #[test]
    fn aead_tag_tamper() {
        let a = Ysc4Aead::<Ysc4_128>::new(&[0x11; 32]).unwrap();
        let nonce = [0x22; 24];
        let mut buf = b"secret".to_vec();
        let mut tag = a.encrypt(&nonce, b"", &mut buf).unwrap();
        tag[0] ^= 1;
        assert!(a.decrypt(&nonce, b"", &mut buf, &tag).is_err());
        assert_eq!(buf, vec![0u8; 6]);
    }
}
