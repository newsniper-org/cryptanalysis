//! RustCrypto `digest` trait 통합. `feature = "yhash-digest"` 활성 시 컴파일.
//!
//! 제공:
//! - `YHashDigest` — unkeyed 256-bit hash (`Update + FixedOutput + HashMarker`).
//! - `YHashMac`   — keyed 256-bit MAC (`Update + FixedOutput + MacMarker + KeyInit`).

use crate::consts::CV_BYTES;
use crate::hasher::{YHashBuilder, YHasher};
use digest::{
    consts::{U16, U32},
    crypto_common::{KeyInit, KeySizeUser, Output, OutputSizeUser},
    FixedOutput, HashMarker, MacMarker, Reset, Update,
};

/// 256-bit unkeyed digest (RustCrypto `digest` API).
#[derive(Clone)]
pub struct YHashDigest {
    inner: YHasher,
}

impl Default for YHashDigest {
    fn default() -> Self {
        Self {
            inner: YHashBuilder::unkeyed().build_hasher(),
        }
    }
}

impl OutputSizeUser for YHashDigest {
    type OutputSize = U32;
}

impl Update for YHashDigest {
    fn update(&mut self, data: &[u8]) {
        self.inner.update(data);
    }
}

impl FixedOutput for YHashDigest {
    fn finalize_into(self, out: &mut Output<Self>) {
        let digest = self.inner.finalize();
        out.copy_from_slice(&digest);
    }
}

impl Reset for YHashDigest {
    fn reset(&mut self) {
        *self = Self::default();
    }
}

impl HashMarker for YHashDigest {}

// ---- Keyed MAC ----

/// 128-bit 키로 init되는 256-bit MAC.
#[derive(Clone)]
pub struct YHashMac {
    inner: YHasher,
}

impl KeySizeUser for YHashMac {
    type KeySize = U16;
}

impl KeyInit for YHashMac {
    fn new(key: &digest::Key<Self>) -> Self {
        Self {
            inner: YHashBuilder::keyed(key.as_slice()).build_hasher(),
        }
    }
}

impl OutputSizeUser for YHashMac {
    type OutputSize = U32;
}

impl Update for YHashMac {
    fn update(&mut self, data: &[u8]) {
        self.inner.update(data);
    }
}

impl FixedOutput for YHashMac {
    fn finalize_into(self, out: &mut Output<Self>) {
        let tag = self.inner.finalize();
        out.copy_from_slice(&tag);
    }
}

impl MacMarker for YHashMac {}

const _: () = {
    // sanity check: CV_BYTES == 32 == U32::USIZE
    let _ = CV_BYTES - 32;
};

#[cfg(test)]
mod tests {
    use super::*;
    use digest::{Digest, Mac};

    #[test]
    fn digest_basic() {
        let mut h = YHashDigest::default();
        Update::update(&mut h, b"hello");
        let out = h.finalize_fixed();
        assert_eq!(out.len(), 32);
    }

    #[test]
    fn digest_deterministic() {
        let mut h1 = YHashDigest::default();
        Update::update(&mut h1, b"hello");
        let d1 = h1.finalize_fixed();

        let mut h2 = YHashDigest::default();
        Update::update(&mut h2, b"hello");
        let d2 = h2.finalize_fixed();

        assert_eq!(d1, d2);
    }

    #[test]
    fn digest_distinct() {
        let mut h1 = YHashDigest::default();
        Update::update(&mut h1, b"a");
        let mut h2 = YHashDigest::default();
        Update::update(&mut h2, b"b");
        assert_ne!(h1.finalize_fixed(), h2.finalize_fixed());
    }

    #[test]
    fn mac_basic() {
        let key = [0x42u8; 16];
        let mut m1 = <YHashMac as KeyInit>::new_from_slice(&key).unwrap();
        Update::update(&mut m1, b"msg");
        let t1 = m1.finalize_fixed();

        let mut m2 = <YHashMac as KeyInit>::new_from_slice(&key).unwrap();
        Update::update(&mut m2, b"msg");
        let t2 = m2.finalize_fixed();

        assert_eq!(t1, t2);
    }

    #[test]
    fn mac_distinct_keys() {
        let mut m1 = <YHashMac as KeyInit>::new_from_slice(&[0u8; 16]).unwrap();
        Update::update(&mut m1, b"msg");
        let mut m2 = <YHashMac as KeyInit>::new_from_slice(&[1u8; 16]).unwrap();
        Update::update(&mut m2, b"msg");
        assert_ne!(m1.finalize_fixed(), m2.finalize_fixed());
    }

    #[test]
    fn mac_uses_mac_trait() {
        // digest::Mac 자동 구현 검증 (KeyInit + MacMarker + Update + FixedOutput)
        let key = [0xAB; 16];
        let mut m = <YHashMac as Mac>::new_from_slice(&key).unwrap();
        Mac::update(&mut m, b"data");
        let tag = m.finalize();
        let _bytes = tag.into_bytes();
    }
}
