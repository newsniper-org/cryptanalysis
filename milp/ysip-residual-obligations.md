# YSip 잔여 의무 처리 — 차분·선형·회전·상수·라운드수·KAT (v0.0-pre → v0.1-pre)

> SPEC §6 의 6개 운영화 의무를 자체 암호분석으로 처리. 모든 1차 결론은 **적대적 검증 워크플로**
> (차원별 독립 회의론자가 스크립트 재실행·반증 시도, `wf_bdf91ff3-44b`)를 통과했고, 그 과정에서
> 드러난 **프레이밍 과대주장 5건을 정정**했다(아래 §검증 반영). 결론(설계 변경 0)은 생존.
>
> **정직 한계**: 절대 차분/선형 trail 경계는 z3 64bit R≥3 timeout 으로 미확립(yttrium 문서와
> 동일 한계). 라운드수는 SipHash **상대** 정당화(절대 증명 아님). 외부 검토 전.
>
> 재현: `ysip_diff.py`(SMT 차분), `ysip_lm_diff[.cu]`(GPU best-DP), `ysip_rotational.py`,
> `ysip_linear.py`; 교차구현 KAT `ysip/ref_check.py` ≡ `ysip/examples/gen_kat.rs`.

## 요약 (전 의무 처리, 설계 변경 0)

| # | 의무 | 결과 (검증후) | 설계 영향 |
|---|------|------|-----------|
| 1 | 차분 | **YSip > SipHash 정확**: R1 1>0, R2 **7>4** (z3 K별 UNSAT/SAT 증명). | 없음 |
| 2 | 선형 | per-add \|corr\| = SipHash (회전불변, n=5 multiset 동일 증명). 멀티라운드 hull = **open**. | 없음 |
| 3 | 회전 | YSip 라운드 RX **근소 열세**(~0.3bit/round), 동일차수. **키의존 δ가 구성차단** → RC 불요. | 없음 |
| 4 | 상수 | (8,9) **SMT-exact 최강**(R2=7 > (12,29)·(16,21)=6) + RX 최강. | (8,9) 유지 |
| 5 | 라운드수 | SipHash 상대(차분 우위·회전 동급·구성 동일). 절대 다라운드 경계는 **미확립**(정직). | (2,4)/(3,6) 유지 |
| 6 | KAT | 교차구현(Rust≡Python) bit-exact 66벡터 → 동결 + PARAM_VERSION bump. | v0.1-pre |

## 1. 차분 (differential) — confirmed

**도구**: `ysip_diff.py` (SMT-LIB2 QF_BV 64bit + z3, Lipmaa–Moriai). SipHash/YSip 모드는 결합기
(⊞ vs rar) 래핑만 다름 → 동일 도구 *상대* 보정 공정.

정확 최소 trail weight (z3 K별 UNSAT→SAT 증명, `-T:500`):

| R | SipHash | YSip(8,9) |
|---|--:|--:|
| 1 | 0 (K=0 SAT) | **1** (K=0 UNSAT, K=1 SAT) |
| 2 | 4 (K=3 UNSAT, K=4 SAT) | **7** (K=6 UNSAT, K=7 SAT) |
| ≥3 | z3 timeout | z3 timeout |

- **YSip가 R1,R2 모두 SipHash보다 엄격히 높다(차분 우위).** 검증으로 확정: 스크립트가 한때
  R2=`5*`(timeout 하한)로 표기했으나 `-T:500` 으로 **정확히 7** 임을 증명 → 결론은 *과소* 표기였음.
- **기전(정밀)**: weight-0 자명 trail(all-MSB 입력차분, mod-2⁶⁴ 가산서 MSB는 carry-free)은
  **SipHash R1** 에 존재(1라운드 DP=2⁰ 실측). `rar`의 **ROTL₈** 가 x-MSB(bit63)→bit7 로 보내
  그 자명 trail 을 깬다(YSip R1: K=0 UNSAT → weight≥1, 1라운드 all-MSB DP=2⁻³). R2의 저weight
  trail 은 all-MSB 아님(dv0 bits{63,18}) — 기전은 R1 에 적용됨(이전 초안의 "R2 자명trail" 표기 정정).
- **인코딩 검증**: L-M validity/weight 를 n=5 전수(32768쌍)로 brute-force 대조 — 0 false-pos/neg.
  ADDMASK=2⁶³−1(MSB 제외) 확인. ROTL_A 방향이 Rust `rar`와 정합. width=64 = 비축소 진짜 64bit.
- R≥3 은 z3 timeout(ARX SMT 본질적 난제; yttrium 동일). **절대경계 아님.**

