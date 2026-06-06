//! [공격 3] AuxCrypt의 "비선형 함수"가 사실 affine임을 보이고,
//!         순열 전체가 GF(2) 위 affine map임을 실험적으로 검증한다.
//!
//! f(x) = ¬x ⊕ (x <<< 19) ⊕ (x <<< 41)
//!      = (x ⊕ 0xFF...FF) ⊕ rot(x,19) ⊕ rot(x,41)
//!      → 상수 항이 있으므로 affine. GF(2)-선형 부분은 R19 ⊕ R41 ⊕ I.
//!
//! Lai-Massey 라운드: a' = a ⊕ f(a⊕b), b' = b ⊕ f(a⊕b)
//!   f는 affine이므로 라운드는 affine.
//! 라운드 상수 추가, 워드 순열 — 모두 affine.
//! 따라서 14·20 라운드 전체가 affine. ⇒ permutation(x) = M·x ⊕ c.

#[path = "ysc2_ref.rs"]
mod ysc2_ref;
use ysc2_ref::auxcrypt;

/// 정의된 affine성을 직접 검증: f(0)을 c라 할 때
///   permutation(x) ⊕ permutation(0) = M·x  (선형)
///   permutation(x ⊕ y) ⊕ permutation(0) = permutation(x) ⊕ permutation(y) ⊕ permutation(0)
fn check_affinity(rounds: usize) {
    // 임의의 두 입력 x, y와 그 XOR z = x ⊕ y에 대해,
    // P(x) ⊕ P(y) ⊕ P(z) = P(0)  ↔  affine.
    use std::hash::Hasher;
    let mut tested = 0u32;
    let mut hasher = std::collections::hash_map::DefaultHasher::new();
    for seed in 0..16u64 {
        hasher.write_u64(seed);
        let h = hasher.finish();

        let mut x = [0u64; 16];
        let mut y = [0u64; 16];
        for i in 0..16 {
            x[i] = h.wrapping_mul(0x9E3779B97F4A7C15).wrapping_add(i as u64);
            y[i] = h.wrapping_mul(0xC6BC279692B5C323).wrapping_add((i as u64) << 32);
        }
        let mut z = [0u64; 16];
        for i in 0..16 { z[i] = x[i] ^ y[i]; }

        let mut px = x; auxcrypt::permutation(&mut px, rounds);
        let mut py = y; auxcrypt::permutation(&mut py, rounds);
        let mut pz = z; auxcrypt::permutation(&mut pz, rounds);
        let mut p0 = [0u64; 16]; auxcrypt::permutation(&mut p0, rounds);

        for i in 0..16 {
            let lhs = px[i] ^ py[i] ^ pz[i];
            let rhs = p0[i];
            assert_eq!(lhs, rhs,
                "affinity 위반: 라운드={}, seed={}, word={}", rounds, seed, i);
        }
        tested += 1;
    }
    println!("  {} 라운드: {}개의 (x,y) 쌍에 대해 affine 성질 통과", rounds, tested);
}

/// 표준 기저 벡터에 대한 영향으로부터 1024×1024 GF(2) 행렬 M과 상수 c 추출.
fn extract_affine_map(rounds: usize) -> (Vec<[u64; 16]>, [u64; 16]) {
    // c = P(0)
    let mut c = [0u64; 16];
    auxcrypt::permutation(&mut c, rounds);

    // M의 j번째 열 = P(e_j) ⊕ c, 단 e_j는 j번 비트만 1인 1024비트 벡터.
    let mut columns: Vec<[u64; 16]> = Vec::with_capacity(1024);
    for bit in 0..1024 {
        let word_idx = bit / 64;
        let bit_idx = bit % 64;
        let mut e = [0u64; 16];
        e[word_idx] = 1u64 << bit_idx;
        auxcrypt::permutation(&mut e, rounds);
        for i in 0..16 { e[i] ^= c[i]; }
        columns.push(e);
    }
    (columns, c)
}

fn apply_affine(columns: &[[u64; 16]], c: &[u64; 16], x: &[u64; 16]) -> [u64; 16] {
    let mut y = *c;
    for bit in 0..1024 {
        let word_idx = bit / 64;
        let bit_idx = bit % 64;
        if (x[word_idx] >> bit_idx) & 1 == 1 {
            let col = &columns[bit];
            for i in 0..16 { y[i] ^= col[i]; }
        }
    }
    y
}

fn main() {
    println!("=== 공격 3: AuxCrypt 순열은 affine 함수 ===\n");

    println!("[A] 순열의 affine 성질 확인:");
    check_affinity(14);
    check_affinity(20);

    println!("\n[B] 표준 기저로부터 affine map (M, c) 추출, 임의 입력에 대해 일치 확인:");
    let rounds = 20;
    let (cols, c) = extract_affine_map(rounds);
    for trial in 0..8 {
        let mut x = [0u64; 16];
        for i in 0..16 { x[i] = (0x123456789ABCDEFu64).wrapping_mul(trial as u64 + 1).wrapping_add(i as u64); }
        let mut px = x; auxcrypt::permutation(&mut px, rounds);
        let predicted = apply_affine(&cols, &c, &x);
        assert_eq!(px, predicted, "trial {} 실패", trial);
    }
    println!("  20라운드 순열 = M·x ⊕ c (M은 1024×1024 GF(2) 행렬). 검증 완료.");

    println!("\n[C] 키 복구 환원:");
    println!("  - AuxCrypt 키스트림 블록 = P(state ⊕ counter@[0])  (전체 1024비트 출력)");
    println!("  - P가 affine이므로 keystream_block = M·state ⊕ M·(counter@[0]) ⊕ c");
    println!("  - state는 P(load(key, nonce))이며 다시 affine: state = M·(key||nonce) ⊕ c");
    println!("  - 따라서 keystream = M' · (key||nonce) ⊕ c'");
    println!("  → 128바이트 KPA + 1024×1024 GF(2) 선형계 풀이로 키 복구 (재공격 시 행렬 재사용)");
    println!("  → 라운드 수가 14/20 → 그 어떤 수든 영향 없음 (affine 합성은 여전히 affine).");
}
