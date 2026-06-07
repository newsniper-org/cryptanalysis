//! YSC4 — σ-Generalized Lai-Massey 기반 FHE 친화 스트림/AEAD/XOF 스위트.
//!
//! YSC3의 후속작으로, 순열만 σ-GLM으로 교체한 변종.
//! 모드 사양(stream/AEAD/XOF/MAC)은 YSC3와 동일한 sponge 패턴.
//!
//! 핵심 sleeve:
//! - 16-branch Lai-Massey: `T = F(⊕ᵢ Lᵢ)`, broadcast `Lᵢ ⊕ T`.
//! - σ-층: branches {0,4,8,12}에 GF(2⁶⁴) 위 `αᵏ·x` (k = 1,3,5,7)을 적용.
//! - π: `P[i] = (5i+7) mod 16` — 단일 16-cycle 워드 순열.

#![cfg_attr(all(not(feature = "std"), not(test)), no_std)]
#![cfg_attr(ysc4_simd_nightly, feature(portable_simd))]
#![forbid(unsafe_code)]
#![deny(missing_docs)]

#[cfg(feature = "alloc")]
extern crate alloc;

pub mod consts;
pub mod gf2_64;
pub mod permutation;
#[cfg(ysc4_simd_any)]
pub mod permutation_simd;
pub mod stream;

#[cfg(feature = "ysc4x")]
pub mod aead;

#[cfg(feature = "ysc4x")]
pub mod xof;

pub use stream::{Ysc4_128Stream, Ysc4_256Stream};
