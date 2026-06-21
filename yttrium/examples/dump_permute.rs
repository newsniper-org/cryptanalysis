// Dump permute() outputs for cross-check against Python model.
// Run: cargo run --example dump_permute
fn main() {
    // expose via a tiny re-impl is impossible (private); instead use public permute.
    // yttrium::permute is pub.
    let inputs: [[u32; 8]; 3] = [
        [0x01234567, 0x89abcdef, 0xdeadbeef, 0xcafebabe, 1, 2, 3, 0xffffffff],
        [0, 0, 0, 0, 0, 0, 0, 0],
        [1, 0, 0, 0, 0, 0, 0, 0],
    ];
    for inp in inputs.iter() {
        for &r in &[1usize, 2, 3, 4, 6, 8] {
            let mut s = *inp;
            yttrium::permute(&mut s, r);
            print!("IN");
            for w in inp.iter() { print!(" {:08x}", w); }
            print!(" R={} OUT", r);
            for w in s.iter() { print!(" {:08x}", w); }
            println!();
        }
    }
}
