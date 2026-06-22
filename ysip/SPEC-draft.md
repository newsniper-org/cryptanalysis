# YSip 사양 초안 (v0.1-pre)

> **파생 설계**: yttrium(not -large)의 RAR(ROT-ADD-ROT) 코어를 SipHash의 가산-회전 믹싱
> 대체재로 추출한 경량 keyed PRF. **외부 검토 전 초안 — 운영 사용 금지.**
> 권위 파라미터: `PARAM_VERSION = "ysip-params-v0.1-pre"`. 레퍼런스 구현: `src/lib.rs`.
> 자체 암호분석(차분·선형·회전·상수·라운드수, 적대검증 통과): `milp/ysip-residual-obligations.md`.

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
| (c, d) | (2,4) 기본 / (3,6) 보수 | §6 정당화 완료(SipHash 상대) — (8,9)는 SMT-exact 차분 R2=7 로 후보 중 최강 |

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

## 6. 보안 의무 — 자체 분석 처리 완료 (적대검증 통과)

전 항목 `milp/ysip-residual-obligations.md` 에서 처리(도구·재현·정정 포함). 결론 요약:

1. **차분** ✅: 정확 최소 trail weight(z3 K별 증명) SipHash R1=0/R2=4 < **YSip R1=1/R2=7** —
   `rar`의 ROTL₈ 가 SipHash 의 weight-0 자명(all-MSB) trail 을 깸. 차분축 **per-round 우위**.
2. **선형** ◐: per-add 선형상관 \|corr\| 은 SipHash 와 **동일**(회전불변, n=5 multiset 증명).
   멀티라운드 **linear-hull 은 미측정(open)** — `rar` 피연산자 비대칭이라 per-add 동등이 hull
   동등을 함의 안 함. 1비트 라운드상관은 노이즈(비정보적). → 외부 검토 잔여.
3. **회전(RX)** ✅: 라운드 RX 가 SipHash 와 동일차수(YSip ~0.3bit/round 근소 열세). **RC 불요** —
   방어 기전은 초기상태 `v=IV⊕k` 의 RX-XOR 차분 `δ(v)=v⊕ROTL_γ(v)` 가 **키 의존**이라 키독립
   RX trail 이 불가능(SipHash 와 동일 구성차단). (이전 "RC 없어 취약 가능" 우려는 반증됨.)
4. **상수** ✅: (8,9)는 SMT-exact 차분 R2=7 로 후보 중 최강((12,29)·(16,21)=6), RX 도 최강.
   yttrium 코어와 동일 → 파생 일관성. 변경 사유 없음.
5. **라운드수** ◐: SipHash **상대** 정당화 — 구성 동일 + 차분 우위 + 회전 동급. (2,4)≙SipHash-2-4,
   (3,6) 보수. **절대 다라운드 trail 경계는 미확립**(z3 R≥3 timeout) — 유추이지 증명 아님.
6. **KAT 동결** ✅: 교차구현(Rust≡Python) bit-exact → `tests/kat.rs` 동결 + `PARAM_VERSION`
   `v0.0-pre`→`v0.1-pre` bump.

> **현 상태**: 자체 의무 처리·적대검증 통과로 *설계 가설*에서 **검토된 후보**로 격상. 단 `-pre` 유지
> 사유 = 외부 암호분석 미수행 + linear-hull/절대경계 open(아래 §6.1). yttrium v0.2-pre 와 동일 규율.

### 6.1 완전성 비평 (누락 공격 5축) — no-new-threat

`milp/ysip_completeness.py` (YSip 전용): 슬라이드·부메랑/회전-차분·차분-선형·고정점/약한키·
길이확장 전부 **무위협**. 부메랑 복귀율 R4 ≤2⁻²⁰; 유일 고정점 `f(0)=0` 은 키드 구성에서 **도달불가**
(v0,v2 가 k0 공유하나 IV0≠IV2; v1,v3·k1·IV1≠IV3). 슬라이드는 SipHash 논거 전이.

> **DL caveat (정직)**: bare-순열 차분-선형 상관이 ≤3라운드서 ≈1 (ARX carry-free, **SipHash 동일**)이고
> 출력 **64bit XOR-fold 가 죽인다**(finalize R=4서 floor 붕괴). 얕은 깊이 보안이 라운드믹싱보다
> **fold 에 기댐** — YSip-2-4 c=2 + fold. SipHash 와 동급·미악용이나 명시. 마진 원하면 YSip-3-6.

### 6.2 잔여 (외부 검토 과제)

- 멀티비트 **linear-hull** 미측정(ARX SMT 선형(Wallén) 미구현). δ≠0 라운드-내재 RX-XOR weight 미측정.
- 절대 차분/선형 trail 경계 R≥3(z3 timeout). 외부 암호분석 미수행(=`-pre` 사유).

## 7. 성능 (참고, scalar 레퍼런스, key=128b/out=64b)

`cargo run --release --example bench` (코어고정, 적응형). **벌크 처리량** (1 MiB):

| 함수 | MB/s | vs SipHash-2-4 |
|---|--:|--:|
| SipHash-1-3 | ~6600 | 1.8× |
| SipHash-2-4 | ~3640 | 1.0× |
| **YSip-2-4** | ~2410 | **0.66×** |
| YSip-3-6 | ~1710 | 0.47× |

**짧은 입력 ns/hash** (SipHash 핵심 용도 = HashMap 키 등; per-call init+finalize 지배):

| 입력 | SipHash-2-4 | YSip-2-4 | YSip-3-6 |
|---|--:|--:|--:|
| 8 B | 9.6 ns | 15.4 ns (1.6×) | 20.5 ns |
| 16 B | 12.0 ns | 18.2 ns (1.5×) | 25.0 ns |
| 32 B | 16.5 ns | 23.7 ns (1.4×) | 33.5 ns |
| 64 B | 24.9 ns | 36.2 ns (1.5×) | 52.6 ns |

`rar`는 `⊞`당 회전 2회를 추가하므로 라운드당 회전이 늘어 SipHash보다 느리다(벌크 0.66×,
짧은입력 ~1.5×). 그럼에도 **같은 차수(SipHash-class)** — 가치제안 충족. (SIMD/배치 미적용 잔여.)

## 8. 재현

```bash
cargo test -p ysip --release              # 결정성·스트리밍·avalanche·rar 가역성·KAT
cargo run  -p ysip --release --example bench
cargo run  -p ysip --release --example gen_kat   # KAT 생성 (≡ ref_check.py)
cargo build -p ysip --no-default-features        # no_std
diff <(cargo run -q --release --example gen_kat) <(python3 ysip/ref_check.py)  # 교차구현
# 자체 암호분석 (milp/, 결과: ysip-residual-obligations.md):
python3 milp/ysip_diff.py both 2         # SMT 차분 (SipHash vs YSip R1,R2 정확)
python3 milp/ysip_rotational.py          # RX 감쇠 + 키의존 δ 구성차단
python3 milp/ysip_linear.py              # per-add 선형(W1) + 1비트 노이즈 대조
clang++ -x cuda milp/ysip_lm_diff.cu --cuda-gpu-arch=sm_120 --cuda-path=/opt/cuda -O3 \
  -o milp/ysip_lm_diff -L/opt/cuda/lib64 -lcudart -ldl -lrt -lpthread && ./milp/ysip_lm_diff
python3 milp/rar_avalanche.py            # 코어 확산 vs SipRound (보조)
```
