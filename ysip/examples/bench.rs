//! 처리량 벤치 — YSip(RAR 믹싱) vs SipHash. 동일 입력·키·64-bit 출력.
//!
//! 가치제안 검증: "SipHash-class 속도". YSip 라운드는 SipRound의 `⊞`를 `rar`(회전 2회 추가)로
//! 치환하므로 라운드당 회전이 늘어 SipHash보다 느릴 것으로 예상 — 그 격차를 정량화한다.
//! YSip는 **scalar 레퍼런스**(SIMD 없음), siphasher도 scalar라 비교적 공정.
//!
//! 실행: cargo run --release --example bench -p ysip

use std::hash::Hasher as _;
use std::time::Instant;
use ysip::YSip;

fn mkinput(n: usize) -> Vec<u8> {
    let mut s = 0x0123_4567_89ab_cdefu64;
    let mut v = vec![0u8; n];
    for c in v.iter_mut() {
        s = s.wrapping_add(0x9E3779B97F4A7C15);
        let mut z = s;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58476D1CE4E5B9);
        z ^= z >> 31;
        *c = z as u8;
    }
    v
}

fn tput(label: &str, len: usize, mut f: impl FnMut()) {
    f(); // warmup
    let mut iters = 0u64;
    let t0 = Instant::now();
    loop {
        f();
        iters += 1;
        if t0.elapsed().as_secs_f64() >= 0.5 {
            break;
        }
    }
    let secs = t0.elapsed().as_secs_f64();
    let mbps = (len as f64 * iters as f64) / 1e6 / secs;
    println!("    {label:30} {mbps:9.1} MB/s");
}

fn main() {
    let n = 1 << 20; // 1 MiB
    let data = mkinput(n);
    let (k0, k1) = (0x0706050403020100u64, 0x0f0e0d0c0b0a0908u64);
    let key16 = {
        let mut k = [0u8; 16];
        k[..8].copy_from_slice(&k0.to_le_bytes());
        k[8..].copy_from_slice(&k1.to_le_bytes());
        k
    };

    println!(
        "== key=128b, out=64b : SipHash vs YSip (입력 {} KiB) ==",
        n / 1024
    );

    tput("SipHash-1-3", n, || {
        let mut h = siphasher::sip::SipHasher13::new_with_keys(k0, k1);
        h.write(&data);
        std::hint::black_box(h.finish());
    });
    tput("SipHash-2-4", n, || {
        let mut h = siphasher::sip::SipHasher::new_with_keys(k0, k1);
        h.write(&data);
        std::hint::black_box(h.finish());
    });

    tput("YSip-2-4 (RAR)", n, || {
        let mut h = YSip::new(&key16);
        h.write(&data);
        std::hint::black_box(h.finish());
    });
    tput("YSip-3-6 (RAR, conservative)", n, || {
        let mut h = YSip::new_conservative(&key16);
        h.write(&data);
        std::hint::black_box(h.finish());
    });

    // ---- 짧은 입력 (SipHash 본래 용도: HashMap 키 등) — per-call init+finalize 지배 ----
    println!("\n== 짧은 입력 ns/hash (SipHash 핵심 용도; init+finalize 비용 지배) ==");
    for sz in [8usize, 16, 32, 64] {
        let s = mkinput(sz);
        println!("  -- {sz} bytes --");
        lat("SipHash-2-4", &s, || {
            let mut h = siphasher::sip::SipHasher::new_with_keys(k0, k1);
            h.write(&s);
            std::hint::black_box(h.finish());
        });
        lat("YSip-2-4", &s, || {
            let mut h = YSip::new(&key16);
            h.write(&s);
            std::hint::black_box(h.finish());
        });
        lat("YSip-3-6", &s, || {
            let mut h = YSip::new_conservative(&key16);
            h.write(&s);
            std::hint::black_box(h.finish());
        });
    }

    println!("\n(YSip=scalar 레퍼런스, v0.1-pre. 절대수치 아닌 상대 비교용.)");
}

/// 짧은 입력 지연: 다회 반복으로 ns/hash 산출.
fn lat(label: &str, data: &[u8], mut f: impl FnMut()) {
    for _ in 0..1000 {
        f(); // warmup
    }
    let mut iters = 0u64;
    let t0 = Instant::now();
    loop {
        for _ in 0..2000 {
            f();
        }
        iters += 2000;
        if t0.elapsed().as_secs_f64() >= 0.3 {
            break;
        }
    }
    let ns = t0.elapsed().as_secs_f64() * 1e9 / iters as f64;
    let _ = data;
    println!("    {label:30} {ns:7.1} ns/hash");
}
