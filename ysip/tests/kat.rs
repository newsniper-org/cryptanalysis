//! YSip KAT (Known-Answer Tests) — 동결 벡터 + 교차구현 회귀가드.
//!
//! 벡터 출처: `examples/gen_kat.rs` (Rust) ≡ `ref_check.py` (독립 Python). 두 구현 bit-exact
//! 일치 확인됨(사양 무모호). `PARAM_VERSION` ∧ (c,d) 가 같으면 이 값들이 재현된다.
//!
//! ⚠ `-pre` = 외부 검토 전 동결. 자체 암호분석(차분/선형/회전/상수/라운드수)은
//! `milp/ysip-residual-obligations.md` 에서 처리 완료.

use std::hash::Hasher as _;
use ysip::YSip;

/// gen_kat.rs / ref_check.py 와 동일한 결정적 메시지.
fn msg(n: usize) -> Vec<u8> {
    (0..n).map(|i| ((i.wrapping_mul(0x9d)).wrapping_add(7)) as u8).collect()
}

const K00: [u8; 16] = [0u8; 16];
const KFF: [u8; 16] = [0xffu8; 16];
fn kseq() -> [u8; 16] {
    core::array::from_fn(|i| i as u8)
}

fn tag(key: &[u8; 16], c: usize, d: usize, n: usize) -> u64 {
    let mut h = YSip::new_with_key_and_rounds(key, c, d);
    h.write(&msg(n));
    h.finish()
}

#[test]
fn frozen_param_version() {
    // 파라미터 동결 tripwire — 의도치 않은 상수/구조 변경 차단.
    assert_eq!(ysip::PARAM_VERSION, "ysip-params-v0.1-pre");
}

#[test]
fn kat_ysip_2_4() {
    let ks = kseq();
    // (key, len, expected_u64) — 길이로직: 빈/부분워드/완전워드/멀티블록.
    let v: &[(&[u8; 16], usize, u64)] = &[
        (&K00, 0, 0x5e567352e0ecfede),
        (&K00, 8, 0xd994273b72dd3dba),
        (&K00, 9, 0x769c8c7562a094c5),
        (&K00, 32, 0x5133e10ca102601a),
        (&K00, 64, 0xab06753f706ae6a8),
        (&KFF, 0, 0x30f38ba668401650),
        (&KFF, 8, 0xa1dff150b07010cf),
        (&KFF, 9, 0xb98beb5ffc07b8b0),
        (&KFF, 32, 0xe39dc65355a8894b),
        (&KFF, 64, 0x4c3268bcedff88ff),
        (&ks, 0, 0xd30bf7cb1d04f931),
        (&ks, 8, 0x416d711626965cd8),
        (&ks, 9, 0x6168d7c79c3b2e8b),
        (&ks, 32, 0x096d4351278c5d6e),
        (&ks, 64, 0xdf75c4d0d166af15),
    ];
    for &(k, n, want) in v {
        assert_eq!(tag(k, 2, 4, n), want, "YSip-2-4 len={n}");
    }
}

#[test]
fn kat_ysip_3_6() {
    let ks = kseq();
    let v: &[(&[u8; 16], usize, u64)] = &[
        (&K00, 0, 0x449c3e6b2778aa05),
        (&K00, 8, 0x5b215051a517acde),
        (&K00, 9, 0x61ba07a73695c8bf),
        (&K00, 32, 0x02e068e6e0fceea4),
        (&K00, 64, 0xdaea2f2103e85b08),
        (&KFF, 0, 0xa139fd2c42fc3bfb),
        (&KFF, 8, 0xe44d99fc38520db1),
        (&KFF, 9, 0x11081fd7fddd9007),
        (&KFF, 32, 0x7e6f08345accef8b),
        (&KFF, 64, 0x942c98edec5cb09a),
        (&ks, 0, 0x1fef197f1f0d22de),
        (&ks, 8, 0xb80ea088fda945a9),
        (&ks, 9, 0x6bc7c36703665ab8),
        (&ks, 32, 0xe430fccdd5f3173f),
        (&ks, 64, 0x0eb974889185a1c6),
    ];
    for &(k, n, want) in v {
        assert_eq!(tag(k, 3, 6, n), want, "YSip-3-6 len={n}");
    }
}

/// 임의 분할 스트리밍이 원샷 KAT와 일치 (streaming ≡ oneshot, 모든 길이 경계).
#[test]
fn kat_streaming_consistency() {
    let ks = kseq();
    for n in [0usize, 1, 7, 8, 9, 15, 16, 31, 32, 63, 64] {
        let m = msg(n);
        let want = tag(&ks, 2, 4, n);
        for split in [0, 1, 5, 8, n / 2, n] {
            if split > n {
                continue;
            }
            let mut h = YSip::new(&ks);
            h.write(&m[..split]);
            h.write(&m[split..]);
            assert_eq!(h.finish(), want, "len={n} split={split}");
        }
    }
}
