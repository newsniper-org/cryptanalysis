//! YSC5 AEAD — RustCrypto `aead::AeadInPlace` trait 구현.

use crate::consts::{domain, STATE_WORDS};
use crate::farfalle::{
    key_setup, transition, Compressor, Expander, Ysc5Variant, Ysc5_128, Ysc5_256,
};
use aead::{
    consts::{U0, U16, U24, U32, U64},
    generic_array::GenericArray,
    AeadCore, AeadInPlace, Key, KeyInit, KeySizeUser, Nonce, Tag,
};
use alloc::vec;
use zeroize::Zeroize;

/// AEAD cipher 인스턴스.
#[derive(Clone)]
pub struct Ysc5Aead<V: Ysc5Variant> {
    seed: [u64; STATE_WORDS],
    _variant: core::marker::PhantomData<V>,
}

impl<V: Ysc5Variant> Drop for Ysc5Aead<V> {
    fn drop(&mut self) {
        self.seed.zeroize();
    }
}

// ---- KeySizeUser / KeyInit ----

impl KeySizeUser for Ysc5Aead<Ysc5_128> {
    type KeySize = U32;
}
impl KeySizeUser for Ysc5Aead<Ysc5_256> {
    type KeySize = U64;
}

impl KeyInit for Ysc5Aead<Ysc5_128> {
    fn new(key: &Key<Self>) -> Self {
        let seed = key_setup::<Ysc5_128>(key.as_slice(), domain::AEAD)
            .expect("KeyInit: GenericArray length guaranteed");
        Self {
            seed,
            _variant: core::marker::PhantomData,
        }
    }
}

impl KeyInit for Ysc5Aead<Ysc5_256> {
    fn new(key: &Key<Self>) -> Self {
        let seed = key_setup::<Ysc5_256>(key.as_slice(), domain::AEAD)
            .expect("KeyInit: GenericArray length guaranteed");
        Self {
            seed,
            _variant: core::marker::PhantomData,
        }
    }
}

// ---- AeadCore ----

impl AeadCore for Ysc5Aead<Ysc5_128> {
    type NonceSize = U24;
    type TagSize = U16;
    type CiphertextOverhead = U0;
}

impl AeadCore for Ysc5Aead<Ysc5_256> {
    type NonceSize = U24;
    type TagSize = U32;
    type CiphertextOverhead = U0;
}

// ---- Internal: 두 패스 AEAD ----

impl<V: Ysc5Variant> Ysc5Aead<V> {
    fn keystream_seed(&self, nonce: &[u8], ad: &[u8]) -> [u64; STATE_WORDS] {
        let mut c = Compressor::<V>::new(&self.seed);
        c.absorb(nonce);
        let mut dm = [0u8; 8];
        dm.copy_from_slice(&domain::AEAD_AD.to_le_bytes());
        c.absorb(&dm);
        c.absorb(ad);
        let (y, end_mask) = c.finish();
        transition::<V>(&y, &end_mask)
    }

    fn tag_seed(&self, nonce: &[u8], ad: &[u8], ct: &[u8]) -> [u64; STATE_WORDS] {
        let mut c = Compressor::<V>::new(&self.seed);
        c.absorb(nonce);
        let mut dm_ad = [0u8; 8];
        dm_ad.copy_from_slice(&domain::AEAD_AD.to_le_bytes());
        c.absorb(&dm_ad);
        c.absorb(ad);
        let mut dm_ct = [0u8; 8];
        dm_ct.copy_from_slice(&domain::AEAD_CT.to_le_bytes());
        c.absorb(&dm_ct);
        c.absorb(ct);
        let (y, end_mask) = c.finish();
        let mut yp = transition::<V>(&y, &end_mask);
        yp[STATE_WORDS - 1] ^= domain::AEAD_TAG;
        yp
    }