**GPU 경험적 best-DP** (`ysip_lm_diff`, N=2³⁰, 24bit-fold, floor~**2⁻²³·²**, δ 54종, deterministic):

| | R2 | R3 | R4 |
|---|--:|--:|--:|
| SipHash | 2⁻⁶·⁴ | 2⁻²¹·³ | floor |
| YSip(8,9) | 2⁻¹¹·³ | 2⁻²³·¹(floor) | floor |

R2 는 max-bucket≫floor 라 실신호(Poisson 1σ ±0.003bit); YSip < SipHash(강함) 재확인.
R3+ 는 fold floor(2⁻²³·²) 도달 = 측정한계(차분정보 0), 절대경계 아님. (이전 floor 표기 2⁻²⁵ 는 오기 → 정정.)

## 2. 선형 (linear) — confirmed(W1) / open(hull)

- **(W1, 증명)** `rar = ROTR_B ∘ ⊞ ∘ ROTL_A`, 회전은 GF(2)-선형 전단사 → 단일 가산의 선형상관
  **multiset 이 비트단위 불변**(n=5 전수: add·rar top=[.125,.25,.5,1.0] 동일). ⟹ **per-add 선형
  weight = SipHash**. best 비자명 \|corr\|=0.5(weight1), LSB corr=1(weight0).
- **(1비트 라운드상관 — 비정보적, 신호 0)**: 256×256 bias-matrix MAX 는 R1부터 **max-of-노이즈**
  (2⁻⁷·⁷⁶ 기대)에 묻힘. 재측정 R1~R5 ≈ 2⁻⁷·⁸ = **독립랜덤 대조군 2⁻⁷·⁷²와 통계적 동일** →
  1비트 선형 신호 0. *감쇠표 아님*(이전 초안의 "floor 2⁻¹⁰" 는 per-cell std 오라벨 → 정정).
- **(미해결, open)** 멀티라운드 **linear-hull 미측정**. `rar`는 피연산자 비대칭(ROTL은 누산입력에만,
  ROTR은 합에만)이라 SipHash 라운드의 전역 conjugation 이 **아님** → per-add 동등이 hull 동등을
  함의하지 **않는다**. 따라서 "선형 ≥ SipHash"는 **미입증**(이전 초안 주장 철회). 차분축에서
  교차라운드 정렬이 YSip를 더 강하게 만든 정황(R2 7>4)이 선형서도 유리할 *가능성*은 있으나 미검증.
  → **선형 hull = 외부 검토 잔여 과제**(ARX SMT 선형(Wallén)은 알려진 난제, 미구현).

## 3. 회전 / RX (rotational, ARX 1순위) — caveat / 결론 생존

**도구**: `ysip_rotational.py` (numpy, **동일 seed 공정비교**·multi-seed 평균; 적대검증 지적 반영).

- **sanity**: 단일 ⊞ γ=1 rotational 2⁻¹·⁴² (이론 2⁻¹·⁴¹⁵ 일치 → 도구 검증). Python round ≡
  Rust(0 mismatch/100k), siphash 모드 ≡ 진짜 SipRound(0/200k).
- **라운드 RX-prob 감쇠** (순수 rotational δ=0, best γ; 공정 seed):

| R | SipHash | YSip(8,9) | per-round 감쇠 |
|---|--:|--:|--|
| 1 | 2⁻⁶·⁴² | 2⁻⁶·²⁴ | — |
| 2 | 2⁻¹³·⁴⁵ | 2⁻¹³·⁰⁶ | Sip 7.03 / YSip 6.82 bits |
| ≥3 | ≤floor | 2⁻¹⁸·⁸(R3), ≥4 floor | — |

  **정정**: YSip는 SipHash보다 라운드당 **~0.2~0.4 bit 근소 열세**(rar 추가회전이 RX-path 약간 연장).
  "YSip ≈ SipHash"는 "근소 열세이나 동일차수"로 정정. R6 외삽 양쪽 ≪2⁻⁴⁰.
- **구성 차단(정정된 근거)**: bare IV 회전대칭만으로는 불충분. 실제 기전 = 초기상태 `v=IV⊕k`에서
  RX-XOR 차분 `δ(v)=v⊕ROTL_γ(v)` 가 **미지의 키 k 에 의존**(k0 별로 δ 상이) → 키독립 RX trail
  불가능(single-key 완전차단). 또 IV0≠IV2 라 한 k0 가 v0,v2 동시 rotational 불가(related-key 부분차단).
