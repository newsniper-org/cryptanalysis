//! YSC3-XOF (sponge 해시). 사양 §3.3.
//!
//! 본 모드는 `ysc3x` feature가 활성화될 때만 컴파일된다.

use crate::consts::{domain, STATE_WORDS};
use crate::permutation::permute;
use crate::stream::Ysc3Variant;
use zeroize::{Zeroize, ZeroizeOnDrop};

/// XOF 흡수 단계.
#[derive(Clone, Zeroize, ZeroizeOnDrop)]
pub struct Hasher<V: Ysc3Variant> {
    state: [u64; STATE_WORDS],
    buf: [u8; 256],
    buf_len: usize,
    #[zeroize(skip)]
    _variant: core::marker::PhantomData<V>,
}

impl<V: Ysc3Variant> Default for Hasher<V> {
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

impl<V: Ysc3Variant> Hasher<V> {
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

    /// XOF 종료 및 squeeze 시작.
    pub fn finalize_xof(mut self) -> Reader<V> {
        let rate = V::RATE_BYTES;
        // SHA-3 식 패딩.
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

/// XOF squeeze 단계.
#[derive(Clone, Zeroize, ZeroizeOnDrop)]
pub struct Reader<V: Ysc3Variant> {
    state: [u64; STATE_WORDS],
    pos: usize,
    #[zeroize(skip)]
    _variant: core::marker::PhantomData<V>,
}

impl<V: Ysc3Variant> Reader<V> {
    /// 임의 길이의 출력 읽기.
    pub fn read(&mut self, mut out: &mut [u8]) {
        let rate = V::RATE_BYTES;
        while !out.is_empty() {
            if self.pos == rate {
                permute(&mut self.state, V::ROUNDS_BLOCK);
                self.pos = 0;
            }
            // 현재 state의 rate에서 (self.pos..rate)만큼 출력.
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
    use crate::stream::Ysc3_128;

    #[test]
    fn xof_deterministic() {
        let mut h1 = Hasher::<Ysc3_128>::new();
        h1.update(b"hello");
        let mut r1 = h1.finalize_xof();
        let mut o1 = [0u8; 32];
        r1.read(&mut o1);

        let mut h2 = Hasher::<Ysc3_128>::new();
        h2.update(b"hello");
        let mut r2 = h2.finalize_xof();
        let mut o2 = [0u8; 32];
        r2.read(&mut o2);

        assert_eq!(o1, o2);
    }

    #[test]
    fn xof_changes_with_input() {
        let mut h1 = Hasher::<Ysc3_128>::new();
        h1.update(b"hello");
        let mut o1 = [0u8; 32];
        h1.finalize_xof().read(&mut o1);

        let mut h2 = Hasher::<Ysc3_128>::new();
        h2.update(b"world");
        let mut o2 = [0u8; 32];
        h2.finalize_xof().read(&mut o2);

        assert_ne!(o1, o2);
    }

    #[test]
    fn xof_extends_consistently() {
        let mut h = Hasher::<Ysc3_128>::new();
        h.update(b"streaming squeeze");
        let mut reader = h.finalize_xof();
        let mut full = [0u8; 128];
        reader.read(&mut full);

        let mut h = Hasher::<Ysc3_128>::new();
        h.update(b"streaming squeeze");
        let mut reader = h.finalize_xof();
        let mut a = [0u8; 32];
        let mut b = [0u8; 96];
        reader.read(&mut a);
        reader.read(&mut b);

        assert_eq!(&full[..32], &a);
        assert_eq!(&full[32..], &b);
    }
}
