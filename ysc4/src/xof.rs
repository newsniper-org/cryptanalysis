//! v0.2 sponge XOF.

use crate::consts::{domain, STATE_WORDS};
use crate::permutation::permute;
use crate::stream::Ysc4Variant;
use zeroize::{Zeroize, ZeroizeOnDrop};

/// XOF 흡수 단계.
#[derive(Clone, Zeroize, ZeroizeOnDrop)]
pub struct Hasher<V: Ysc4Variant> {
    state: [u64; STATE_WORDS],
    buf: [u8; 256],
    buf_len: usize,
    #[zeroize(skip)]
    _variant: core::marker::PhantomData<V>,
}

impl<V: Ysc4Variant> Default for Hasher<V> {
    fn default() -> Self {
        let mut state = [0u64; STATE_WORDS];
        state[STATE_WORDS - 1] ^= domain::XOF;
        Self {
            state,
            buf: [0u8; 256],
            buf_len: 0,
            _variant: core::marker::PhantomData,
        }
    }
}

impl<V: Ysc4Variant> Hasher<V> {
    /// 새 해셔.
    pub fn new() -> Self {
        Self::default()
    }

    /// 메시지 흡수.
    pub fn update(&mut self, mut data: &[u8]) {
        let rate = V::RATE_BYTES;
        debug_assert!(rate <= self.buf.len());
        while !data.is_empty() {
            let free = rate - self.buf_len;
            let take = core::cmp::min(free, data.len());
            self.buf[self.buf_len..self.buf_len + take].copy_from_slice(&data[..take]);
            self.buf_len += take;
            data = &data[take..];
            if self.buf_len == rate {
                for i in 0..(rate / 8) {
                    self.state[i] ^= u64::from_le_bytes(
                        self.buf[i * 8..(i + 1) * 8].try_into().unwrap(),
                    );
                }
                permute(&mut self.state, V::ROUNDS_BLOCK);
                self.buf_len = 0;
            }
        }
    }

    /// XOF squeeze 시작.
    pub fn finalize_xof(mut self) -> Reader<V> {
        let rate = V::RATE_BYTES;
        self.buf[self.buf_len] = 0x01;
        for k in (self.buf_len + 1)..rate {
            self.buf[k] = 0;
        }
        self.buf[rate - 1] |= 0x80;
        for i in 0..(rate / 8) {
            self.state[i] ^= u64::from_le_bytes(self.buf[i * 8..(i + 1) * 8].try_into().unwrap());
        }
        permute(&mut self.state, V::ROUNDS_INIT);
        Reader {
            state: self.state,
            pos: 0,
            _variant: core::marker::PhantomData,
        }
    }
}

/// XOF squeeze.
#[derive(Clone, Zeroize, ZeroizeOnDrop)]
pub struct Reader<V: Ysc4Variant> {
    state: [u64; STATE_WORDS],
    pos: usize,
    #[zeroize(skip)]
    _variant: core::marker::PhantomData<V>,
}

impl<V: Ysc4Variant> Reader<V> {
    /// 출력 읽기.
    pub fn read(&mut self, mut out: &mut [u8]) {
        let rate = V::RATE_BYTES;
        while !out.is_empty() {
            if self.pos == rate {
                permute(&mut self.state, V::ROUNDS_BLOCK);
                self.pos = 0;
            }
            let mut block = [0u8; 256];
            debug_assert!(rate <= block.len());
            for i in 0..(rate / 8) {
                block[i * 8..(i + 1) * 8].copy_from_slice(&self.state[i].to_le_bytes());
            }
            let avail = rate - self.pos;
            let take = core::cmp::min(avail, out.len());
            out[..take].copy_from_slice(&block[self.pos..self.pos + take]);
            self.pos += take;
            out = &mut out[take..];
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::stream::Ysc4_128;

    #[test]
    fn xof_deterministic() {
        let mut h1 = Hasher::<Ysc4_128>::new();
        h1.update(b"hello");
        let mut o1 = [0u8; 32];
        h1.finalize_xof().read(&mut o1);

        let mut h2 = Hasher::<Ysc4_128>::new();
        h2.update(b"hello");
        let mut o2 = [0u8; 32];
        h2.finalize_xof().read(&mut o2);

        assert_eq!(o1, o2);
    }

    #[test]
    fn xof_changes_with_input() {
        let mut h1 = Hasher::<Ysc4_128>::new();
        h1.update(b"hello");
        let mut o1 = [0u8; 32];
        h1.finalize_xof().read(&mut o1);

        let mut h2 = Hasher::<Ysc4_128>::new();
        h2.update(b"world");
        let mut o2 = [0u8; 32];
        h2.finalize_xof().read(&mut o2);

        assert_ne!(o1, o2);
    }
}
