//! Farfalle 압축의 incremental absorb 검증.

use ysc5::consts::domain;
use ysc5::farfalle::{key_setup, transition, Compressor, Ysc5_128};

#[test]
fn incremental_compression_equals_monolithic() {
    let key = [0x42; 32];
    let seed = key_setup::<Ysc5_128>(&key, domain::STREAM).unwrap();
    let block_aligned: Vec<u8> = vec![0xABu8; 256]; // 2 blocks

    let mut c_a = Compressor::<Ysc5_128>::new(&seed);
    c_a.absorb_block(&block_aligned[..128]);
    c_a.absorb_block(&block_aligned[128..]);
    c_a.absorb(&[]); // padding block
    let (y_a, mask_a) = c_a.finish();

    let mut c_b = Compressor::<Ysc5_128>::new(&seed);
    c_b.absorb(&block_aligned);
    let (y_b, mask_b) = c_b.finish();

    assert_eq!(y_a, y_b);
    assert_eq!(mask_a, mask_b);
}

#[test]
fn incremental_block_then_block_matches_full() {
    let key = [0xCC; 32];
    let seed = key_setup::<Ysc5_128>(&key, domain::STREAM).unwrap();
    let m1 = vec![0x11u8; 128];
    let m2 = vec![0x22u8; 128];
    let combined: Vec<u8> = [&m1[..], &m2[..]].concat();

    let mut c_incr = Compressor::<Ysc5_128>::new(&seed);
    c_incr.absorb_block(&m1);
    c_incr.absorb_block(&m2);

    let mut c_mono = Compressor::<Ysc5_128>::new(&seed);
    c_mono.absorb_block(&combined[..128]);
    c_mono.absorb_block(&combined[128..]);

    assert_eq!(c_incr.snapshot(), c_mono.snapshot());
}

#[test]
fn snapshot_and_resume() {
    let key = [0x77; 32];
    let seed = key_setup::<Ysc5_128>(&key, domain::STREAM).unwrap();

    let mut c1 = Compressor::<Ysc5_128>::new(&seed);
    c1.absorb_block(&[0xAA; 128]);
    c1.absorb_block(&[0xBB; 128]);
    let (y1, m1) = c1.finish();

    let mut c2 = Compressor::<Ysc5_128>::new(&seed);
    c2.absorb_block(&[0xAA; 128]);
    c2.absorb_block(&[0xBB; 128]);
    let (y2, m2) = c2.finish();

    assert_eq!(transition::<Ysc5_128>(&y1, &m1), transition::<Ysc5_128>(&y2, &m2));
}

#[test]
fn block_order_changes_result() {
    let key = [0x33; 32];
    let seed = key_setup::<Ysc5_128>(&key, domain::STREAM).unwrap();
    let blocks: Vec<[u8; 128]> = (0..4)
        .map(|i| {
            let mut b = [0u8; 128];
            b[0] = i as u8;
            b
        })
        .collect();
    let mut c1 = Compressor::<Ysc5_128>::new(&seed);
    for b in &blocks {
        c1.absorb_block(b);
    }
    let s1 = c1.snapshot();

    let mut c2 = Compressor::<Ysc5_128>::new(&seed);
    for b in blocks.iter().rev() {
        c2.absorb_block(b);
    }
    let s2 = c2.snapshot();

    assert_ne!(s1.0, s2.0, "마스크 roll이 순서 의존성을 만들어야 함");
}
