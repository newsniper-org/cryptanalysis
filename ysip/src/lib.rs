//! # YSip — yttrium RAR 코어 기반 경량 keyed PRF (SipHash-class)
//!
//! **파생 설계**: yttrium(not -large)의 결합기 전체(G = 영합 reduction · F · all-8 σ)는
//! 추출이 곤란하다(상호 결합). 그러나 그 *코어 ARX 프리미티브* `rar(x,y) = ROTR_β(ROTL_α(x) ⊞ y)`
//! (SPECK 빌딩블록류, (α,β)=(8,9))만 떼어내면 SipHash의 가산-회전 믹싱을 대체하는 경량
//! PRF를 구성할 수 있다 (`milp/rar_avalanche.py` 확산 평가에서 SipRound와 comparable 확인).
//!
//! YSip = **SipHash 구성**(키 흡수/finalize 프레이밍·메시지 워드 패딩 그대로) +
//! **RAR 믹싱**(SipRound의 `⊞`를 `rar`로 치환, SipHash 회전상수 13/16/21/17/32 유지).
//! 도메인분리: IV를 SipHash의 ASCII 상수 대신 **SHA-512 IV 상위 4워드**(NUMS)로 둔다.
//!
//! - 상태: 4 × u64 = 256 bit. 키: 128 bit. 출력: 64 bit.
//! - 변형: `YSip-2-4`(c=2,d=4, 기본) / `YSip-3-6`(c=3,d=6, 보수).
//! - `no_std` (alloc 불요). `unsafe` 없음.
//!
//! ⚠ **v0.1-pre**: 자체 암호분석(차분·선형·회전·상수·라운드수, 적대검증 통과 —
//! `milp/ysip-residual-obligations.md`) 처리 완료. 차분축은 SipHash 대비 per-round 우위
//! (정확 R2 weight 7>4), 회전은 동급, 상수 (8,9)는 후보 중 SMT-exact 최강. 단 **외부 검토 전**
//! (`-pre`) + 멀티라운드 linear-hull·절대 trail 경계는 open. **운영 사용 금지.** SipHash 보안논증을
//! 그대로 상속하지 않으며(구성은 동일하나 결합기 상이), 라운드수는 SipHash 상대 정당화다.

#![cfg_attr(not(feature = "std"), no_std)]
#![forbid(unsafe_code)]

use core::hash::Hasher;

// ===================================================================================
// §1. 파라미터
// ===================================================================================

/// 동결 파라미터 버전. 이 문자열 ∧ (c,d)가 같으면 출력이 bit-exact 재현된다
/// (rar 상수 (α,β)·SipHash 회전상수·IV·엔디안·패딩 고정). 교차구현 KAT: `tests/kat.rs`
/// ≡ `ref_check.py`. 자체 암호분석(차분/선형/회전/상수/라운드수): `milp/ysip-residual-obligations.md`.
/// ⚠ `-pre` = **외부 검토 전** 동결 (자체 의무는 처리 완료; yttrium v0.2-pre 와 동일 규율).
pub const PARAM_VERSION: &str = "ysip-params-v0.1-pre";

/// rar 회전 (α,β) = (8,9) — yttrium 결합기와 동일.
const ROT_A: u32 = 8;
const ROT_B: u32 = 9;

/// SipHash 라운드 회전상수 (믹싱 위상 유지를 위해 그대로 차용).
const R1: u32 = 13;
const R2: u32 = 16;
const R3: u32 = 21;
const R4: u32 = 17;
const RX: u32 = 32;

/// IV = SHA-512 초기 해시값 상위 4워드 (NUMS: 첫 소수들의 √의 소수부).
/// SipHash의 "somepseudorandomlygeneratedbytes" ASCII 상수와 도메인분리.
const IV0: u64 = 0x6a09_e667_f3bc_c908;
const IV1: u64 = 0xbb67_ae85_84ca_a73b;
const IV2: u64 = 0x3c6e_f372_fe94_f82b;
const IV3: u64 = 0xa54f_f53a_5f1d_36f1;

/// 기본 변형 (c,d) = (2,4) — SipHash-2-4 대응.
pub const ROUNDS_2_4: (usize, usize) = (2, 4);
/// 보수 변형 (c,d) = (3,6) — 라운드 마진.
pub const ROUNDS_3_6: (usize, usize) = (3, 6);

// ===================================================================================
// §2. RAR 코어 + 라운드
// ===================================================================================

/// 코어 ARX 프리미티브: `rar(x,y) = ROTR_β(ROTL_α(x) ⊞ y)`. y 고정 시 x에 대해 가역
/// (x = ROTR_α(ROTL_β(z) ⊟ y)) — SipRound와 동일하게 라운드가 순열을 이룬다.
#[inline(always)]
const fn rar(x: u64, y: u64) -> u64 {
    x.rotate_left(ROT_A).wrapping_add(y).rotate_right(ROT_B)
}

