//! YSC5 XOF (Extendable Output Function). SPEC §7.3.

use crate::consts::{domain, STATE_WORDS};
use crate::farfalle::{transition, Compressor, Expander, Ysc5Variant};
use ysc4::permutation::permute;

/// XOF: keyless extendable hash. zero key + 도메인 분리자.
///
/// Compressor의 `ZeroizeOnDrop`이 내부 상태 zeroize를 담당. Hasher 자체는
/// finalize 단계에서 inner를 move하기 위해 Drop을 구현하지 않는다.
#[derive(Clone)]
pub struct Hasher<V: Ysc5Variant> {
    compressor: Compressor<V>,
}

impl<V: Ysc5Variant> Default for Hasher<V> {
    fn default() -> Self {
        // zero key를 capacity에 배치한 dummy seed 생성
        let mut state = [0u64; STATE_WORDS];
        state[STATE_WORDS - 1] ^= domain::XOF;
        permute(&mut state, V::ROUNDS_C);
        Self {
            compressor: Compressor::<V>::new(&state),
        }
    }
}

impl<V: Ysc5Variant> Hasher<V> {
    /// 새 해셔.
    pub fn new() -> Self {
        Self::default()
    }

    /// 메시지 흡수.
    pub fn update(&mut self, data: &[u8]) {
        self.compressor.absorb(data);
    }

    /// 종료 및 squeeze 시작.
    pub fn finalize_xof(self) -> Reader<V> {
        let (y, end_mask) = self.compressor.finish();
        let y_prime = transition::<V>(&y, &end_mask);
        Reader {
            expander: Expander::<V>::new(&y_prime),
        }
    }
}

/// XOF squeeze.
#[derive(Clone)]
pub struct Reader<V: Ysc5Variant> {
    expander: Expander<V>,
}

impl<V: Ysc5Variant> Reader<V> {
    /// 임의 길이 출력 읽기.
    pub fn read(&mut self, out: &mut [u8]) {
        self.expander.squeeze(out);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::farfalle::Ysc5_128;

    #[test]
    fn xof_deterministic() {
        let mut h1 = Hasher::<Ysc5_128>::new();
        h1.update(b"hello");
        let mut o1 = [0u8; 32];
        h1.finalize_xof().read(&mut o1);

        let mut h2 = Hasher::<Ysc5_128>::new();
        h2.update(b"hello");
        let mut o2 = [0u8; 32];
        h2.finalize_xof().read(&mut o2);

        assert_eq!(o1, o2);
    }

    #[test]
    fn xof_distinct_input() {
        let mut h1 = Hasher::<Ysc5_128>::new();
        h1.update(b"hello");
        let mut o1 = [0u8; 32];
        h1.finalize_xof().read(&mut o1);

        let mut h2 = Hasher::<Ysc5_128>::new();
        h2.update(b"world");
        let mut o2 = [0u8; 32];
        h2.finalize_xof().read(&mut o2);

        assert_ne!(o1, o2);
    }

    #[test]
    fn xof_extends_consistently() {
        let mut h = Hasher::<Ysc5_128>::new();
        h.update(b"test");
        let mut reader = h.finalize_xof();
        let mut full = [0u8; 128];
        reader.read(&mut full);

        let mut h = Hasher::<Ysc5_128>::new();
        h.update(b"test");
        let mut reader = h.finalize_xof();
        let mut a = [0u8; 32];
        let mut b = [0u8; 96];
        reader.read(&mut a);
        reader.read(&mut b);

        assert_eq!(&full[..32], &a);
        assert_eq!(&full[32..], &b);
    }
}
