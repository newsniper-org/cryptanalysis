# YSip 사양 초안 (v0.0-pre)

> **파생 설계**: yttrium(not -large)의 RAR(ROT-ADD-ROT) 코어를 SipHash의 가산-회전 믹싱
> 대체재로 추출한 경량 keyed PRF. **검증 전 초안 — 운영 사용 금지.**
> 권위 파라미터: `PARAM_VERSION = "ysip-params-v0.0-pre"`. 레퍼런스 구현: `src/lib.rs`.

## 0. 한 줄 요약

YSip = **SipHash 구성**(키 흡수·메시지 워드 패딩·finalize 프레이밍 그대로) +
**RAR 믹싱**(SipRound의 모듈러 가산 `⊞`를 yttrium 코어 `rar(x,y) = ROTR_β(ROTL_α(x) ⊞ y)`로
치환). 도메인분리를 위해 IV만 SipHash ASCII 상수 대신 **SHA-512 IV 상위 4워드**(NUMS)로 둔다.

- 상태 256-bit(4×u64), 키 128-bit, 출력 64-bit.
- 변형: **YSip-2-4**(c=2, d=4, 기본) / **YSip-3-6**(c=3, d=6, 보수).
- `no_std`, `unsafe` 없음.

## 1. 동기 / 파생 근거

yttrium 결합기 *전체* G = (영합 reduction)∘F∘(all-8 σ)∘rar 는 상호 결합돼 통째 추출이
곤란하다(영합 broadcast가 8레인을 묶고, σ가 레인별 α^k로 갈라짐). 그러나 그 **코어 ARX
프리미티브** `rar` 하나만 떼면 SPECK 빌딩블록(`(x ⋙? ) ... `)과 동급의 단순 믹서이고,
SipHash의 `v ⊞ v'` 위치에 그대로 꽂을 수 있다.

확산 평가(`milp/rar_avalanche.py`, 그리고 본 크레이트 `avalanche_full_diffusion` 테스트가
실제 구현 기준으로 재확인): SipRound의 `⊞`를 `rar`로 치환한 라운드는 1-bit 입력차분에 대해
**finalize(d=4)까지 거치면 64-bit 출력의 평균 ~32bit가 뒤집히고 per-bit bias < 0.05**
(완전확산). 즉 RAR 코어 추출은 viable하다.

> **무엇을 상속하지 *않는가*(정직)**: SipHash 자체의 차분/선형 trail 경계와 회전불변
> 논증은 가산 기반이다. `⊞`→`rar` 치환은 회전을 추가하므로 trail 분기·회전불변 특성이
> 달라진다. YSip는 SipHash의 보안논증을 **상속하지 않으며**, §6의 자체 분석 의무가 남는다.

## 2. 상수 (동결, 단 잠정)

| 기호 | 값 | 출처 |
|---|---|---|
| (α, β) | (8, 9) | yttrium 결합기 `ROT_A`/`ROT_B`와 동일 |
| SipRound 회전 | 13, 16, 21, 17, 32 | SipHash 원본 그대로(믹싱 위상 유지) |
| IV0..IV3 | `6a09e667f3bcc908`, `bb67ae8584caa73b`, `3c6ef372fe94f82b`, `a54ff53a5f1d36f1` | SHA-512 초기 해시값 상위 4워드 (NUMS) |
| (c, d) | (2,4) 기본 / (3,6) 보수 | §6 정당화 **미완** — SipHash 대응값 잠정 차용 |

`rar(x,y) = ROTR_β(ROTL_α(x) ⊞ y)`. y 고정 시 x에 대해 가역
(`x = ROTR_α(ROTL_β(z) ⊟ y)`), 따라서 라운드는 SipRound처럼 순열이다(`rar_invertible` 테스트).

## 3. 라운드 함수

SipRound 구조에서 4개의 `⊞`를 `rar`로 치환:

```
v0 = rar(v0, v1);  v1 = v1 ≪ 13;  v1 ^= v0;  v0 = v0 ≪ 32;
v2 = rar(v2, v3);  v3 = v3 ≪ 16;  v3 ^= v2;
v0 = rar(v0, v3);  v3 = v3 ≪ 21;  v3 ^= v0;
v2 = rar(v2, v1);  v1 = v1 ≪ 17;  v1 ^= v2;  v2 = v2 ≪ 32;
```

