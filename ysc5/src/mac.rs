//! YSC5 MAC. SPEC §7.4.
//!
//! `YSC5-MAC(K, M) = YSC5-PRF(K, M ∥ DOMAIN-MAC, tag-size)`.

use crate::consts::{domain, STATE_WORDS};
use crate::farfalle::{
    key_setup, transition, Compressor, Error, Expander, Ysc5Variant,
};
use alloc::vec;
use alloc::vec::Vec;

/// MAC 인스턴스. Compressor의 ZeroizeOnDrop이 비밀 상태 정리를 담당.
#[derive(Clone)]
pub struct Ysc5Mac<V: Ysc5Variant> {
    seed: [u64; STATE_WORDS],
    compressor: Compressor<V>,
    _variant: core::marker::PhantomData<V>,
}

impl<V: Ysc5Variant> Ysc5Mac<V> {
    /// 새 MAC.
    pub fn new(key: &[u8]) -> Result<Self, Error> {
        let seed = key_setup::<V>(key, domain::MAC)?;
        Ok(Self {
            seed,
            compressor: Compressor::<V>::new(&seed),
            _variant: core::marker::PhantomData,
        })
    }

    /// 메시지 흡수.
    pub fn update(&mut self, data: &[u8]) {
        self.compressor.absorb(data);
    }

    /// 태그 출력 (consumes self).
    pub fn finalize(self) -> Vec<u8> {
        let (y, end_mask) = self.compressor.finish();
        let y_prime = transition::<V>(&y, &end_mask);
        let mut e = Expander::<V>::new(&y_prime);
        let mut tag = vec![0u8; V::TAG_BYTES];
        e.squeeze(&mut tag);
        let mut seed_copy = self.seed;
        zeroize::Zeroize::zeroize(&mut seed_copy);
        tag
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::farfalle::Ysc5_128;

    #[test]
    fn mac_deterministic() {
        let mut m1 = Ysc5Mac::<Ysc5_128>::new(&[0x42; 32]).unwrap();
        m1.update(b"hello");
        let tag1 = m1.finalize();

        let mut m2 = Ysc5Mac::<Ysc5_128>::new(&[0x42; 32]).unwrap();
        m2.update(b"hello");
        let tag2 = m2.finalize();

        assert_eq!(tag1, tag2);
    }

    #[test]
    fn mac_distinct_keys() {
        let mut m1 = Ysc5Mac::<Ysc5_128>::new(&[0x42; 32]).unwrap();
        m1.update(b"msg");
        let tag1 = m1.finalize();

        let mut m2 = Ysc5Mac::<Ysc5_128>::new(&[0x43; 32]).unwrap();
        m2.update(b"msg");
        let tag2 = m2.finalize();

        assert_ne!(tag1, tag2);
    }

    #[test]
    fn mac_distinct_messages() {
        let mut m1 = Ysc5Mac::<Ysc5_128>::new(&[0x55; 32]).unwrap();
        m1.update(b"msg1");
        let tag1 = m1.finalize();

        let mut m2 = Ysc5Mac::<Ysc5_128>::new(&[0x55; 32]).unwrap();
        m2.update(b"msg2");
        let tag2 = m2.finalize();

        assert_ne!(tag1, tag2);
    }
}
