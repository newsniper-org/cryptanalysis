//! YSC5 Stream cipher — RustCrypto `StreamCipherCore` 구현.
//!
//! ```text
//! Ysc5_128StreamCipher = StreamCipherCoreWrapper<Ysc5StreamCore<Ysc5_128>>
//! ```

use crate::consts::{domain, STATE_WORDS};
use crate::farfalle::{
    key_setup, transition, Compressor, Expander, Ysc5Variant, Ysc5_128, Ysc5_256,
};
use cipher::{
    consts::{U24, U32, U64},
    typenum::Unsigned,
    Block, BlockSizeUser, Iv, IvSizeUser, Key, KeyIvInit, KeySizeUser, ParBlocksSizeUser,
    StreamBackend, StreamCipherCore, StreamCipherCoreWrapper, StreamCipherSeekCore, StreamClosure,
};
use zeroize::{Zeroize, ZeroizeOnDrop};

// --- 타입-수준 사이즈 매핑 ---
// (key/nonce/rate 모두 변종에 따라 다르므로 trait의 connected types로 노출)

/// RustCrypto-호환 stream cipher *core*.
///
/// 사용자는 보통 `StreamCipherCoreWrapper<Ysc5StreamCore<V>>` (= `Ysc5_128StreamCipher`
/// 등의 타입 alias)를 사용. Wrapper가 `StreamCipher` 고수준 trait들을 자동 제공.
#[derive(Clone, Zeroize, ZeroizeOnDrop)]
pub struct Ysc5StreamCore<V: Ysc5Variant> {
    /// transition 후의 Y' (expand seed).
    y_prime: [u64; STATE_WORDS],
    /// 현재 블록 카운터 (squeeze 위치).
    counter: u64,
    #[zeroize(skip)]
    _variant: core::marker::PhantomData<V>,
}

// ---- Ysc5_128 (rate=64, key=32, nonce=24) ----

impl KeySizeUser for Ysc5StreamCore<Ysc5_128> {
    type KeySize = U32;
}
impl IvSizeUser for Ysc5StreamCore<Ysc5_128> {
    type IvSize = U24;
}
impl BlockSizeUser for Ysc5StreamCore<Ysc5_128> {
    type BlockSize = U64;
}
impl ParBlocksSizeUser for Ysc5StreamCore<Ysc5_128> {
    type ParBlocksSize = cipher::consts::U1;
}

// ---- Ysc5_256 (rate=32, key=64, nonce=24) ----

impl KeySizeUser for Ysc5StreamCore<Ysc5_256> {
    type KeySize = U64;
}
impl IvSizeUser for Ysc5StreamCore<Ysc5_256> {
    type IvSize = U24;
}
impl BlockSizeUser for Ysc5StreamCore<Ysc5_256> {
    type BlockSize = U32;
}
impl ParBlocksSizeUser for Ysc5StreamCore<Ysc5_256> {
    type ParBlocksSize = cipher::consts::U1;
}

// ---- KeyIvInit ----

impl<V: Ysc5Variant> Ysc5StreamCore<V>
where
    Self: KeySizeUser + IvSizeUser,
{
    fn new_inner(key: &[u8], nonce: &[u8]) -> Self {
        // 길이 검사는 GenericArray 타입에 의해 컴파일 타임에 강제됨.
        let seed = key_setup::<V>(key, domain::STREAM)
            .expect("KeyIvInit: lengths guaranteed by GenericArray");
        let mut c = Compressor::<V>::new(&seed);
        c.absorb(nonce);
        let (y, end_mask) = c.finish();
        let y_prime = transition::<V>(&y, &end_mask);
        Self {
            y_prime,
            counter: 0,
            _variant: core::marker::PhantomData,
        }
    }
}

impl KeyIvInit for Ysc5StreamCore<Ysc5_128> {
    fn new(key: &Key<Self>, iv: &Iv<Self>) -> Self {
        Self::new_inner(key.as_slice(), iv.as_slice())
    }
}

