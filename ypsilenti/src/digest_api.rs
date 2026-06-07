//! RustCrypto `digest` trait 통합. `feature = "ypsi-digest"` 활성 시 컴파일.
//!
//! - `YpsiDigest` — unkeyed 128-bit hash.
//! - `YpsiMac` — keyed 128-bit MAC (key size U16).

use crate::hasher::{YpsiBuilder, YpsiHasher};
use digest::{
    consts::U16,
    crypto_common::{KeyInit, KeySizeUser, Output, OutputSizeUser},
    FixedOutput, HashMarker, MacMarker, Reset, Update,
};

#[derive(Clone)]
pub struct YpsiDigest {
    inner: YpsiHasher,
}

impl Default for YpsiDigest {
    fn default() -> Self {
        Self {
            inner: YpsiBuilder::unkeyed().build_hasher(),
        }
    }
}

impl OutputSizeUser for YpsiDigest {
    type OutputSize = U16;
}

impl Update for YpsiDigest {
    fn update(&mut self, data: &[u8]) {
        self.inner.update(data);
    }
}

impl FixedOutput for YpsiDigest {
    fn finalize_into(self, out: &mut Output<Self>) {
        let digest = self.inner.finalize();
        out.copy_from_slice(&digest);
    }
}

impl Reset for YpsiDigest {
    fn reset(&mut self) {
        *self = Self::default();
    }
}

impl HashMarker for YpsiDigest {}

// ---- Keyed MAC ----

#[derive(Clone)]
pub struct YpsiMac {
    inner: YpsiHasher,
}

impl KeySizeUser for YpsiMac {
    type KeySize = U16;
}

impl KeyInit for YpsiMac {
    fn new(key: &digest::Key<Self>) -> Self {
        Self {
            inner: YpsiBuilder::keyed(key.as_slice()).build_hasher(),
        }
    }
}

impl OutputSizeUser for YpsiMac {
    type OutputSize = U16;
}

impl Update for YpsiMac {
    fn update(&mut self, data: &[u8]) {
        self.inner.update(data);
    }
}

impl FixedOutput for YpsiMac {
    fn finalize_into(self, out: &mut Output<Self>) {
        let tag = self.inner.finalize();
        out.copy_from_slice(&tag);
    }
}

impl MacMarker for YpsiMac {}

#[cfg(test)]
mod tests {
    use super::*;
    use digest::{Digest, Mac};

    #[test]
    fn digest_basic() {
        let mut h = YpsiDigest::default();
        Update::update(&mut h, b"hello");
        let out = h.finalize_fixed();
        assert_eq!(out.len(), 16);
    }

    #[test]
    fn digest_deterministic() {
        let mut h1 = YpsiDigest::default();
        Update::update(&mut h1, b"x");
        let mut h2 = YpsiDigest::default();
        Update::update(&mut h2, b"x");
        assert_eq!(h1.finalize_fixed(), h2.finalize_fixed());
    }

    #[test]
    fn digest_distinct() {
        let mut h1 = YpsiDigest::default();
        Update::update(&mut h1, b"a");
        let mut h2 = YpsiDigest::default();
        Update::update(&mut h2, b"b");
        assert_ne!(h1.finalize_fixed(), h2.finalize_fixed());
    }

    #[test]
    fn mac_basic() {
        let key = [0x42u8; 16];
        let mut m1 = <YpsiMac as KeyInit>::new_from_slice(&key).unwrap();
        Update::update(&mut m1, b"msg");
        let t1 = m1.finalize_fixed();
        let mut m2 = <YpsiMac as KeyInit>::new_from_slice(&key).unwrap();
        Update::update(&mut m2, b"msg");
        let t2 = m2.finalize_fixed();
        assert_eq!(t1, t2);
    }

    #[test]
    fn mac_distinct_keys() {
        let mut m1 = <YpsiMac as KeyInit>::new_from_slice(&[0u8; 16]).unwrap();
        Update::update(&mut m1, b"msg");
        let mut m2 = <YpsiMac as KeyInit>::new_from_slice(&[1u8; 16]).unwrap();
        Update::update(&mut m2, b"msg");
        assert_ne!(m1.finalize_fixed(), m2.finalize_fixed());
    }

    #[test]
    fn mac_uses_mac_trait() {
        let key = [0xAB; 16];
        let mut m = <YpsiMac as Mac>::new_from_slice(&key).unwrap();
        Mac::update(&mut m, b"data");
        let _ = m.finalize().into_bytes();
    }
}
