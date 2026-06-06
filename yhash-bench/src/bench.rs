//! 해시 비교 — keyed/unkeyed × throughput/per-call × 다양한 크기.
//!
//! **공정성**: HashMap 사용 패턴 모사 — builder는 한 번만 구축, hasher는 매 호출마다 생성.

use std::hash::Hasher;
use std::mem::size_of;
use std::time::Instant;

use yhash::YHashBuilder;
use ypsilenti::YpsiBuilder;
use ahash::{AHasher, RandomState};
use rustc_hash::FxHasher;
use siphasher::sip::SipHasher13;

// ---- 공통 throughput bench: builder/state 외부 주입, hash op만 측정 ----

fn bench_throughput<F>(name: &str, sizes: &[usize], iters: usize, mut hash_fn: F)
where
    F: FnMut(&[u8]) -> u64,
{
    println!("\n--- Throughput ({}): ---", name);
    for &size in sizes {
        let data = vec![0xABu8; size];
        for _ in 0..100 {
            std::hint::black_box(hash_fn(&data));
        }
        let t0 = Instant::now();
        for _ in 0..iters {
            std::hint::black_box(hash_fn(&data));
        }
        let elapsed = t0.elapsed();
        let total_bytes = (size as u64) * (iters as u64);
        let mb_per_sec = (total_bytes as f64) / elapsed.as_secs_f64() / 1e6;
        let ns_per_hash = elapsed.as_nanos() as f64 / iters as f64;
        println!(
            "  size={:>6} bytes: {:>9.2} MB/s  ({:>9.2} ns/hash)",
            size, mb_per_sec, ns_per_hash
        );
    }
}

fn bench_per_call(name: &str, key_lens: &[usize], iters: usize, mut hash_fn: impl FnMut(&[u8]) -> u64) {
    println!("\n--- Per-call cost ({}): ---", name);
    for &k in key_lens {
        let key = vec![0xCDu8; k];
        for _ in 0..100 {
            std::hint::black_box(hash_fn(&key));
        }
        let t0 = Instant::now();
        for _ in 0..iters {
            std::hint::black_box(hash_fn(&key));
        }
        let elapsed = t0.elapsed();
        let ns = elapsed.as_nanos() as f64 / iters as f64;
        println!("  key_len={:>4}: {:>8.2} ns/hash  ({:>8.0} K hash/s)",
                 k, ns, 1e6 / ns);
    }
}

// ---- state size ----

fn report_state_sizes() {
    println!("\n--- State size (Hasher instance) ---");
    println!("  YHasher (keyed)  : {:>5} bytes", size_of::<yhash::YHasher>());
    println!("  YpsiHasher       : {:>5} bytes", size_of::<ypsilenti::YpsiHasher>());
    println!("  AHasher          : {:>5} bytes", size_of::<AHasher>());
    println!("  FxHasher         : {:>5} bytes", size_of::<FxHasher>());
    println!("  SipHasher13      : {:>5} bytes", size_of::<SipHasher13>());
    println!("\n--- Builder size (BuildHasher, one per HashMap) ---");
    println!("  YHashBuilder     : {:>5} bytes", size_of::<YHashBuilder>());
    println!("  YpsiBuilder      : {:>5} bytes", size_of::<YpsiBuilder>());
    println!("  ahash::RandomState: {:>5} bytes", size_of::<RandomState>());
}

// ---- 빌더 공유 + hasher 매 호출 (= HashMap 패턴) ----

fn main() {
    println!("===== Hash 비교: keyed / unkeyed, HashMap 패턴 =====");
    println!("(builder는 한 번만 구축, hasher는 매 호출 생성)");

    report_state_sizes();

    let throughput_sizes: &[usize] = &[16, 64, 256, 1024, 4096, 65_536];
    let key_lens: &[usize] = &[4, 8, 16, 32, 64, 128];
    let iters_thru = 50_000;
    let iters_per = 500_000;

    // ---- YHash KEYED ----
    {
        let builder = YHashBuilder::keyed(b"bench-key-16byte");
        bench_throughput(
            "YHash (keyed)", throughput_sizes, iters_thru,
            |data| { let mut h = builder.build_hasher(); h.update(data); h.finalize_u64() },
        );
        bench_per_call(
            "YHash (keyed)", key_lens, iters_per,
            |data| { let mut h = builder.build_hasher(); h.update(data); h.finalize_u64() },
        );
    }

    // ---- YHash UNKEYED ----
    {
        let builder = YHashBuilder::unkeyed();
        bench_throughput(
            "YHash (unkeyed)", throughput_sizes, iters_thru,
            |data| { let mut h = builder.build_hasher(); h.update(data); h.finalize_u64() },
        );
        bench_per_call(
            "YHash (unkeyed)", key_lens, iters_per,
            |data| { let mut h = builder.build_hasher(); h.update(data); h.finalize_u64() },
        );
    }

    // ---- ypsilenti KEYED ----
    {
        let builder = YpsiBuilder::keyed(b"bench-key-16byte");
        bench_throughput(
            "ypsilenti (keyed)", throughput_sizes, iters_thru,
            |data| { let mut h = builder.build_hasher(); h.update(data); h.finalize_u64() },
        );
        bench_per_call(
            "ypsilenti (keyed)", key_lens, iters_per,
            |data| { let mut h = builder.build_hasher(); h.update(data); h.finalize_u64() },
        );
    }

    // ---- ypsilenti UNKEYED ----
    {
        let builder = YpsiBuilder::unkeyed();
        bench_throughput(
            "ypsilenti (unkeyed)", throughput_sizes, iters_thru,
            |data| { let mut h = builder.build_hasher(); h.update(data); h.finalize_u64() },
        );
        bench_per_call(
            "ypsilenti (unkeyed)", key_lens, iters_per,
            |data| { let mut h = builder.build_hasher(); h.update(data); h.finalize_u64() },
        );
    }

    // ---- ahash (RandomState로 builder 공유) ----
    {
        let rs = RandomState::with_seeds(0, 0, 0, 0);
        bench_throughput(
            "ahash", throughput_sizes, iters_thru,
            |data| { let mut h = rs.build_hasher(); h.write(data); h.finish() },
        );
        bench_per_call(
            "ahash", key_lens, iters_per,
            |data| { let mut h = rs.build_hasher(); h.write(data); h.finish() },
        );
    }

    // ---- FxHash (no builder, just new each time) ----
    bench_throughput(
        "FxHash", throughput_sizes, iters_thru,
        |data| { let mut h = FxHasher::default(); h.write(data); h.finish() },
    );
    bench_per_call(
        "FxHash", key_lens, iters_per,
        |data| { let mut h = FxHasher::default(); h.write(data); h.finish() },
    );

    // ---- SipHash13 (with shared keys) ----
    {
        let (k0, k1) = (0u64, 0u64);
        bench_throughput(
            "SipHash13 (keyed)", throughput_sizes, iters_thru,
            |data| { let mut h = SipHasher13::new_with_keys(k0, k1); h.write(data); h.finish() },
        );
        bench_per_call(
            "SipHash13 (keyed)", key_lens, iters_per,
            |data| { let mut h = SipHasher13::new_with_keys(k0, k1); h.write(data); h.finish() },
        );
    }

    println!("\n===== 핵심 비교 — 4-byte key per-call =====");
    println!("(별도 측정 결과, 위의 표 참고)");
}

use std::hash::BuildHasher;
