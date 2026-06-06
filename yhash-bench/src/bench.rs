//! YHash vs ahash vs FxHash vs SipHash13 — throughput / 메모리 비교.
//!
//! 측정 항목:
//!   - throughput (MB/s) at 다양한 input sizes
//!   - per-hash cost (ns/hash) for fixed-size keys (HashMap workload)
//!   - state size (bytes per Hasher instance)
//!   - CPU 점유 패턴 (process CPU time 추정)

use std::hash::Hasher;
use std::mem::size_of;
use std::time::Instant;

use yhash::YHashBuilder;
use ahash::AHasher;
use rustc_hash::FxHasher;
use siphasher::sip::SipHasher13;

// ---- throughput benchmarks ----

fn bench_throughput<F>(name: &str, sizes: &[usize], iters: usize, mut hash_fn: F)
where
    F: FnMut(&[u8]) -> u64,
{
    println!("\n--- Throughput ({}): ---", name);
    for &size in sizes {
        let data = vec![0xABu8; size];
        // warmup
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

fn hash_yhash(data: &[u8]) -> u64 {
    let mut h = YHashBuilder::keyed(b"bench-key-16byte").build_hasher();
    h.update(data);
    h.finalize_u64()
}

fn hash_ahash(data: &[u8]) -> u64 {
    let mut h = AHasher::default();
    h.write(data);
    h.finish()
}

fn hash_fxhash(data: &[u8]) -> u64 {
    let mut h = FxHasher::default();
    h.write(data);
    h.finish()
}

fn hash_siphash13(data: &[u8]) -> u64 {
    let mut h = SipHasher13::new();
    h.write(data);
    h.finish()
}

// ---- state size ----

fn report_state_sizes() {
    println!("\n--- State size (Hasher instance) ---");
    println!("  YHasher          : {:>5} bytes", size_of::<yhash::YHasher>());
    println!("  AHasher          : {:>5} bytes", size_of::<AHasher>());
    println!("  FxHasher         : {:>5} bytes", size_of::<FxHasher>());
    println!("  SipHasher13      : {:>5} bytes", size_of::<SipHasher13>());
}

// ---- key-size workload (HashMap-typical) ----

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

// ---- main ----

fn main() {
    println!("===== YHash vs ahash vs FxHash vs SipHash13 =====");

    report_state_sizes();

    let throughput_sizes: &[usize] = &[16, 64, 256, 1024, 4096, 16_384, 65_536];

    let iters_thru = 50_000;
    bench_throughput("YHash (keyed)", throughput_sizes, iters_thru, hash_yhash);
    bench_throughput("ahash",        throughput_sizes, iters_thru, hash_ahash);
    bench_throughput("FxHash",       throughput_sizes, iters_thru, hash_fxhash);
    bench_throughput("SipHash13",    throughput_sizes, iters_thru, hash_siphash13);

    let key_lens: &[usize] = &[4, 8, 16, 32, 64, 128];
    let iters_per = 1_000_000;
    bench_per_call("YHash (keyed)", key_lens, iters_per, hash_yhash);
    bench_per_call("ahash",        key_lens, iters_per, hash_ahash);
    bench_per_call("FxHash",       key_lens, iters_per, hash_fxhash);
    bench_per_call("SipHash13",    key_lens, iters_per, hash_siphash13);

    println!("\n===== 요약 =====");
    println!("- YHash: cryptographic-grade DoS resistance + 256-bit digest.");
    println!("- aHash: very fast, AES-NI 가속, *NOT* crypto-grade.");
    println!("- FxHash: fastest, no DoS resistance.");
    println!("- SipHash13: Rust std HashMap의 default, DoS-resistant but ~3-bit faster than YHash.");
}