impl KeyIvInit for Ysc5StreamCore<Ysc5_256> {
    fn new(key: &Key<Self>, iv: &Iv<Self>) -> Self {
        Self::new_inner(key.as_slice(), iv.as_slice())
    }
}

// ---- StreamCipherCore ----

/// 단일 블록 generation backend.
struct Ysc5Backend<'a, V: Ysc5Variant> {
    expander: Expander<V>,
    core: &'a mut Ysc5StreamCore<V>,
}

impl<'a, V: Ysc5Variant> BlockSizeUser for Ysc5Backend<'a, V>
where
    Ysc5StreamCore<V>: BlockSizeUser,
{
    type BlockSize = <Ysc5StreamCore<V> as BlockSizeUser>::BlockSize;
}

impl<'a, V: Ysc5Variant> ParBlocksSizeUser for Ysc5Backend<'a, V>
where
    Ysc5StreamCore<V>: BlockSizeUser,
{
    type ParBlocksSize = cipher::consts::U1;
}

impl<'a, V: Ysc5Variant> StreamBackend for Ysc5Backend<'a, V>
where
    Ysc5StreamCore<V>: BlockSizeUser,
    <Ysc5StreamCore<V> as BlockSizeUser>::BlockSize: Unsigned,
{
    #[inline]
    fn gen_ks_block(&mut self, block: &mut Block<Self>) {
        // Expander가 내부적으로 mask roll을 진행
        self.expander.squeeze(block.as_mut_slice());
        self.core.counter = self.core.counter.wrapping_add(1);
    }
}

impl StreamCipherCore for Ysc5StreamCore<Ysc5_128> {
    fn remaining_blocks(&self) -> Option<usize> {
        None
    }
    fn process_with_backend(&mut self, f: impl StreamClosure<BlockSize = Self::BlockSize>) {
        let expander = Expander::<Ysc5_128>::new(&self.y_prime);
        let mut backend = Ysc5Backend {
            expander,
            core: self,
        };
        // counter만큼 뛰어넘기
        let mut skip = backend.core.counter;
        let mut tmp = [0u8; 64];
        while skip > 0 {
            backend.expander.squeeze(&mut tmp[..Ysc5_128::RATE_BYTES]);
            skip -= 1;
        }
        f.call(&mut backend);
    }
}

impl StreamCipherCore for Ysc5StreamCore<Ysc5_256> {
    fn remaining_blocks(&self) -> Option<usize> {
        None
    }
    fn process_with_backend(&mut self, f: impl StreamClosure<BlockSize = Self::BlockSize>) {
        let expander = Expander::<Ysc5_256>::new(&self.y_prime);
        let mut backend = Ysc5Backend {
            expander,
            core: self,
        };
        let mut skip = backend.core.counter;
        let mut tmp = [0u8; 64];
        while skip > 0 {
            backend.expander.squeeze(&mut tmp[..Ysc5_256::RATE_BYTES]);
            skip -= 1;
        }
        f.call(&mut backend);
    }
}

// ---- StreamCipherSeekCore (seek 지원) ----

impl StreamCipherSeekCore for Ysc5StreamCore<Ysc5_128> {
    type Counter = u64;
    fn get_block_pos(&self) -> u64 {
        self.counter
    }
    fn set_block_pos(&mut self, pos: u64) {
        self.counter = pos;
    }
}

impl StreamCipherSeekCore for Ysc5StreamCore<Ysc5_256> {
    type Counter = u64;
    fn get_block_pos(&self) -> u64 {
        self.counter
    }
    fn set_block_pos(&mut self, pos: u64) {
        self.counter = pos;
    }
}

// --- 사용자-facing 타입 alias ---

/// RustCrypto convention: high-level stream cipher (`StreamCipher` trait 자동 구현).
pub type Ysc5_128StreamCipher = StreamCipherCoreWrapper<Ysc5StreamCore<Ysc5_128>>;
/// 256-비트 변종.
pub type Ysc5_256StreamCipher = StreamCipherCoreWrapper<Ysc5StreamCore<Ysc5_256>>;