## 4. 구성 (SipHash 프레이밍)

키 `K`(16바이트 LE) → `k0 = LE64(K[0..8])`, `k1 = LE64(K[8..16])`.

```
초기화:  v0 = IV0 ^ k0,  v1 = IV1 ^ k1,  v2 = IV2 ^ k0,  v3 = IV3 ^ k1
흡수:    각 8바이트 LE 워드 mi 에 대해   v3 ^= mi;  c-라운드;  v0 ^= mi
마지막:  b = (len mod 256) ≪ 56  |  잔여바이트(LE, 하위)        ;  v3 ^= b;  c-라운드;  v0 ^= b
finalize: v2 ^= 0xff;  d-라운드;  반환  v0 ^ v1 ^ v2 ^ v3
```

엔디안·패딩·길이 인코딩은 SipHash와 동일하다. 스트리밍 임의 분할이 원샷과 bit-exact
일치함을 `streaming_equals_oneshot` 테스트가 보장한다.

## 5. API / 노출면

- `YSip::new(&[u8;16])` — YSip-2-4. `new_conservative` — YSip-3-6.
- `YSip::new_with_key_and_rounds(key, c, d)` — 임의 (c,d).
- `YSip::oneshot(key, c, d, data) -> u64`.
- `impl core::hash::Hasher` — `BuildHasher`로 감싸 HashMap drop-in (SipHash 자리 대체).

## 6. 보안 의무 (미완 — v0.0-pre 차단 사유)

운영화 전 반드시 수행:

1. **차분 분석**: `rar`-SipRound의 1라운드 차분분기 수 → R-라운드 최적 trail 가중치
   하한 → c·d 라운드수 정당화 (yttrium의 `milp/` MILP/외삽 방법론 재사용 가능).
2. **선형 분석**: 회전+가산 합성의 선형 상관 walk; 마스킹 정당화.
3. **회전 분석(rotational / rotational-XOR)**: ARX-only이므로 회전불변 공격이 1순위 위협.
   상수(IV·RC 부재)가 회전대칭을 깨는지 확인 — 현재 RC 주입이 **없어** SipHash보다 회전
   취약 가능성 → RC 도입 여부 결정 필요.
4. **상수 튜닝**: (α,β)=(8,9)는 yttrium 상속값일 뿐 YSip 라운드에 최적이라는 근거 없음.
   SipRound 회전과의 상호작용으로 재탐색.
5. **라운드수 정당화**: (2,4)/(3,6)은 SipHash 차용. RAR 치환 후 안전마진 재산정.
6. **KAT 동결**: §6.1~6.5 통과 후 교차구현 KAT 벡터 동결 + `PARAM_VERSION` bump(`-pre` 제거).

> **현 상태 근거**: 확산(avalanche)은 통과했으나 확산 ≠ 차분/선형/회전 저항. 위 6항 전까지
> YSip는 *설계 가설*이다.

## 7. 성능 (참고, scalar 레퍼런스)

`cargo run --release --example bench` (1 MiB, 코어고정 1회 측정):

| 함수 | MB/s | vs SipHash-2-4 |
|---|--:|--:|
| SipHash-1-3 | ~6550 | 1.8× |
| SipHash-2-4 | ~3645 | 1.0× |
| **YSip-2-4** | ~2400 | **0.66×** |
| YSip-3-6 | ~1657 | 0.45× |

`rar`는 `⊞`당 회전 2회를 추가하므로 라운드당 회전이 늘어 SipHash보다 느리다. 그럼에도
**같은 차수(SipHash-class)** 속도를 유지한다 — 가치제안 충족. (SIMD/배치 미적용 잔여.)

## 8. 재현

```bash
cargo test -p ysip --release          # 결정성·스트리밍·avalanche·rar 가역성
cargo run  -p ysip --release --example bench
cargo build -p ysip --no-default-features   # no_std
python3 milp/rar_avalanche.py         # 코어 확산 vs SipRound (보조)
```
