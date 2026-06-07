//! ypsilenti — downsized YHash variant.
//!
//! - 상태: 8 × u32 = 256 bit (YHash 1024 bit의 1/4)
//! - α-mult: GF(2³²) with p(x) = x³² + x²² + x² + x + 1 (Q1' 형식 검증됨)
//! - 라운드: R_b=4, R_c=6 (YHash의 절반)
//! - 트리 모드 유지, single-leaf fast path
//!
//! 형식 검증: `ypsilenti-verify/` (Q1', Q2', Y1'~Y4')
//! 사양: `ypsilenti/SPEC-draft.md`

#![cfg_attr(all(not(feature = "std"), not(test)), no_std)]
#![forbid(unsafe_code)]
#![allow(missing_docs)]

#[cfg(feature = "alloc")]
extern crate alloc;

pub mod consts;
pub mod gf32;
pub mod perm;
pub mod encode;
pub mod leaf;
pub mod tree;
pub mod hasher;
pub mod spawner;

pub use hasher::{YpsiHasher, YpsiBuilder, Digest};

#[cfg(feature = "ypsi-digest")]
pub mod digest_api;