- **RC 결정 — 불요(생존)**: 라운드 RX 가 SipHash *차수*이고(근소 열세는 0.3bit), 키의존 δ가 구성단계
  차단(SipHash와 동일 논거). RC 도입은 SipHash 이탈+성능손실만, 이득 없음. 단 정직히: 방어의 근거는
  **per-round 우위가 아니라 양쪽 공유하는 구성차단**이다. **미측정**: δ≠0 라운드-내재 RX-XOR trail
  (구성논거로 커버되나 라운드 weight 자체는 미측정).

## 4. 상수 튜닝 (A,B) — caveat / (8,9) 유지(강화)

| (A,B) | SMT 정확 R2 (provable) | GPU best-DP R2 (경험 상한) |
|---|--:|--:|
| **(8,9)** | **7** (K=6 UNSAT, K=7 SAT) | 2⁻¹¹·³ |
| (12,29) | 6 (K=5 UNSAT, K=6 SAT) | 2⁻¹²·⁶ |
| (16,21) | 6 | 2⁻⁸·⁸ |
| (7,16) | — | 2⁻¹¹·⁷ |

- **(8,9) 유지 — 정정·강화된 근거**: ① **SMT-exact 차분 R2=7 이 최강**(유일한 provable 하한;
  (12,29)·(16,21)=6 능가) ② **RX-prob 최강**(후보 중 최저 확률) ③ 선형 1비트 전 후보 동률(floor).
  GPU 경험 best-DP 는 (12,29)를 +1.3bit 높게(강하게) 매기나, 이는 **trail-clustering 포함 경험
  상한**이라 provable bound(SMT)에서 **역전**된다((8,9) 우위). (12,29)는 avalanche 확산만 modest 우위.
- 이전 초안의 "강한 클러스터+R3 소멸" 근거는 floor 오기(2⁻²⁵→2⁻²³·²) 포함·강조점 오귀속 → **정정**:
  진짜 근거는 SMT-exact·RX 최강. ④ **yttrium 코어와 동일 상수**(파생 정체성·공유 분석 일관성).
  → (12,29)로 바꿀 강한 이유 없음(경험차분 우위는 provable bound 에서 무효).

## 5. 라운드수 정당화 (c,d) — caveat / 정직 재프레이밍

이전 초안 "YSip가 **모든 축**에서 ≥SipHash → 마진 상속"은 **회전축에서 거짓**(§3, YSip 근소 열세)이고
1비트 선형은 노이즈(§2)라, 그대로는 과대주장 → **정정**:

1. **구성 동일**: YSip 구성 = SipHash 구성(키흡수·워드패딩·finalize·길이인코딩 동일; 결합기만 rar).
2. **차분축**: YSip per-round **엄격히 강함**(R1,R2 정확 7>4). 유일하게 provable 한 우위.
3. **회전축**: **동급**(YSip 근소 열세 ~0.3bit/round, 동일차수). 방어는 양쪽 공유 구성차단.
4. **선형축**: per-add 동일(증명); 멀티라운드 hull **양쪽 미측정**(YSip·SipHash 모두 본 도구 한계).
5. ⟹ 라운드수 (2,4)/(3,6)은 **SipHash 구조적 쌍둥이로서 차용**하고, 차분축 마진(>SipHash)으로 보강.
   **정직**: 이는 절대 다라운드 trail 경계가 **아니며**(z3 R3 timeout), SipHash 의 다년 분석으로
   축적된 hull/boomerang 마진을 **독립 재유도하지 않는다**. "마진 상속"은 구조적 유사성+차분 우위에
   기반한 *유추*다 — 절대경계 부재는 명시(과소포장 아님).
6. SipHash-2-4 는 64bit keyed PRF 표준(hash-flooding 방어), SipHash-4-8 보수변형. ⟹ **YSip-2-4 ≙
   SipHash-2-4**(차분 마진 우위), **YSip-3-6 보수옵션**. 새 설계라 마진 원하면 **YSip-3-6 권고**.

## 6. KAT 동결

- **교차구현**: 독립 Python(`ysip/ref_check.py`, 사양만 보고 작성) ≡ Rust(`examples/gen_kat.rs`)
  **bit-exact**(2변형×3키×11길이=66벡터) → 사양 무모호.
- Rust KAT 테스트(`tests/kat.rs`) 동결(30벡터+스트리밍일치) + `frozen_param_version` tripwire.
- `PARAM_VERSION`: `v0.0-pre` → **`v0.1-pre`** (자체 의무 처리 완료; `-pre`=외부 검토 전, yttrium
  v0.2-pre 와 동일 규율로 유지).