/// YSip 라운드: SipRound 구조에서 `⊞`를 `rar`로 치환 (회전상수 13/16/21/17/32 유지).
#[inline(always)]
fn ysip_round(v: &mut [u64; 4]) {
    v[0] = rar(v[0], v[1]);
    v[1] = v[1].rotate_left(R1);
    v[1] ^= v[0];
    v[0] = v[0].rotate_left(RX);
    v[2] = rar(v[2], v[3]);
    v[3] = v[3].rotate_left(R2);
    v[3] ^= v[2];
    v[0] = rar(v[0], v[3]);
    v[3] = v[3].rotate_left(R3);
    v[3] ^= v[0];
    v[2] = rar(v[2], v[1]);
    v[1] = v[1].rotate_left(R4);
    v[1] ^= v[2];
    v[2] = v[2].rotate_left(RX);
}

#[inline(always)]
fn apply_rounds(v: &mut [u64; 4], n: usize) {
    for _ in 0..n {
        ysip_round(v);
    }
}

#[inline(always)]
fn load_u64_le(buf: &[u8], i: usize) -> u64 {
    let mut b = [0u8; 8];
    b.copy_from_slice(&buf[i..i + 8]);
    u64::from_le_bytes(b)
}

/// 부분 워드(0..8바이트) LE 로드.
#[inline(always)]
fn tail_u64_le(buf: &[u8], start: usize, len: usize) -> u64 {
    let mut out = 0u64;
    let mut j = 0;
    while j < len {
        out |= (buf[start + j] as u64) << (8 * j);
        j += 1;
    }
    out
}

// ===================================================================================
// §3. 스트리밍 PRF (core::hash::Hasher 구현 — HashMap drop-in)
// ===================================================================================

/// YSip 스트리밍 상태. `Hasher`를 구현하므로 `BuildHasher`로 감싸 HashMap에 쓸 수 있다.
#[derive(Clone)]
pub struct YSip {
    c: usize,
    d: usize,
    v0: u64,
    v1: u64,
    v2: u64,
    v3: u64,
    tail: u64,
    ntail: usize,
    length: usize,
}

impl YSip {
    /// 128-bit 키 + 변형 (c,d)로 초기화. 키는 리틀엔디안 16바이트.
    pub fn new_with_key_and_rounds(key: &[u8; 16], c: usize, d: usize) -> Self {
        let k0 = load_u64_le(key, 0);
        let k1 = load_u64_le(key, 8);
        YSip {
            c,
            d,
            v0: IV0 ^ k0,
            v1: IV1 ^ k1,
            v2: IV2 ^ k0,
            v3: IV3 ^ k1,
            tail: 0,
            ntail: 0,
            length: 0,
        }
    }

    /// 기본 변형 YSip-2-4.
    #[inline]
    pub fn new(key: &[u8; 16]) -> Self {
        Self::new_with_key_and_rounds(key, ROUNDS_2_4.0, ROUNDS_2_4.1)
    }

    /// 보수 변형 YSip-3-6.
    #[inline]
    pub fn new_conservative(key: &[u8; 16]) -> Self {
        Self::new_with_key_and_rounds(key, ROUNDS_3_6.0, ROUNDS_3_6.1)
    }

    /// 원샷: 키·변형·메시지 → 64-bit 태그.
    pub fn oneshot(key: &[u8; 16], c: usize, d: usize, data: &[u8]) -> u64 {
        let mut h = Self::new_with_key_and_rounds(key, c, d);
        h.write(data);
        h.finish()
    }

    #[inline]
    fn v(&self) -> [u64; 4] {
        [self.v0, self.v1, self.v2, self.v3]
    }
}

impl Hasher for YSip {
    fn write(&mut self, msg: &[u8]) {
        let length = msg.len();
        self.length = self.length.wrapping_add(length);

        let mut v = self.v();
        let mut needed = 0;

        // 직전 호출에서 남은 부분 워드를 먼저 채운다.
        if self.ntail != 0 {
            needed = 8 - self.ntail;
            if length < needed {
                self.tail |= tail_u64_le(msg, 0, length) << (8 * self.ntail);
                self.ntail += length;
                return;
            }
            let m = self.tail | (tail_u64_le(msg, 0, needed) << (8 * self.ntail));
            v[3] ^= m;
            apply_rounds(&mut v, self.c);
            v[0] ^= m;
            self.ntail = 0;
            self.tail = 0;
        }

        let len = length - needed;
        let left = len & 0x7;
        let mut i = needed;
        while i < length - left {
            let mi = load_u64_le(msg, i);
            v[3] ^= mi;
            apply_rounds(&mut v, self.c);
            v[0] ^= mi;
            i += 8;
        }
        self.tail = tail_u64_le(msg, i, left);
        self.ntail = left;

        self.v0 = v[0];
        self.v1 = v[1];
        self.v2 = v[2];
        self.v3 = v[3];
    }

