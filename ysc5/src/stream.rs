//! YSC5 Stream cipher. SPEC §7.1.
//!
//! `YSC5-Stream(K, Nc, Pt) = Pt ⊕ YSC5-PRF(K, Nc ∥ DOMAIN-STM, |Pt|)`.

use crate::consts::{domain, STATE_WORDS};
use crate::farfalle::{
    key_setup, transition, Compressor, Error, Expander, Ysc5Variant, Ysc5_128, Ysc5_256,
};
use zeroize::{Zeroize, ZeroizeOnDrop};

/// 스트림 cipher 인스턴스.
///
/// 같은 (key, nonce)로 여러 번 만들면 동일한 키스트림을 다시 만들 수 있음 (deterministic).
#[derive(Clone, Zeroize, ZeroizeOnDrop)]
pub struct Ysc5Stream<V: Ysc5Variant> {
    /// transition 후의 Y' (expand seed).
    y_prime: [u64; STATE_WORDS],
    #[zeroize(skip)]
    _variant: core::marker::PhantomData<V>,
}

impl<V: Ysc5Variant> Ysc5Stream<V> {
    /// 새 스트림 cipher.
    pub fn new(key: &[u8], nonce: &[u8]) -> Result<Self, Error> {
        if nonce.len() != V::NONCE_BYTES {
            return Err(Error::BadKeyOrNonceLength);
        }
        let seed = key_setup::<V>(key, domain::STREAM)?;
        let mut c = Compressor::<V>::new(&seed);
        c.absorb(nonce);
        let (y, end_mask) = c.finish();
        let y_prime = transition::<V>(&y, &end_mask);
        Ok(Self {
            y_prime,
            _variant: core::marker::PhantomData,
        })
    }

    /// 키스트림 블록 squeeze.
    pub fn keystream(&self, out: &mut [u8]) {
        let mut e = Expander::<V>::new(&self.y_prime);
        e.squeeze(out);
    }

    /// In-place XOR (encrypt = decrypt).
    pub fn apply_keystream(&self, buffer: &mut [u8]) {
        let mut e = Expander::<V>::new(&self.y_prime);
        let mut block = [0u8; 64];
        let rate = V::RATE_BYTES;
        debug_assert!(rate <= block.len());
        let mut offset = 0usize;
        while offset < buffer.len() {
            e.squeeze_block(&mut block[..rate]);
            let take = core::cmp::min(rate, buffer.len() - offset);
            for k in 0..take {
                buffer[offset + k] ^= block[k];
            }
            offset += take;
        }
        block.zeroize();
    }
}

/// YSC5-128 스트림 cipher.
pub type Ysc5_128Stream = Ysc5Stream<Ysc5_128>;
/// YSC5-256 스트림 cipher.
pub type Ysc5_256Stream = Ysc5Stream<Ysc5_256>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn stream_roundtrip_128() {
        let key = [0x42; 32];
        let nonce = [0x24; 24];
        let pt = b"YSC5 Farfalle stream cipher round-trip" as &[u8];
        let mut buf = pt.to_vec();

        Ysc5_128Stream::new(&key, &nonce)
            .unwrap()
            .apply_keystream(&mut buf);
        assert_ne!(&buf[..], pt);

        Ysc5_128Stream::new(&key, &nonce)
            .unwrap()
            .apply_keystream(&mut buf);
        assert_eq!(&buf[..], pt);
    }

    #[test]
    fn stream_roundtrip_256() {
        let key = [0x55; 64];
        let nonce = [0xAA; 24];
        let pt = b"512-bit key variant of YSC5" as &[u8];
        let mut buf = pt.to_vec();
        Ysc5_256Stream::new(&key, &nonce)
            .unwrap()
            .apply_keystream(&mut buf);
        Ysc5_256Stream::new(&key, &nonce)
            .unwrap()
            .apply_keystream(&mut buf);
        assert_eq!(&buf[..], pt);
    }

    #[test]
    fn distinct_nonces_distinct_streams() {
        let key = [0x11; 32];
        let mut buf1 = vec![0u8; 256];
        let mut buf2 = vec![0u8; 256];
        Ysc5_128Stream::new(&key, &[0x00; 24])
            .unwrap()
            .apply_keystream(&mut buf1);
        Ysc5_128Stream::new(&key, &[0x01; 24])
            .unwrap()
            .apply_keystream(&mut buf2);
        assert_ne!(buf1, buf2);
    }
}
