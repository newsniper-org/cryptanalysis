//! YHash — Farfalle-tree hash function for HashMap/KV stores.
//!
//! 사양: `yhash/SPEC-draft.md`. 형식 검증: `yhash-verify/` (Y1~Y5).
//!
//! 핵심 설계:
//! - YSC4-p 순열 재사용 (1024-bit state)
//! - Tree-positional masks (Farfalle-tree 식)
//! - Single-leaf fast path: ≤ 1024 바이트 입력 (단일 leaf, 무-heap)
//! - Larger inputs: fixed-depth tree buffer (stack-only)
//! - 256-bit chaining value, 256-bit 또는 64-bit 출력 옵션
//!
//! **무-heap 디자인**: 모든 핵심 경로가 stack-only. `alloc` feature는 *optional*
//! (variable-length output 시).

#![cfg_attr(all(not(feature = "std"), not(test)), no_std)]
#![cfg_attr(feature = "nightly-portable-simd", feature(portable_simd))]
#![forbid(unsafe_code)]
#![deny(missing_docs)]

#[cfg(feature = "alloc")]
extern crate alloc;

pub mod consts;
pub mod encode;
pub mod perm;
#[cfg(any(feature = "nightly-portable-simd", feature = "stable-portable-simd"))]
pub mod perm_simd;
pub mod leaf;
pub mod tree;
pub mod hasher;
pub mod spawner;
#[cfg(feature = "alloc")]
pub mod parallel;

pub use hasher::{YHasher, YHashBuilder, Digest};

#[cfg(feature = "yhash-digest")]
pub mod digest_api;
