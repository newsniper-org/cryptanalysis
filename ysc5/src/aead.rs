//! YSC5 AEAD. SPEC §7.2.
//!
//! 구현: encrypt와 decrypt 모두 *두 패스*로 처리하여 *CT만* 압축에 흡수한다.
//!   패스 1: (Nc ∥ AD)을 흡수 → 키스트림 생성 → CT 계산
//!   패스 2: (Nc ∥ AD ∥ CT)을 흡수 → 태그 생성
//!
//! 이로써 encrypt/decrypt가 *대칭*이 되어 같은 (K, Nc, Ad, Ct)에서 동일 태그.

use crate::consts::{domain, STATE_WORDS};
use crate::farfalle::{
    key_setup, transition, Compressor, Error, Expander, Ysc5Variant,
};
use alloc::vec;
use alloc::vec::Vec;
use zeroize::Zeroize;

/// AEAD cipher 인스턴스.
#[derive(Clone)]
pub struct Ysc5Aead<V: Ysc5Variant> {
    seed: [u64; STATE_WORDS],
    _variant: core::marker::PhantomData<V>,
}

impl<V: Ysc5Variant> Drop for Ysc5Aead<V> {
    fn drop(&mut self) {
        self.seed.zeroize();
    }
}

impl<V: Ysc5Variant> Ysc5Aead<V> {
    /// 새 AEAD.
    pub fn new(key: &[u8]) -> Result<Self, Error> {
        let seed = key_setup::<V>(key, domain::AEAD)?;
        Ok(Self {
            seed,
            _variant: core::marker::PhantomData,
        })
    }

    /// 패스 1 결과: (Nc + AD)을 흡수한 Compressor의 finish 후 Y'.
    fn keystream_seed(&self, nonce: &[u8], ad: &[u8]) -> [u64; STATE_WORDS] {
        let mut c = Compressor::<V>::new(&self.seed);
        c.absorb(nonce);
        let mut dm = [0u8; 8];
        dm.copy_from_slice(&domain::AEAD_AD.to_le_bytes());
        c.absorb(&dm);
        c.absorb(ad);
        let (y, end_mask) = c.finish();
        transition::<V>(&y, &end_mask)
    }

    /// 패스 2 결과: (Nc + AD + CT)을 흡수한 Compressor의 finish 후 Y'_tag.
    fn tag_seed(&self, nonce: &[u8], ad: &[u8], ct: &[u8]) -> [u64; STATE_WORDS] {
        let mut c = Compressor::<V>::new(&self.seed);
        c.absorb(nonce);
        let mut dm_ad = [0u8; 8];
        dm_ad.copy_from_slice(&domain::AEAD_AD.to_le_bytes());
        c.absorb(&dm_ad);
        c.absorb(ad);
        let mut dm_ct = [0u8; 8];
        dm_ct.copy_from_slice(&domain::AEAD_CT.to_le_bytes());
        c.absorb(&dm_ct);
        c.absorb(ct);
        let (y, end_mask) = c.finish();
        let mut yp = transition::<V>(&y, &end_mask);
        yp[STATE_WORDS - 1] ^= domain::AEAD_TAG;
        yp
    }

    /// 암호화. `buffer`는 in-place로 ct로 변환됨.
    pub fn encrypt(
        &self,
        nonce: &[u8],
        ad: &[u8],
        buffer: &mut [u8],
    ) -> Result<Vec<u8>, Error> {
        if nonce.len() != V::NONCE_BYTES {
            return Err(Error::BadKeyOrNonceLength);
        }

        // 패스 1: 키스트림 생성 → PT를 CT로
        let y_ks = self.keystream_seed(nonce, ad);
        let mut e = Expander::<V>::new(&y_ks);
        let mut block = [0u8; 64];
        let rate = V::RATE_BYTES;
        let mut offset = 0usize;
        while offset < buffer.len() {
            let take = core::cmp::min(rate, buffer.len() - offset);
            e.squeeze(&mut block[..take]);
            for k in 0..take {
                buffer[offset + k] ^= block[k];
            }
            offset += take;
        }

        // 패스 2: CT를 흡수 → 태그
        let y_tag = self.tag_seed(nonce, ad, buffer);
        let mut e_tag = Expander::<V>::new(&y_tag);
        let mut tag = vec![0u8; V::TAG_BYTES];
        e_tag.squeeze(&mut tag);

        block.zeroize();
        Ok(tag)
    }

    /// 복호화.
    pub fn decrypt(
        &self,
        nonce: &[u8],
        ad: &[u8],
        buffer: &mut [u8],
        expected_tag: &[u8],
    ) -> Result<(), Error> {
        if nonce.len() != V::NONCE_BYTES || expected_tag.len() != V::TAG_BYTES {
            return Err(Error::BadKeyOrNonceLength);
        }

        // 패스 1: 태그 검증 (CT 흡수)
        let y_tag = self.tag_seed(nonce, ad, buffer);
        let mut e_tag = Expander::<V>::new(&y_tag);
        let mut computed = vec![0u8; V::TAG_BYTES];
        e_tag.squeeze(&mut computed);

        if !ct_eq(&computed, expected_tag) {
            buffer.zeroize();
            return Err(Error::AuthenticationFailed);
        }

        // 패스 2: 태그 검증 통과 후 키스트림 적용 → PT
        let y_ks = self.keystream_seed(nonce, ad);
        let mut e = Expander::<V>::new(&y_ks);
        let mut block = [0u8; 64];
        let rate = V::RATE_BYTES;
        let mut offset = 0usize;
        while offset < buffer.len() {
            let take = core::cmp::min(rate, buffer.len() - offset);
            e.squeeze(&mut block[..take]);
            for k in 0..take {
                buffer[offset + k] ^= block[k];
            }
            offset += take;
        }

        block.zeroize();
        Ok(())
    }
}

fn ct_eq(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    a.iter().zip(b.iter()).fold(0u8, |acc, (&x, &y)| acc | (x ^ y)) == 0
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::farfalle::Ysc5_128;

    #[test]
    fn aead_roundtrip() {
        let aead = Ysc5Aead::<Ysc5_128>::new(&[0xAA; 32]).unwrap();
        let nonce = [0xBB; 24];
        let ad = b"associated data";
        let pt = b"plaintext message for AEAD";
        let mut buf = pt.to_vec();
        let tag = aead.encrypt(&nonce, ad, &mut buf).unwrap();
        aead.decrypt(&nonce, ad, &mut buf, &tag).unwrap();
        assert_eq!(&buf[..], pt);
    }

    #[test]
    fn aead_tag_tamper_fails() {
        let aead = Ysc5Aead::<Ysc5_128>::new(&[0x11; 32]).unwrap();
        let nonce = [0x22; 24];
        let mut buf = b"secret".to_vec();
        let mut tag = aead.encrypt(&nonce, b"", &mut buf).unwrap();
        tag[0] ^= 1;
        assert!(aead.decrypt(&nonce, b"", &mut buf, &tag).is_err());
        assert_eq!(buf, vec![0u8; 6]);
    }

    #[test]
    fn aead_ad_tamper_fails() {
        let aead = Ysc5Aead::<Ysc5_128>::new(&[0x33; 32]).unwrap();
        let nonce = [0x44; 24];
        let mut buf = b"data".to_vec();
        let tag = aead.encrypt(&nonce, b"original AD", &mut buf).unwrap();
        assert!(aead.decrypt(&nonce, b"tampered AD", &mut buf, &tag).is_err());
    }
}