## 7. 완전성 비평 (누락 공격 5축) — no-new-threat

`ysip_completeness.py` (YSip 전용 신규 — 기존 boomerang_*/dl_*.py 는 yttrium-LM 8레인용이라 재사용
불가). 모델 Rust/Python 레퍼런스와 bit-exact 교차검증 후:

| 축 | 결과 | 근거 |
|----|------|------|
| 슬라이드 | 무위협 | 라운드상수 없으나 ① 블록당 데이터주입 `v3^=m … v0^=m` 이 라운드열 분리 ② keyed init `v=IV⊕k` 가 순열입력 은닉 ③ finalize 가 *다른 길이*(d≠c) ④ 출력=64bit XOR-fold 라 f I/O 비관측. SipHash 논거 전이. |
| 부메랑/회전-차분 | 무위협 | 검증된 역라운드(`f⁻ᴿ∘fᴿ=id`)로 state-level 4-tuple: 복귀율 R2=2⁻²·⁰ → R3=2⁻¹²·⁶ → **R4 ≤2⁻²⁰ floor(0/2²⁰)**. 회전-차분이 순수 rotational 대비 무이득. rar ROTL_A 가 additive-BCT MSB switch 차단. |
| 차분-선형(DL) | 무위협(**caveat**) | bare-순열 DL 상관이 R1-R3 ≈2⁰(ARX carry-free LSB 구조)이나 **YSip ≡ SipHash**(R4 2⁻²·¹ vs 2⁻²·³, R5 2⁻⁸·⁸ 동일). **구성**에선 XOR-fold 가 lane0 국소 고상관을 상쇄 → finalize R=4서 ~2⁻⁸ floor 붕괴. ⇒ 직선차분 못 넘고 fold 가 죽임(SipHash 동일). |
| 고정점/약한키 | 무위협 | 유일 고정점 `f(0,0,0,0)=0` 이 **도달불가**: 영상태는 IVᵢ⊕kᵢ=0 ∀i 필요하나 v0,v2 가 k0 공유·IV0≠IV2 (v1,v3·k1·IV1≠IV3). 2²² 탐색서 영점뿐. 대칭화 약키류 없음(IV0⊕IV2, IV1⊕IV3 ∉{0,~0}). |
| 길이확장/멀티충돌/절단 | 무관 | keyed PRF·비가역 fold·은닉상태 → 길이확장 없음; 64bit birthday(2³²)는 PRF 수용범위(충돌저항 비목표), SipHash 동일. |

> **DL caveat (정직 기록)**: bare-순열 DL 상관이 ≤3라운드서 ≈1 (SipHash 동일, ARX carry-free)이고
> **XOR-fold 가 죽인다**. 즉 얕은 깊이의 보안은 라운드믹싱이 아니라 **fold 에 기댄다** —
> YSip-2-4 의 얇은 블록당 c=2 + fold. SipHash 와 동급·미악용이나 명시.

## 8. 적대적 검증 반영 (정정 5건 + 완전성, 결론 생존)

워크플로 `wf_bdf91ff3-44b` 6 에이전트(5축 회의론자 + 완전성)가 스크립트 재실행·반증 시도:
- 차분 **confirmed**(오히려 과소표기 — R2=7 정확 증명). 선형/회전/상수/라운드수 **caveat**. 완전성 **no-new-threat**.
- **정정**: (a) 선형 "≥SipHash" 철회(1비트=노이즈, hull open) (b) 회전 "≈"→"근소 열세"·근거를
  키의존 δ로 (c) 상수 근거를 SMT-exact·RX 최강으로(클러스터 프레이밍 폐기) (d) floor 2⁻²⁵→2⁻²³·²
  (e) 라운드수 "전축 ≥" 철회→차분 우위+구성 유추 (f) DL caveat·영점 도달불가 신규 기록.
  **어떤 결론도 뒤집히지 않음**(설계 변경 0).

## 한계 / 잔여 (정직)

- 절대 차분/선형 trail 경계 R≥3 미확립(z3). **선형 linear-hull(멀티비트) 미측정** = 최대 잔여.
- 라운드수 = SipHash 상대(절대 아님). δ≠0 RX-XOR 라운드 weight 미측정(구성차단으로 커버).
- 외부 암호분석 미수행(=`-pre` 유지 사유). 완전성 비평(슬라이드/부메랑/DL/약한키) = 별도 진행.
- 후순위(사용자 지시): 커널패닉 직전 극단 stress. 하드웨어/측정 아티팩트 해당 없음(전부 알고리즘 레벨).
