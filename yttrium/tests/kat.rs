//! yttrium KAT (known-answer test) — 변형 패밀리별 고정 벡터.
//!
//! ⚠ **v0.2-pre, 미동결(R4 전)**: 파라미터(라운드·σ-power·F·RC·도메인·엔디안) 변경 시
//! 벡터 재생성 필요. 동결 시 PARAM_VERSION 부여 + 교차구현 대조. `print_kat`로 재생성.

use yttrium::{hash, Rounds, YttriumBuilder, PARAM_VERSION};

/// 동결 tripwire: KAT 벡터는 이 PARAM_VERSION에 묶인다. 파라미터(F·σ·ε·π·GF·RC·도메인·
/// 엔디안·변형) 변경 시 digest가 바뀌어 kat_unkeyed가 깨지므로 **버전 bump + 벡터 재생성**
/// 이 강제된다. 이 상수가 바뀌었는데 KAT 그대로면 동결 규율 위반.
#[test]
fn frozen_param_version() {
    assert_eq!(PARAM_VERSION, "yttrium-params-v0.2-pre",
        "PARAM_VERSION 변경 시 KAT 벡터 재생성(print_kat) 후 본 상수도 갱신할 것");
}

fn hx(d: &[u8; 16]) -> String {
    d.iter().map(|b| format!("{:02x}", b)).collect()
}

/// 벡터 재생성용 (ignored — `cargo test --test kat print_kat -- --ignored --nocapture`).
#[test]
#[ignore]
fn print_kat() {
    let variants = [
        ("yttrium-(8,12,24)", Rounds::V8_12_24),
        ("yttrium-(10,14,24)", Rounds::V10_14_24),
        ("yttrium-(4,6,12)", Rounds::V4_6_12),
        ("yttrium-(4,6,8)", Rounds::V4_6_8),
    ];
    let inputs: [(&str, Vec<u8>); 5] = [
        ("empty", vec![]),
        ("abc", b"abc".to_vec()),
        ("32B", vec![0x5a; 32]),
        ("1024B", vec![0xa5; 1024]),
        ("5000B", vec![0xc3; 5000]),
    ];
    for (vn, rd) in &variants {
        for (inm, data) in &inputs {
            println!("{:18} {:8} {}", vn, inm, hx(&hash(data, *rd)));
        }
    }
}

/// (variant, 입력설명, 입력생성, 기대 digest hex)
struct Kat {
    rd: Rounds,
    make: fn() -> Vec<u8>,
    want: &'static str,
}

const KATS: &[Kat] = &[
    // yttrium-(8,12,24) — 기본 unkeyed
    Kat { rd: Rounds::V8_12_24, make: || vec![],            want: "de15759160da1cc0547d71a38ce11df6" },
    Kat { rd: Rounds::V8_12_24, make: || b"abc".to_vec(),   want: "97344bc21652deaab3e1feba76e82990" },
    Kat { rd: Rounds::V8_12_24, make: || vec![0x5a; 32],    want: "84803061e6a52d7b3bfa2e8653e0dc8a" },
    Kat { rd: Rounds::V8_12_24, make: || vec![0xa5; 1024],  want: "5a8337a723b8cc12432bea3c8c391ca6" },
    Kat { rd: Rounds::V8_12_24, make: || vec![0xc3; 5000],  want: "59b40b6731517a4eeec03b45485ae51e" },
    // yttrium-(10,14,24) — 보수
    Kat { rd: Rounds::V10_14_24, make: || vec![],           want: "21d3c942a2516d1d7a80744bf80d0d71" },
    Kat { rd: Rounds::V10_14_24, make: || b"abc".to_vec(),  want: "d5c47ff4d0402d173993d15e0c2834f3" },
    Kat { rd: Rounds::V10_14_24, make: || vec![0xc3; 5000], want: "3485aa3f9223159172d788045c098553" },
    // yttrium-(4,6,12) — keyed-lite
    Kat { rd: Rounds::V4_6_12, make: || vec![],             want: "233610f30ee793d51e8e2a60ff3eb633" },
    Kat { rd: Rounds::V4_6_12, make: || b"abc".to_vec(),    want: "6934568053f3b73274039ad8a32ebc81" },
    Kat { rd: Rounds::V4_6_12, make: || vec![0xc3; 5000],   want: "f99425a2a5646fda0658d6a8e0247eb0" },
    // yttrium-(4,6,8) — lite
    Kat { rd: Rounds::V4_6_8, make: || vec![],              want: "d2d461c6851f231826add0dfe74dbc3d" },
    Kat { rd: Rounds::V4_6_8, make: || b"abc".to_vec(),     want: "97f36207ea011c3e50777f7d03a79f4e" },
    Kat { rd: Rounds::V4_6_8, make: || vec![0xa5; 1024],    want: "b78cbab1e227f9521684c494cf28f78c" },
    Kat { rd: Rounds::V4_6_8, make: || vec![0xc3; 5000],    want: "ebd786823004827a49a881823fd57ac4" },
];

#[test]
fn kat_unkeyed() {
    for (i, k) in KATS.iter().enumerate() {
        let got = hx(&hash(&(k.make)(), k.rd));
        assert_eq!(got, k.want, "KAT #{i} mismatch ({:?})", k.rd);
    }
}

#[test]
fn kat_keyed() {
    let mut h = YttriumBuilder::keyed(b"k", Rounds::V4_6_12).build_hasher();
    h.update(b"abc");
    assert_eq!(hx(&h.finalize()), "0ee03302ae1f40cf1f90bbb88d764bbd");
}

/// 스트리밍 update 분할이 한번에-update와 동일 (incremental 일관성).
#[test]
fn kat_streaming_consistency() {
    let data = vec![0xc3u8; 5000];
    let one = hash(&data, Rounds::V8_12_24);
    let mut h = YttriumBuilder::unkeyed(Rounds::V8_12_24).build_hasher();
    for chunk in data.chunks(37) {
        h.update(chunk);
    }
    assert_eq!(h.finalize(), one, "streaming != one-shot");
}
