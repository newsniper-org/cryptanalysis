//! 처리량 벤치마크 — yttrium variants vs 표준 해시. 동일 입력 바이트스트림·키/출력 길이.
//!
//! ⚠ 공정성(필독): yttrium는 **scalar 레퍼런스**(SIMD/병렬 없음)이고 BLAKE3=SIMD·SHA3/SipHash=
//! 최적화 라이브러리 → **비대칭**. yttrium 수치는 *미최적화 레퍼런스*이지 알고리즘 잠재력 아님.
//! yttrium-large 라운드수는 *미확정*(§11) — u32 변형값 잠정 적용(provisional).
//!
//! 비교: (1) BLAKE3 vs yttrium-large (key 256b, out 128b)
//!       (2) SipHash vs yttrium (key 128b, out 64b)
//!       (3) SHA3-{256,384,512} vs yttrium-large (no key, out 256/384/512b)
//!
//! 실행: cargo run --release --example bench -p yttrium

use sha3::Digest as _;
use std::hash::Hasher as _;
use std::time::Instant;
use yttrium::large::YttriumLargeBuilder;
use yttrium::{Rounds, YttriumBuilder};

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

/// 적응형 throughput: 0.5s 이상 돌려 MB/s 산출(넓은 속도 범위 대응).
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
    println!("    {label:38} {mbps:9.1} MB/s");
}

const VARIANTS: [(&str, Rounds); 4] = [
    ("yttrium-(10,14,24)", Rounds::V10_14_24),
    ("yttrium-(8,12,24)", Rounds::V8_12_24),
    ("yttrium-(4,6,12)", Rounds::V4_6_12),
    ("yttrium-(4,6,8)", Rounds::V4_6_8),
];

fn main() {
    let n = 1 << 20; // 1 MiB 동일 입력
    let data = mkinput(n);
    println!("처리량 벤치 (입력 {} KiB 동일 바이트스트림; scalar 레퍼런스 caveat 위 참조)\n", n / 1024);

    // ---- (1) BLAKE3 vs yttrium-large : key 256b, out 128b ----
    println!("== (1) key=256b, out=128b : BLAKE3 vs yttrium-large ==");
    let key32 = [0x42u8; 32];
    tput("BLAKE3 (keyed, SIMD)", n, || {
        let h = blake3::keyed_hash(&key32, &data);
        std::hint::black_box(&h.as_bytes()[..16]);
    });
    for (name, rd) in VARIANTS {
        let b = YttriumLargeBuilder::keyed(&key32, rd);
        tput(&format!("{name}-large"), n, || {
            std::hint::black_box(b.hash(&data, 16));
        });
    }

    // ---- (2) SipHash vs yttrium(u32) : key 128b, out 64b ----
    println!("\n== (2) key=128b, out=64b : SipHash-2-4 vs yttrium ==");
    let (k0, k1) = (0x0706050403020100u64, 0x0f0e0d0c0b0a0908u64); // 128-bit key
    tput("SipHash-2-4", n, || {
        let mut h = siphasher::sip::SipHasher::new_with_keys(k0, k1);
        h.write(&data);
        std::hint::black_box(h.finish());
    });
    let key16 = [0x42u8; 16];
    for (name, rd) in VARIANTS {
        let b = YttriumBuilder::keyed(&key16, rd);
        tput(name, n, || {
            std::hint::black_box(&b.hash(&data)[..8]); // one-shot 배치, 64-bit
        });
    }

    // ---- (3) SHA3 vs yttrium-large : no key, out 256/384/512b ----
    for &(bits, ob) in &[(256usize, 32usize), (384, 48), (512, 64)] {
        println!("\n== (3) no key, out={bits}b : SHA3-{bits} vs yttrium-large ==");
        tput(&format!("SHA3-{bits}"), n, || {
            let out: Vec<u8> = match bits {
                256 => sha3::Sha3_256::digest(&data).to_vec(),
                384 => sha3::Sha3_384::digest(&data).to_vec(),
                _ => sha3::Sha3_512::digest(&data).to_vec(),
            };
            std::hint::black_box(out);
        });
        for (name, rd) in VARIANTS {
            let b = YttriumLargeBuilder::unkeyed(rd);
            tput(&format!("{name}-large"), n, || {
                std::hint::black_box(b.hash(&data, ob));
            });
        }
    }
    // ---- (4) 병렬(멀티스레드) — feature="parallel". 16 MiB로 스레드 오버헤드 amortize ----
    #[cfg(feature = "parallel")]
    {
        use yttrium::parallel::hash_parallel;
        use yttrium::spawner::{SerialSpawner, StdThreadSpawner};
        let big = mkinput(16 << 20);
        let cores = std::thread::available_parallelism().map(|n| n.get()).unwrap_or(1);
        println!("\n== (4) 병렬 트리 (16 MiB, {cores} cores; SIMD={}) ==", cfg!(feature = "simd"));
        let bu = YttriumBuilder::unkeyed(Rounds::V8_12_24);
        tput("yttrium-(8,12,24) serial(1-thread)", big.len(), || {
            std::hint::black_box(hash_parallel(&bu, &big, &SerialSpawner));
        });
        let sp = StdThreadSpawner::new();
        tput("yttrium-(8,12,24) parallel(std-thread)", big.len(), || {
            std::hint::black_box(hash_parallel(&bu, &big, &sp));
        });
    }

    println!("\n(주의: yttrium=scalar 레퍼런스·large 라운드수 잠정. 절대수치 아닌 상대·구조 비교용.)");
}
