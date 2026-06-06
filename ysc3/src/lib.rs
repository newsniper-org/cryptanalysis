//! YSC3 — FHE 친화, S-box 미사용 스트림/AEAD/XOF 스위트.
//!
//! 모든 핵심 API는 `no_std` 환경에서 동작한다. `std` feature는 표준 라이브러리
//! 헬퍼 (e.g. `std::io::Write` 어댑터)를 제공하기 위한 *순수 어댑터* 용도이며,
//! 알고리즘 자체는 std에 의존하지 않는다.
//!
//! ```ignore
//! #[cfg(feature = "std")]
//! fn _why_std_is_optional() {
//!     // std feature가 꺼져 있어도 ysc3는 빌드되어야 한다.
//! }
//! ```

#![cfg_attr(all(not(feature = "std"), not(test)), no_std)]
#![cfg_attr(feature = "simd", feature(portable_simd))]
#![forbid(unsafe_code)]
#![deny(missing_docs)]

#[cfg(feature = "alloc")]
extern crate alloc;

pub mod consts;
pub mod permutation;
pub mod stream;

#[cfg(feature = "ysc3x")]
pub mod aead;

#[cfg(feature = "ysc3x")]
pub mod xof;

// --- 편의 타입 별칭 ---

pub use stream::{Ysc3_128Stream, Ysc3_256Stream};