    fn apply_keystream(&self, y_ks: &[u64; STATE_WORDS], buffer: &mut [u8]) {
        let mut e = Expander::<V>::new(y_ks);
        let mut block = [0u8; 64];
        let rate = V::RATE_BYTES;
        let mut offset = 0usize;
        while offset < buffer.len() {
            let take = core::cmp::min(rate, buffer.len() - offset);
            e.squeeze(&mut block[..take]);
            for k in 0..take {
                buffer[offset + k] ^= block[k];
            }
            offset += take;
        }
        block.zeroize();
    }
}

// ---- AeadInPlace ----

impl AeadInPlace for Ysc5Aead<Ysc5_128> {
    fn encrypt_in_place_detached(
        &self,
        nonce: &Nonce<Self>,
        ad: &[u8],
        buffer: &mut [u8],
    ) -> aead::Result<Tag<Self>> {
        let y_ks = self.keystream_seed(nonce.as_slice(), ad);
        self.apply_keystream(&y_ks, buffer);
        let y_tag = self.tag_seed(nonce.as_slice(), ad, buffer);
        let mut e_tag = Expander::<Ysc5_128>::new(&y_tag);
        let mut tag = vec![0u8; 16];
        e_tag.squeeze(&mut tag);
        Ok(*GenericArray::from_slice(&tag))
    }

    fn decrypt_in_place_detached(
        &self,
        nonce: &Nonce<Self>,
        ad: &[u8],
        buffer: &mut [u8],
        expected: &Tag<Self>,
    ) -> aead::Result<()> {
        let y_tag = self.tag_seed(nonce.as_slice(), ad, buffer);
        let mut e_tag = Expander::<Ysc5_128>::new(&y_tag);
        let mut computed = vec![0u8; 16];
        e_tag.squeeze(&mut computed);
        if !ct_eq(&computed, expected.as_slice()) {
            buffer.zeroize();
            return Err(aead::Error);
        }
        let y_ks = self.keystream_seed(nonce.as_slice(), ad);
        self.apply_keystream(&y_ks, buffer);
        Ok(())
    }
}

impl AeadInPlace for Ysc5Aead<Ysc5_256> {
    fn encrypt_in_place_detached(
        &self,
        nonce: &Nonce<Self>,
        ad: &[u8],
        buffer: &mut [u8],
    ) -> aead::Result<Tag<Self>> {
        let y_ks = self.keystream_seed(nonce.as_slice(), ad);
        self.apply_keystream(&y_ks, buffer);
        let y_tag = self.tag_seed(nonce.as_slice(), ad, buffer);
        let mut e_tag = Expander::<Ysc5_256>::new(&y_tag);
        let mut tag = vec![0u8; 32];
        e_tag.squeeze(&mut tag);
        Ok(*GenericArray::from_slice(&tag))
    }

    fn decrypt_in_place_detached(
        &self,
        nonce: &Nonce<Self>,
        ad: &[u8],
        buffer: &mut [u8],
        expected: &Tag<Self>,
    ) -> aead::Result<()> {
        let y_tag = self.tag_seed(nonce.as_slice(), ad, buffer);
        let mut e_tag = Expander::<Ysc5_256>::new(&y_tag);
        let mut computed = vec![0u8; 32];
        e_tag.squeeze(&mut computed);
        if !ct_eq(&computed, expected.as_slice()) {
            buffer.zeroize();
            return Err(aead::Error);
        }
        let y_ks = self.keystream_seed(nonce.as_slice(), ad);
        self.apply_keystream(&y_ks, buffer);
        Ok(())
    }
}

fn ct_eq(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    a.iter().zip(b.iter()).fold(0u8, |acc, (&x, &y)| acc | (x ^ y)) == 0
}

/// 128-비트 AEAD.
pub type Ysc5_128Aead = Ysc5Aead<Ysc5_128>;
/// 256-비트 AEAD.
pub type Ysc5_256Aead = Ysc5Aead<Ysc5_256>;
