//! KAT 생성기 — 독립 Python 레퍼런스(`ref_check.py`)와 bit-exact 교차검증용.
//! 동일 key/len/메시지 규칙. 실행: cargo run --release --example gen_kat -p ysip
//! 검증: diff <(cargo run -q --release --example gen_kat) <(python3 ref_check.py)

use std::hash::Hasher as _;
use ysip::YSip;

fn msg(n: usize) -> Vec<u8> {
    (0..n).map(|i| ((i.wrapping_mul(0x9d)).wrapping_add(7)) as u8).collect()
}

fn main() {
    let keys: [(&str, [u8; 16]); 3] = [
        ("k00", [0u8; 16]),
        ("kff", [0xffu8; 16]),
        ("kseq", core::array::from_fn(|i| i as u8)),
    ];
    let lens = [0usize, 1, 7, 8, 9, 15, 16, 31, 32, 63, 64];
    println!("# YSip KAT (독립 Python 레퍼런스). 형식: variant key len = tag_u64_hex (tag_le_bytes_hex)");
    for (vname, c, d) in [("YSip-2-4", 2usize, 4usize), ("YSip-3-6", 3, 6)] {
        for (kname, key) in &keys {
            for n in lens {
                let mut h = YSip::new_with_key_and_rounds(key, c, d);
                h.write(&msg(n));
                let t = h.finish();
                println!("{vname} {kname} {n:2} = {t:016x} ({})", hex::encode(t.to_le_bytes()));
            }
        }
    }
}
