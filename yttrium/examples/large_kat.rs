//! large 해시 1벡터 출력 (scalar/simd bit-exact 대조용).
use yttrium::{large, Rounds};
fn main() {
    for (n, rd) in [("(8,12,24)", Rounds::V8_12_24), ("(10,14,24)", Rounds::V10_14_24)] {
        for (inm, data) in [("abc", b"abc".to_vec()), ("5000B", vec![0xc3u8; 5000])] {
            let h = large::hash(&data, rd, 32);
            let hex: String = h.iter().map(|b| format!("{b:02x}")).collect();
            println!("large-{n} {inm:6} {hex}");
        }
    }
}
