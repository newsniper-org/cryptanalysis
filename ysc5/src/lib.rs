//! YSC5 — Farfalle PRF/Stream/AEAD/XOF/MAC on YSC4 σ-GLM permutation.
//!
//! 사양: `ysc5/SPEC.pdf` (Typst source: `ysc5/SPEC.typ`).
//! 핵심 산술: `ysc4::gf2_64::{alpha, alpha_pow}`, `ysc4::permutation::permute`.
//!
//! **RustCrypto convention**: 본 크레이트는 `cipher::StreamCipherCore`,
//! `aead::AeadInPlace`, `digest::Update`/`ExtendableOutput`/`Mac` traits를 구현.
//! 저수준 Farfalle primitives (`Compressor`, `Expander`)는 `farfalle` 모듈에 유지.

#![cfg_attr(all(not(feature = "std"), not(test)), no_std)]
#![cfg_attr(feature = "simd", feature(portable_simd))]
#![forbid(unsafe_code)]
#![deny(missing_docs)]

#[cfg(feature = "alloc")]
extern crate alloc;

pub mod consts;
pub mod roll;
pub mod farfalle;
pub mod stream;

#[cfg(feature = "ysc5x")]
pub mod aead;
#[cfg(feature = "ysc5x")]
pub mod xof;
#[cfg(feature = "ysc5x")]
pub mod mac;

// RustCrypto re-exports
pub use cipher;
#[cfg(feature = "ysc5x")]
pub use aead as aead_api;
#[cfg(feature = "ysc5x")]
pub use digest;

pub use farfalle::{Ysc5Variant, Ysc5_128, Ysc5_256};
pub use stream::{Ysc5_128StreamCipher, Ysc5_256StreamCipher};

#[cfg(feature = "ysc5x")]
pub use aead::{Ysc5_128Aead, Ysc5_256Aead};
#[cfg(feature = "ysc5x")]
pub use xof::{Ysc5_128Hasher, Ysc5_256Hasher};
#[cfg(feature = "ysc5x")]
pub use mac::{Ysc5_128Mac, Ysc5_256Mac};
