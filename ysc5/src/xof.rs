//! YSC5 XOF — RustCrypto `digest::{Update, ExtendableOutput, XofReader}` 구현.
//!
//! 단순 구조: CoreApi 래퍼를 거치지 않고 `Update`/`ExtendableOutput` 직접 구현.

use crate::consts::{domain, STATE_WORDS};
use crate::farfalle::{transition, Compressor, Expander, Ysc5Variant, Ysc5_128, Ysc5_256};
use digest::{ExtendableOutput, HashMarker, Reset, Update, XofReader};
use ysc4::permutation::permute;

/// XOF 흡수 단계.
#[derive(Clone)]
pub struct Ysc5Hasher<V: Ysc5Variant> {
    compressor: Compressor<V>,
}

impl<V: Ysc5Variant> Default for Ysc5Hasher<V> {
    fn default() -> Self {
        let mut state = [0u64; STATE_WORDS];
        state[STATE_WORDS - 1] ^= domain::XOF;
        permute(&mut state, V::ROUNDS_C);
        Self {
            compressor: Compressor::<V>::new(&state),
        }
    }
}

impl<V: Ysc5Variant> Ysc5Hasher<V> {
    /// 새 해셔.
    pub fn new() -> Self {
        Self::default()
    }
}

impl<V: Ysc5Variant> HashMarker for Ysc5Hasher<V> {}

impl<V: Ysc5Variant> Update for Ysc5Hasher<V> {
    fn update(&mut self, data: &[u8]) {
        self.compressor.absorb(data);
    }
}

impl<V: Ysc5Variant> Reset for Ysc5Hasher<V> {
    fn reset(&mut self) {
        *self = Self::default();
    }
}

impl<V: Ysc5Variant> ExtendableOutput for Ysc5Hasher<V> {
    type Reader = Ysc5XofReader<V>;
    fn finalize_xof(self) -> Self::Reader {
        let (y, end_mask) = self.compressor.finish();
        let y_prime = transition::<V>(&y, &end_mask);
        Ysc5XofReader {
            expander: Expander::<V>::new(&y_prime),
        }
    }
}

/// XOF squeeze 단계.
#[derive(Clone)]
pub struct Ysc5XofReader<V: Ysc5Variant> {
    expander: Expander<V>,
}

impl<V: Ysc5Variant> XofReader for Ysc5XofReader<V> {
    fn read(&mut self, buffer: &mut [u8]) {
        self.expander.squeeze(buffer);
    }
}

/// YSC5-128 XOF.
pub type Ysc5_128Hasher = Ysc5Hasher<Ysc5_128>;
/// YSC5-256 XOF.
pub type Ysc5_256Hasher = Ysc5Hasher<Ysc5_256>;
/// YSC5-128 XOF reader.
pub type Ysc5_128XofReader = Ysc5XofReader<Ysc5_128>;
/// YSC5-256 XOF reader.
pub type Ysc5_256XofReader = Ysc5XofReader<Ysc5_256>;
