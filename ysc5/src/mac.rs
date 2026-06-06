//! YSC5 MAC — RustCrypto `digest::Mac` 호환.
//!
//! 직접 구현: `KeyInit + MacMarker + Update + FixedOutput`.

use crate::consts::{domain, STATE_WORDS};
use crate::farfalle::{
    key_setup, transition, Compressor, Expander, Ysc5Variant, Ysc5_128, Ysc5_256,
};
use crypto_common::{Key, KeyInit, KeySizeUser, Output, OutputSizeUser};
use digest::{
    consts::{U16, U32},
    FixedOutput, MacMarker, Update,
};
use zeroize::Zeroize;

/// MAC core.
#[derive(Clone)]
pub struct Ysc5MacCore<V: Ysc5Variant> {
    seed: [u64; STATE_WORDS],
    compressor: Compressor<V>,
    _variant: core::marker::PhantomData<V>,
}

impl<V: Ysc5Variant> Drop for Ysc5MacCore<V> {
    fn drop(&mut self) {
        self.seed.zeroize();
    }
}

impl<V: Ysc5Variant> MacMarker for Ysc5MacCore<V> {}

// ---- per-variant impls ----

impl KeySizeUser for Ysc5MacCore<Ysc5_128> {
    type KeySize = U32;
}
impl KeySizeUser for Ysc5MacCore<Ysc5_256> {
    type KeySize = digest::consts::U64;
}

impl OutputSizeUser for Ysc5MacCore<Ysc5_128> {
    type OutputSize = U16;
}
impl OutputSizeUser for Ysc5MacCore<Ysc5_256> {
    type OutputSize = U32;
}

impl KeyInit for Ysc5MacCore<Ysc5_128> {
    fn new(key: &Key<Self>) -> Self {
        let seed = key_setup::<Ysc5_128>(key.as_slice(), domain::MAC).unwrap();
        Self {
            seed,
            compressor: Compressor::<Ysc5_128>::new(&seed),
            _variant: core::marker::PhantomData,
        }
    }
}

impl KeyInit for Ysc5MacCore<Ysc5_256> {
    fn new(key: &Key<Self>) -> Self {
        let seed = key_setup::<Ysc5_256>(key.as_slice(), domain::MAC).unwrap();
        Self {
            seed,
            compressor: Compressor::<Ysc5_256>::new(&seed),
            _variant: core::marker::PhantomData,
        }
    }
}

impl<V: Ysc5Variant> Update for Ysc5MacCore<V> {
    fn update(&mut self, data: &[u8]) {
        self.compressor.absorb(data);
    }
}

impl FixedOutput for Ysc5MacCore<Ysc5_128> {
    fn finalize_into(self, out: &mut Output<Self>) {
        let (y, end_mask) = self.compressor.clone().finish();
        let y_prime = transition::<Ysc5_128>(&y, &end_mask);
        let mut e = Expander::<Ysc5_128>::new(&y_prime);
        e.squeeze(out.as_mut_slice());
    }
}

impl FixedOutput for Ysc5MacCore<Ysc5_256> {
    fn finalize_into(self, out: &mut Output<Self>) {
        let (y, end_mask) = self.compressor.clone().finish();
        let y_prime = transition::<Ysc5_256>(&y, &end_mask);
        let mut e = Expander::<Ysc5_256>::new(&y_prime);
        e.squeeze(out.as_mut_slice());
    }
}

/// YSC5-128 MAC (128-비트 tag).
pub type Ysc5_128Mac = Ysc5MacCore<Ysc5_128>;
/// YSC5-256 MAC (256-비트 tag).
pub type Ysc5_256Mac = Ysc5MacCore<Ysc5_256>;
