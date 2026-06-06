//! [공격 4] AuxCrypt 키스트림 1블록만으로 키 완전 복구.
//!
//! AuxCrypt의 순열은 affine이므로 ysc2와 같은 단순 inverse가 그대로 작동한다.
//! 본 PoC는 inverse_permutation을 두 번 적용해 키를 복원한다.
//! (affine 시스템 푸는 방법도 가능하지만, inverse가 명시적으로 존재.)

#[path = "ysc2_ref.rs"]
mod ysc2_ref;
use ysc2_ref::{block_to_words, auxcrypt};

fn recover_auxcrypt_key(blk1: &[u8; 128], nonce: &[u8; 64], key_len: usize, rounds: usize) -> Vec<u8> {
    let mut s = block_to_words(blk1);
    auxcrypt::inverse_permutation(&mut s, rounds);
    s[0] ^= 1;
    auxcrypt::inverse_permutation(&mut s, rounds);

    // load(key, nonce): state[0..key_len/8] = key, state[8..16] ^= nonce.
    let mut key = vec![0u8; key_len];
    for i in 0..key_len / 8 {
        if i < 8 {
            key[i * 8..(i + 1) * 8].copy_from_slice(&s[i].to_le_bytes());
        } else {
            // 1024비트 키: state[8..16]에 key의 뒷부분이 nonce와 XOR된 채 들어있다
            let nidx = i - 8;
            let nw = u64::from_le_bytes(nonce[nidx * 8..(nidx + 1) * 8].try_into().unwrap());
            let k = s[i] ^ nw;
            key[i * 8..(i + 1) * 8].copy_from_slice(&k.to_le_bytes());
        }
    }
    key
}

fn main() {
    // ---- AuxCrypt-512 (14 라운드) ----
    println!("=== 공격 4-a: AuxCrypt-512 키 복구 (14 라운드) ===");
    let rounds = 14;
    let key: [u8; 64] = std::array::from_fn(|i| (i as u8).wrapping_mul(91) ^ 0x66);
    let nonce: [u8; 64] = std::array::from_fn(|i| (i as u8).wrapping_mul(11) ^ 0x77);
    let state = auxcrypt::init_state(&key, &nonce, rounds);
    let blk = auxcrypt::gen_ks_block(&state, 1, rounds);
    let rec = recover_auxcrypt_key(&blk, &nonce, 64, rounds);
    assert_eq!(&rec[..], &key[..]);
    println!("  원본 키 (앞 16바이트): {}", hex::encode(&key[..16]));
    println!("  복구 키 (앞 16바이트): {}", hex::encode(&rec[..16]));
    println!("  [OK]\n");

    // ---- AuxCrypt-1024 (20 라운드) ----
    println!("=== 공격 4-b: AuxCrypt-1024 키 복구 (20 라운드) ===");
    let rounds = 20;
    let key: [u8; 128] = std::array::from_fn(|i| (i as u8).wrapping_mul(101) ^ 0x88);
    let state = auxcrypt::init_state(&key, &nonce, rounds);
    let blk = auxcrypt::gen_ks_block(&state, 1, rounds);
    let rec = recover_auxcrypt_key(&blk, &nonce, 128, rounds);
    assert_eq!(&rec[..], &key[..]);
    println!("  원본 키 (앞 16바이트): {}", hex::encode(&key[..16]));
    println!("  복구 키 (앞 16바이트): {}", hex::encode(&rec[..16]));
    println!("  [OK]");
}
