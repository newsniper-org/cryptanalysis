# NOTE — YSC5 AEAD에서 nonce의 최적 분할

> *META.md §7 Q5* — "AEAD 모드에서 nonce 일부를 압축에, 나머지를 확장 roll seed에 넣는
> 최적 분할은?" 분석.

## 1. 현재 사양 (YSC5 SPEC §7.2)

```
encrypt(K, Nc, Ad, Pt):
    pass 1: c = Compressor(seed=key_setup(K))
            c.absorb(Nc)
            c.absorb(DOMAIN_AD || Ad)
            y_ks = transition(c.finish())
            Ct = Pt XOR Expand(y_ks)
    pass 2: c = Compressor(seed)  // 재구축
            c.absorb(Nc); c.absorb(DOMAIN_AD || Ad); c.absorb(DOMAIN_CT || Ct)
            y_tag = transition(c.finish()) XOR DOMAIN_TAG
            tag = Expand(y_tag)
```

Nonce는 *완전히 압축*에만 들어감 (확장 단계 입력 없음).

## 2. 대안 — Kravatte-SANE 식 분할

Bertoni–Daemen의 Kravatte-SANE은 nonce를 *seekable 카운터*로 활용:

- Nonce 24 byte의 절반(12 byte)을 압축에 흡수.
- 나머지 12 byte를 확장 시 *roll seed의 초기값*으로 사용 → 같은 (K, Ad, Pt)라도 nonce 일부에 따라 다른 위치에서 keystream 추출.

### 장점
- **Seekable AEAD** — nonce의 일부가 *카운터* 역할 → 같은 메시지의 N번째 블록을 직접 access.
- **Random-access decryption** — 매우 큰 ciphertext에서 임의 위치 복호.

### 단점
- 사양 복잡도 증가 (nonce 절반의 *의미* 달라짐).
- Random-access를 안 쓰는 경우 무의미.

## 3. 권장 — Kravatte 방식이 적절한가?

### 본 사양의 사용 시나리오

YSC5는 *일반 목적 AEAD* — disk encryption, network packet, file encryption.
대부분의 응용은 *seek*가 자주 필요하지 않음:
- TLS-like 패킷: 매번 새 (K, Nc) → seek 불요.
- File encryption: 블록 단위 access가 흔하지만 random access는 fragmentation 등 별도 metadata.

→ *seek가 핵심 요구사항이 아닌* 보통 시나리오에서 현재 사양으로 충분.

### Seekable 변종을 도입한다면

새 모드 `YSC5-AEAD-Seekable`을 추가:
- Nonce를 (compress_nonce ∥ stream_offset)로 분할.
- compress_nonce는 압축 단계에 흡수.
- stream_offset은 expand 단계에서 `Expander.seek_to(offset)` 호출.

```rust
impl<V: Ysc5Variant> Ysc5AeadSeekable<V> {
    fn encrypt_at(&self, compress_nonce: &[u8], stream_offset: u64,
                  ad: &[u8], buffer: &mut [u8]) -> Tag {
        // ...압축 단계 (compress_nonce + ad)...
        let y_ks = transition(...);
        let mut e = Expander::new(&y_ks);
        e.seek_to_block(stream_offset);
        // keystream을 stream_offset부터 squeeze
        e.squeeze(buffer);
        // ...태그 (compress_nonce + ad + ct 모두 흡수)...
    }
}
```

## 4. nonce 길이 trade-off

| Nonce 분할 | compress 부분 | stream offset | 충돌 안전 메시지 수 (생일 한계) |
|-----------|--------------|---------------|----------------------------|
| 24 / 0 (현재) | 192 비트 | 0 | 2^96 |
| 16 / 8 | 128 비트 | 64 비트 | 2^64 |
| 12 / 12 | 96 비트 | 96 비트 | 2^48 |
| 8 / 16 | 64 비트 | 128 비트 | 2^32 |

→ *compress 부분*이 충돌 안전을 결정. 12/12 분할이 합리적 절충 (2^48 메시지는 충분히 큼).

## 5. 결론

| 결정 | 권장 |
|------|------|
| 현재 사양 (24/0) 유지 | *일반 AEAD가 주 용도라면 ✓* |
| 12/12 분할 (seekable 추가) | *seek 사용 시나리오가 있다면 별도 모드로 추가* |
| Nonce 길이 증가 (32 byte) | 충돌 안전 마진 확대; 사양 변경 비용 |

### 권고
- v0.1 사양은 *현재 형태* 유지 (단순함 우선).
- v0.2에 *YSC5-AEAD-Seekable* 추가 모드를 별도 정의 (seek 필요 시).
- *Nonce 24 byte / 192 비트*는 충분히 안전 마진 (≥ 2^96 메시지).

## 6. 참고

- Kravatte-SANE: <https://keccak.team/kravatte.html>
- AEAD nonce 분할의 다른 사례: AES-GCM (12 byte nonce + 4 byte counter), ChaCha20-Poly1305 (12 byte nonce + 4 byte counter).
