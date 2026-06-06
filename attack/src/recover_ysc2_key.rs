//! [공격 2] YSC2 스트림 암호의 단일 키스트림 블록 → 원본 키 완전 복구.
//!
//! 공격 1에서 복구한 비밀 상태(= permutation(key||nonce))는
//! 초기화 순열도 가역적이라는 사실을 추가로 활용하면 키까지 풀린다.
//! 논스는 공개값이므로, 역연산 결과의 키 영역만 그대로 읽으면 끝.

#[path = "ysc2_ref.rs"]
mod ysc2_ref;
use ysc2_ref::{block_to_words, ysc2};

fn recover_key_512(keystream_block1: &[u8; 128], nonce: &[u8; 64], rounds: usize) -> [u8; 64] {
    // 1) 키스트림 → 비밀 상태
    let mut s = block_to_words(keystream_block1);
    ysc2::inverse_permutation(&mut s, rounds);
    s[0] ^= 1; // counter 제거

    // 2) 초기화 순열의 역을 적용 → load(key, nonce) 직전 상태
    ysc2::inverse_permutation(&mut s, rounds);

    // 3) Ysc2_512 분기: state[0..8] = key 워드, state[8..16] = nonce 워드
    let mut key = [0u8; 64];
    for i in 0..8 {
        key[i * 8..(i + 1) * 8].copy_from_slice(&s[i].to_le_bytes());
    }
    // 검증: state[8..16]이 정확히 nonce와 일치해야 함.
    for (i, chunk) in nonce.chunks_exact(8).enumerate() {
        let expect = u64::from_le_bytes(chunk.try_into().unwrap());
        assert_eq!(s[8 + i], expect, "Ysc2_512 키 복구 일관성 검사 실패");
    }
    key
}

fn recover_key_1024(keystream_block1: &[u8; 128], nonce: &[u8; 64], rounds: usize) -> [u8; 128] {
    let mut s = block_to_words(keystream_block1);
    ysc2::inverse_permutation(&mut s, rounds);
    s[0] ^= 1;
    ysc2::inverse_permutation(&mut s, rounds);

    // Ysc2_1024 분기: state[0..8] = key[0..64], state[8..16] = key[64..128] ^ nonce
    let mut key = [0u8; 128];
    for i in 0..8 {
        key[i * 8..(i + 1) * 8].copy_from_slice(&s[i].to_le_bytes());
    }
    for i in 0..8 {
        let n = u64::from_le_bytes(nonce[i * 8..(i + 1) * 8].try_into().unwrap());
        let k = s[8 + i] ^ n;
        key[64 + i * 8..64 + (i + 1) * 8].copy_from_slice(&k.to_le_bytes());
    }
    key
}

fn main() {
    let rounds = 12;

    // -------- Ysc2_512 --------
    println!("=== 공격 2-a: YSC2-512 키 복구 (KPA, 128바이트) ===");
    let key512: [u8; 64] = std::array::from_fn(|i| (i as u8).wrapping_mul(53) ^ 0xC3);
    let nonce: [u8; 64] = std::array::from_fn(|i| (i as u8).wrapping_mul(47) ^ 0x3C);
    let state = ysc2::init_state(&key512, &nonce, rounds);
    let blk = ysc2::gen_ks_block(&state, 1, rounds);

    let recovered = recover_key_512(&blk, &nonce, rounds);
    assert_eq!(recovered, key512);
    println!("  원본 키 (앞 16바이트): {}", hex::encode(&key512[..16]));
    println!("  복구 키 (앞 16바이트): {}", hex::encode(&recovered[..16]));
    println!("  [OK] 512비트 키 완전 복구\n");

    // -------- Ysc2_1024 --------
    println!("=== 공격 2-b: YSC2-1024 키 복구 (KPA, 128바이트) ===");
    let key1024: [u8; 128] = std::array::from_fn(|i| (i as u8).wrapping_mul(73) ^ 0xF0);
    let state = ysc2::init_state(&key1024, &nonce, rounds);
    let blk = ysc2::gen_ks_block(&state, 1, rounds);

    let recovered = recover_key_1024(&blk, &nonce, rounds);
    assert_eq!(recovered, key1024);
    println!("  원본 키 (앞 16바이트): {}", hex::encode(&key1024[..16]));
    println!("  복구 키 (앞 16바이트): {}", hex::encode(&recovered[..16]));
    println!("  [OK] 1024비트 키 완전 복구");

    println!("\n→ ROUNDS = 12든 1200이든 무관하다. 라운드 수와 보안 수준은 무관함.");
    println!("→ 양자 내성 주장(README) 무효: 단일 블록 KPA로 고전 컴퓨터에서도 즉시 풀림.");
}
