//! YSC5 — Farfalle PRF/Stream/AEAD/XOF/MAC on YSC4 σ-GLM permutation.
//!
//! 사양: `ysc5/SPEC.pdf` (Typst source: `ysc5/SPEC.typ`).
//! 핵심 산술: `ysc4::gf2_64::{alpha, alpha_pow}`, `ysc4::permutation::permute`.
//!
//! v0.1: PRF / Stream / AEAD / XOF / MAC 다섯 모드. Incremental compress 지원.

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

pub use farfalle::{Ysc5Variant, Ysc5_128, Ysc5_256};
pub use stream::{Ysc5_128Stream, Ysc5_256Stream};