    fn finish(&self) -> u64 {
        let mut v = self.v();
        // 마지막 워드: 하위에 잔여 바이트, 최상위 바이트에 length mod 256.
        let b = ((self.length as u64 & 0xff) << 56) | self.tail;
        v[3] ^= b;
        apply_rounds(&mut v, self.c);
        v[0] ^= b;
        v[2] ^= 0xff;
        apply_rounds(&mut v, self.d);
        v[0] ^ v[1] ^ v[2] ^ v[3]
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tag(key: &[u8; 16], data: &[u8]) -> u64 {
        YSip::oneshot(key, 2, 4, data)
    }

    #[test]
    fn determinism() {
        let key = [0x11u8; 16];
        let msg = b"the quick brown fox";
        assert_eq!(tag(&key, msg), tag(&key, msg));
    }

    #[test]
    fn streaming_equals_oneshot() {
        let key = [0x42u8; 16];
        let msg: [u8; 40] = core::array::from_fn(|i| i as u8);
        let one = YSip::oneshot(&key, 2, 4, &msg);
        // 임의 분할 스트리밍이 원샷과 동일해야.
        for split in [0usize, 1, 3, 7, 8, 9, 15, 16, 23, 32, 39] {
            let mut h = YSip::new(&key);
            h.write(&msg[..split]);
            h.write(&msg[split..]);
            assert_eq!(h.finish(), one, "split={split}");
        }
    }

    #[test]
    fn distinct_keys_differ() {
        let msg = b"same message";
        let a = tag(&[0u8; 16], msg);
        let b = tag(&[1u8; 16], msg);
        assert_ne!(a, b);
    }

    #[test]
    fn distinct_messages_differ() {
        let key = [0x7eu8; 16];
        assert_ne!(tag(&key, b"alpha"), tag(&key, b"beta"));
    }

    #[test]
    fn empty_message_well_defined() {
        let key = [0x99u8; 16];
        let a = tag(&key, b"");
        let b = tag(&key, b"");
        assert_eq!(a, b);
        // 빈 메시지와 1바이트 메시지는 length 패딩으로 구분돼야.
        assert_ne!(a, tag(&key, b"\x00"));
    }

    #[test]
    fn rar_invertible() {
        // rar(x,y)는 y 고정 시 x에 대해 가역 (라운드 순열성의 토대).
        for &x in &[0u64, 1, 0xdead_beef_cafe_babe, u64::MAX] {
            for &y in &[0u64, 7, 0x0123_4567_89ab_cdef] {
                let z = rar(x, y);
                let xr = z.rotate_left(ROT_B).wrapping_sub(y).rotate_right(ROT_A);
                assert_eq!(xr, x, "rar 역산 실패 x={x:#x} y={y:#x}");
            }
        }
    }

    /// 1-bit 입력차분 avalanche: finalize 출력 64bit가 ~32bit 뒤집혀야 (완전확산).
    /// 실제 구현 기준 측정(파이썬 스크립트보다 권위적). 결정적 LCG로 시드.
    #[test]
    fn avalanche_full_diffusion() {
        let key = [0x5au8; 16];
        let trials = 2000u64;
        let mut state = 0x1234_5678_9abc_def0u64;
        let mut next = || {
            // SplitMix64
            state = state.wrapping_add(0x9e37_79b9_7f4a_7c15);
            let mut z = state;
            z = (z ^ (z >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
            z = (z ^ (z >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
            z ^ (z >> 31)
        };
        let mut flips: u64 = 0;
        let mut samples: u64 = 0;
        let mut worst_bias = 0.0f64;
        let mut per_bit = [0u64; 64];
        for _ in 0..trials {
            let m = next();
            let base = tag(&key, &m.to_le_bytes());
            for bit in 0..64u32 {
                let md = (m ^ (1u64 << bit)).to_le_bytes();
                let d = base ^ tag(&key, &md);
                let hw = d.count_ones() as u64;
                flips += hw;
                samples += 1;
                for (ob, slot) in per_bit.iter_mut().enumerate() {
                    *slot += (d >> ob) & 1;
                }
            }
        }
        let mean = flips as f64 / samples as f64;
        for &count in per_bit.iter() {
            let p = count as f64 / samples as f64;
            worst_bias = worst_bias.max((p - 0.5).abs());
        }
        // YSip-2-4 (c=2): finalize d=4 라운드까지 거치므로 완전확산 기대.
        assert!(mean > 30.0 && mean < 34.0, "평균 flip {mean} (기대 ~32)");
        assert!(
            worst_bias < 0.05,
            "worst per-bit bias {worst_bias} (기대 <0.05)"
        );
    }
}
