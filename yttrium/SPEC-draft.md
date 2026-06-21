# yttrium 사양 초안 (v0.2-pre)

> *경고: 본 문서는 **설계 초안**이다. 구현·형식검증 이전 단계이며, 아래 §10·§11의
> 미해결 항목(라운드수·전체 암호분석·KAT)이 닫히기 전에는 어떤 환경에서도 사용하지 말 것.*
>
> **yttrium** = `ypsilenti`의 **Lai-Massey + ARX 재설계**. Y-패밀리(YSC→YHash→
> ypsilenti→yttrium, 원소 39번 Y). σ-GLM(선형 XOR-broadcast)을 *비선형 ARX 결합기*로
> 교체하되, 가역성은 **영합(zero-sum) Lai-Massey reduction**으로, 약점 차단은
> **all-8 GF α^k orthomorphism**으로 확보한다. 근거: Grassi, "Generalizations of the
> Lai-Massey Scheme: the Blooming of Amaryllises" (IACR ePrint 2022/1245). 체 곱셈
> 대신 **ARX(모듈러 가산)** 로 적응(CPU 효율 + 보편 상수시간), Farfalle-tree 유지.

## 0. 동기 — 왜 재설계인가

`ypsilenti`/σ-GLM의 라운드는 `S=⊕xᵢ; t=F(S); xᵢ⊕=t; σ; π` 로, 결합(broadcast)이
**XOR(선형)** 이다. 본 저장소 R2 분석에서 이 구조가 **확률-1 선형 차분을 R\*=w(=8)
라운드까지** 보유함을 정확히 보였다(`milp/inactive_subspace.py`). yttrium은 broadcast
XOR를 **비선형 ARX 결합기**로 바꾼다. 그 결과 발생하는 가역성 문제(아래)를 *Feistel 없이*
영합 reduction으로, 잔존 차분을 all-8 orthomorphism으로 닫는다(§9 실측).

## 1. 매개변수 (초안 — 일부 *잠정*)

| 항목 | 값 | 비고 |
|------|----|----|
| PARAM_VERSION | **"yttrium-params-v0.2-pre"** | 검증 전 동결(§10-F); 변경 시 bump |
| 상태 | 8 × u32 = **256 bit** | ypsilenti와 동일 |
| 블록 = 상태 | 32 byte | Farfalle 표준 |
| chaining value / digest | 128 bit (16 byte) | truncation 규칙 §8 |
| GF 필드 | GF(2³²), p(x)=x³²+x²²+x²+x+1, red `0x400007` | *primitive ✓* (ypsilenti Q1p 재사용) |
| reduction 부호 ε | **[+,−,+,−,+,−,+,−]** (Σε=0) | 영합 = 가역의 토대(§2.1) |
| 결합기 회전 (α,β) | **(8, 9)** | §9; (9,10)/(8,3)도 수용(차이 작음) |
| F 항 수 | **3-term** | 4-term은 +1 bit뿐(한계효용) |
| σ orthomorphism | **all-8 레인** α^{k}, k=**[1,2,3,4,5,6,7,9]** | §4·§9 — 부분 σ는 약점; Σ=37 α-step(튜닝) |
| π | P=[7,4,1,6,3,0,5,2] = (5i+7) mod 8 | 단일 8-cycle |
| RC | SHA-256 K[r] (NUMS, 비반복) | §7 |
| 라운드 (R_b,R_c,R_mask) | **변형 패밀리 §1.1** (기본 `yttrium-(8,12,24)`) | unkeyed acc-충돌이 R_b 결정(§10-C) |
| T_max, MAX_TREE_DEPTH | 8, 32 | ypsilenti와 동일 |

## 1.1 변형 패밀리 — `yttrium-(R_b, R_c, R_mask)`

라운드수를 **이름에 명시**한다(보안 주장 투명화). 임의 `(R_b,R_c,R_mask)`가 유효 인스턴스이며,
아래는 권고 인스턴스 + 보안 주장이다. 근거: §9·§10-C 실측 + 외삽(`milp/yttrium-round-count.md`).

**라운드 ↔ acc-충돌 매핑** (all-8 σ, (α,β)=(8,9); GPU N=2³⁰ 측정 R2=2⁻¹⁵·⁴, R3=2⁻²³·¹(floor);
slope +7.7 선형 외삽; acc-비용 = 1/best-DP 표준모델. **측정 worst-δ는 best-DP 상한 → acc-충돌은 하한**):

| R_b | worst-DP | unkeyed acc-충돌 |
|----|----|----|
| 4 | ≈2⁻³¹ | ≳2³¹ (**깨짐**) |
| 8 | ≈2⁻⁶¹ | ≳2⁶¹ (≈birthday, 측정상한이라 실제 ≥) |
| 9 | ≈2⁻⁶⁹ | ≳2⁶⁹ (청정 >2⁶⁴) |
| 10 | ≈2⁻⁷⁷ | ≳2⁷⁷ (마진) |

**권고 인스턴스:**

| 변형 | 용도 | unkeyed 충돌 | keyed 키혼합(R_mask) | 상대속도 |
|------|------|----|----|----|
| `yttrium-(10,14,24)` | 보수 unkeyed 크립토 (고마진) | acc≳2⁷⁷; 합성 20+ → 2nd-pre≳2¹²⁸ | 강 | 1.0× |
| `yttrium-(8,12,24)` | **기본** unkeyed 크립토 (yhash-class) | acc≳2⁶¹ (≈birthday) | 강 | ~1.3× |
| `yttrium-(4,6,12)` | keyed-lite (키스케줄 강화) | 비저항(≳2³¹) — **keyed 전용** | 강(R_mask=12) | ~2× |
| `yttrium-(4,6,8)` | lite / 비적대 (ypsilenti-호환) | 비저항(≳2³¹) | 약 | ~2.2× |

(속도는 라운드 총량 대략비; 정밀 벤치 별도. keyed 모드는 마스크 비공개 → aligned-pair acc-충돌이
오프라인 불가하므로 (4,6,\*)도 **keyed 사용 시 안전**; R_mask이 키 흡수도 담당하므로 (4,6,12)가 키혼합 우위.)

> **정직(과장 금지):** 위 acc/합성 수치는 N=2³⁰ floor(~2⁻²³) 너머 **선형 외삽**(절대 trail 경계 아님;
> plateau/가속 둘 다 가능, s=6~7.7 bracket). acc-비용은 **표준 모델**(단일 지배특성 work=1/best-DP);
> 출력차 분포가 집중되면(c→p) 최대 `p^{-1/2}`까지 싸질 수 있어(보안지수 절반) 동일 라운드의 unkeyed
> 주장이 약화될 수 있음 — 미측정(§10-D/R5). yhash 동결값 (8,12,24)도 본 분석상 acc≈2⁶¹로 동일
> 수준(패밀리 일관). rotational-XOR·boomerang·linear-hull·차분 클러스터링 미측정 → 추가 마진 사유.

## 1.2 yttrium-large — u64 형 (yhash 크기 대응)

`ypsilenti↔yhash` 관계처럼 yttrium의 **1024-bit 형**. 구조 동일, 워드폭만 u64.

| 항목 | u32 형(기본) | u64 형(yttrium-large) |
|------|----|----|
| 상태 | 8 × u32 = 256 bit | **16 × u64 = 1024 bit** |
| digest | 128 bit | **256 bit** (앞 8 워드) |
| GF 필드 | GF(2³²) red 0x400007 | **GF(2⁶⁴) red 0x1B** (primitive, ypsilenti↔yhash와 동일) |
| π | (5i+7) mod 8 | **(5i+7) mod 16** = [7,12,1,6,11,0,5,10,15,4,9,14,3,8,13,2] |
| ε | [+,−]×4 (Σ=0) | **[+,−]×8** (Σ=0) |
| σ k (all-lane) | [1,2,3,4,5,6,7,9] | **[1,2,…,15,17]** (skip 16→17; Σ=137) |
| (α,β) | (8,9) | (8,9) *잠정*(u64 회전 재튜닝 §11) |
| F 오프셋 | (7,17)(3,21)(9,29) | 동일(mod 64; 차분 distinct→weight 6) |
| RC | SHA-256 K[r] | **SHA-512 K[r]** (80개, 비반복), 레인 r mod 16 |
| T_max | 8 | 8 (블록=128 byte) |

**검증(직접 측정):** u64 라운드 **가역 roundtrip ✓**(full n=64, 6R, milp 인라인). 16-레인 σ-power
[1,2,…,15,17]: **GF(2)-선형 R\*=17, prob-1 MSB R\*=2**(`yttrium_lm_subspace.py` n=64). 특이: u32에서
퇴행했던 연속 [1..16]은 u64(GF(2⁶⁴))에선 정상(R\*=17)이나, u32 교훈대로 방어적 skip 채택.

**라운드수(u64 별도):** digest 256-bit → acc-충돌 birthday 2¹²⁸ 기준 best-DP(R_b)≤2⁻¹²⁸ 필요 →
u32(R_b≈9)보다 큼. u64 best-DP slope는 별도 GPU 측정 필요(§11). 잠정 yhash-class.

## 2. ARX 비선형 결합기 + 영합(zero-sum) Lai-Massey reduction (핵심 변경)

라운드의 broadcast를 다음으로 교체한다. **가역은 영합 ε-reduction이 책임지고, 결합기·F는
비가역이어도 무방**(Lai-Massey는 F를 역산하지 않음).

```
ε  = [+1,−1,+1,−1,+1,−1,+1,−1]            # Σεᵢ = 0 (필수). 모든 εᵢ ∈ {+1,−1}, 0 금지.
x'ᵢ = ROTL_α(xᵢ)                           ∀i
S   = Σᵢ εᵢ · x'ᵢ   (mod 2³², 부호 가·감산)  ← 영합 reduction (σ-GLM의 ⊕-sum 폐기)
t   = F(S)
yᵢ  = ROTR_β( x'ᵢ ⊞ t )                    ∀i,  (α,β)=(8,9),  ⊞ = mod 2³²
```

- `⊞`(모듈러 가산)가 carry로 비선형을 주입 → 라운드가 GF(2)-affine이 아님.
- **가역의 토대(항등식):** `Σᵢ εᵢ·y'ᵢ = Σᵢ εᵢ(x'ᵢ ⊞ t) = S ⊞ (Σεᵢ)·t = S` (Σε=0).
  즉 broadcast가 같은 `t`를 더해도 부호합 S는 **보존**된다 → 출력만으로 S 복원 가능.
- `RED`/GF 곱은 σ(§4)에만, 가산은 결합기에만 → **mixed-algebra**(GF(2) ∪ Z/2³²). §10-D 주의.

### 2.1 가역성 — *영합 reduction으로 구조적 해결 (✓)*

σ-GLM은 `⊕(xᵢ⊕t)=⊕xᵢ`(XOR 상쇄)로 가역이었다. 가산 broadcast로 바꾸면 이 상쇄가 깨져,
"덧셈형 Horst 조건" `Φ(Σ)=Σ⊞8·F(Σ)`가 치환이어야 하는데 **2³² 전수로 비치환 확정(✗,
`milp/yttrium-invertibility.md`)**. 그러나 **영합 reduction이 이 조건을 우회**한다:

> 출력 부호합으로 `S = Σᵢ εᵢ·ROTL_β(yᵢ)` 정확 복원 → `t=F(S)` 재평가 →
> `x'ᵢ = ROTL_β(yᵢ) ⊟ t` → `xᵢ = ROTR_α(x'ᵢ)`. **F·Φ의 가역성과 무관하게 라운드 전단사.**
> σ는 가역(치환)이기만 하면 됨(아래 §4: α^k는 치환). 갈래 A(Feistel)·B(비가역 모드교체)
> **모두 불요** — 전-레인 broadcast 확산을 유지하면서 가역.

**검증(실측, `milp/yttrium_lm_invert.py`):**
- n=3·w=8 = **2²⁴ 전수 전단사 (image 16777216/16777216) ✓**, n=4·w=4 = 2¹⁶ 전수 전단사 ✓.
- control: `Σε≠0`(all +1) → **비전단사 49152/65536 ✓** (영합이 load-bearing).
- control: **비가역 garbage-F로도 전단사 ✓** (Lai-Massey: F 가역성 무관).
- α^k(k∈{1,2,3,4,5,6,7,9})는 전부 **perm + XOR-orthomorphism**(α^k(x)⊕x 치환);
  **가산-orthomorphism은 아님**(α^k(x)⊟x 비치환) — 가역은 §2 영합이 담당하므로 XOR-orth로 충분.

## 3. F 함수 (비선형, 단일 워드 S에 적용; *고정·재사용*)

```
F(s) = s ⊕ (s⋘7 ∧ s⋘17) ⊕ (s⋘3 ∧ s⋘21) ⊕ (s⋘9 ∧ s⋘29)
```

- AND 게이트 3쌍(no S-box; rotate·AND·XOR만). 회전 오프셋 {10,18,20}이 *서로 다름*
  → 최소 차분 weight **6**(정확, `milp/trail_fweight.py`). (ypsilenti 원본 (7,17,3,13)은
  17−7=13−3=10 충돌로 weight 2였음 — 본 설계가 그 결함을 수정.)
- **F 자체는 비가역이어도 됨**(§2.1). 단일 워드 S에 적용하므로 결합기·가역과 분리.

## 4. σ-층 — all-8 GF α^k orthomorphism (불변 부분공간 + 잔존 MSB-쌍 차단)

```
yᵢ ← α^{kᵢ} · yᵢ    ∀i ∈ {0..7},   k = [1, 2, 3, 4, 5, 6, 7, 9]   (GF(2³²), red 0x400007)
```

α-곱(branchless): `mask = 0 − (y≫31); α(y) = (y≪1) ⊕ (mask ∧ 0x400007)`. α^k는 k회 반복.
α⁻¹(v) = `(v&1) ? ((v^0x400007)>>1)|0x80000000 : v>>1` (red bit0=1).

**k 집합 선택(튜닝, §9):** all-8 distinct-power가 필수(부분 σ는 MSB-쌍 부활). distinct-power 중
**Σk 최소화**로 σ 비용을 줄이되 GF(2)-선형 R\*(대각 불변 차단)을 유지. 측정: k=[1,2,3,4,5,6,7,9]
(Σ=**37** α-step)이 현행 [1,2,3,5,7,11,13,17](Σ=59)와 **동일**(MSB-쌍 R2=2⁻¹⁵·⁸≈2⁻¹⁵·⁴, GF2-선형
R\*=9, prob-1 R\*=2)하면서 **37% 저렴**. 단순 연속 [1..8](Σ=36)은 GF2-선형 R\*=∞(>12)로 **퇴행**
(8=2³ 포함+완전연속이 선형종속 유발) → 8→9 한 칸이 이를 해소. (`milp/yttrium_tune.cu`.)

**왜 부분 σ가 아니라 all-8인가 (§9 실측이 결정):** 영합 같은-부호 **MSB-쌍 차분**은
*정확-LA 두 척도(prob-1 MSB R\*=2, GF(2)-선형 R\*≈9)에는 보이지 않지만* GPU best-DP에서
고확률로 생존한다. σ 커버리지별 worst-δ best-DP @ (8,9):

| σ 커버리지 | R2 | R3 | R4 |
|---|---|---|---|
| **all-8 (권고)** | **2⁻¹⁵·⁴** | **2⁻²³·¹** (floor) | 2⁻²³·¹ |
| even-4 {0,2,4,6} | 2⁻²·⁰ | 2⁻¹⁰·⁶ | 2⁻²³·¹ |
| σ{0,4} (현행 ypsilenti식) | 2⁻²·⁰ | 2⁻²·⁶ | **2⁻³·¹** |
| empty (framing만) | 2⁻²·⁰ | 2⁻²·⁰ | 2⁻²·⁰ |

부분 σ는 σ 미접촉 레인으로 MSB-쌍을 R≈4까지 통과시킨다(현행 σ{0,4}는 R4=2⁻³·¹로 심각).
**all-8 σ만 모든 레인을 GF-비선형화해 R=2서 noise floor로 붕괴.** distinct power kᵢ는
Amaryllises 대각 불변 부분공간(ePrint 2022/1245 §7.2)도 차단(균일 power는 대각 보존).

> *정직(성능):* all-8 = 라운드당 α-step Σk = 59회(부분 σ{0,4}는 4회). 보안마진과의 명시적
> 트레이드오프. distinct power **집합 최적화**(예: 더 작은 distinct 집합으로 비용↓)는 §11 튜닝 항목.

## 5. π-층

`new[i] = y[P[i]]`, P=[7,4,1,6,3,0,5,2].

## 6. 라운드 함수 (종합)

```
round(state, r):
    state[r mod 8] ⊕= RC[r]                              # ι (RC: §7, 비반복)
    for i in 0..8: xp[i] = ROTL_8(state[i])              # framing
    S = Σᵢ εᵢ·xp[i]   (mod 2³², ε=[+,−,+,−,+,−,+,−])      # 영합 reduction
    t = F(S)
    for i in 0..8: y[i] = ROTR_9(xp[i] ⊞ t)             # ARX 결합기 broadcast
    for i in 0..8: y[i] = α^{k_i}·y[i]   (k=[1,2,3,4,5,6,7,9])   # σ all-8 orthomorphism
    new[i] = y[P[i]] ;  state = new                      # π

round⁻¹(state, r):
    for i: y[P[i]] = state[i]                            # π⁻¹
    for i: y[i] = α^{−k_i}·y[i]                          # σ⁻¹
    for i: v[i] = ROTL_9(y[i])                           # = xp[i] ⊞ t
    S = Σᵢ εᵢ·v[i]                                       # 영합 보존 → S 복원
    t = F(S)
    for i: xp[i] = v[i] ⊟ t ;  state[i] = ROTR_8(xp[i])
    state[r mod 8] ⊕= RC[r]
```

## 7. RC 스케줄 (비반복 NUMS)

> RC는 XOR 주입이라 **차분 투명**. RC의 목표는 **slide·rotational·invariant-subspace** 저항이다.

```
RC[r] = SHA256_K[r]                  (r < 64; SHA-256 라운드상수, NUMS·불규칙·전부 distinct)
주입 레인 = r mod 8                  (상수·레인 모두 라운드마다 변화)
r ≥ 64 (사실상 불필요): RC[r] = SHA256_K[r mod 64] ⊕ (r as u32)
```
현행 ypsilenti의 `RC[r&7]`(라운드 ≥8서 반복 → slide 취약)를 **비반복 K[r]** 로 교체.

## 8. Farfalle-tree — bridge 재정의 (α-roll 보존 논거 폐기)

leaf/internal/root·encode·truncation·LE 엔디안은 ypsilenti와 **동일 구조 이월**.
mask 유도 = **`mask(path) = P_y(IV ⊕ encode(path))`** (positional; 표준 Farfalle의 직렬
roll `k_{i+1}=P(k_i)`는 tree 모드에서 *이미 폐기*됨).

> **bridge 재정의(정직).** ypsilenti의 "σ=α-곱이 동시에 Lai-Massey orthomorphism이자
> 직렬 α-roll mask-roll"이라는 coincidence는 **tree 모드엔 적용되지 않는다** — tree 모드는
> 직렬 α-roll 레지스터를 쓰지 않기 때문. 따라서 'σ가 α-roll을 보존'이라는 정당화는 폐기.
> tree 모드에서 실제 필요한 bridge 조건은 **mask 단사성(Y4)** 뿐이며, 이는
> **(encode 단사 Y1) ∧ (P_y 가역, §2.1)** 으로 환원 — 둘 다 성립. α primitivity·레인 power
> 주기 제약은 tree 모드에 무관(직렬 roll을 쓰는 stream 모드 YSC4/5에만 해당).
>
> σ의 Lai-Massey 역할은 '가역 회복'(이건 영합 reduction 담당)이 아니라
> **GF(2) 불변 부분공간 차단(distinct-μ, ePrint 2022/1245 §7.2)** 으로 축소 재정의된다.

(미검증: P_y의 mixed-algebra(영합 ⊞ ↔ GF α^k)가 mask 분포에 통계 편향을 주는지는 §10-D.)

## 9. 설계 근거 (본 세션 실측; `milp/`)

| 결정 | 근거(측정) | 도구 |
|------|-----------|------|
| 가역 = 영합 reduction | 2²⁴ 전수 전단사 ✓; Σε≠0 비전단사(control) ✓; 비가역 F도 전단사 ✓ | `yttrium_lm_invert.py` |
| 결합기 = ARX (vs σ-GLM) | σ-GLM은 prob-1을 R\*=8까지 보유; ARX는 R=2서 weight≥2 | `inactive_subspace`, `arx_trail_z3`(z3 UNSAT) |
| **σ = all-8 (vs 부분)** | MSB-쌍 best-DP: **σ{0,4} R4=2⁻³·¹·even-4 R3=2⁻¹⁰·⁶ vs all-8 R2=2⁻¹⁵·⁴**(즉시 붕괴) | `yttrium_lm_diff.cu` (GPU) |
| (α,β)=(8,9) | all-8서 (8,9)2⁻¹⁵·⁴/(8,3)2⁻¹⁶·⁵/(9,10)2⁻¹⁷·¹; R3 floor 동일 → 차이 작음 | `yttrium_lm_diff.cu` |
| F=3-term | per-active weight 3-term **6** vs 4-term **7**(+1뿐) | `trail_fweight`(정확 rank) |

측정 한계(정직): **best-DP는 δ-부분집합 탐색의 경험적 상한**(증명 아님; N=2³⁰ floor~2⁻²⁵,
worst-δ 최대화로 겉보기 floor ~2⁻²³). **정확-LA 두 척도가 MSB-쌍 약점을 못 봤다**는 점이
핵심 교훈 — best-DP가 보완. 절대 trail 경계(full-width·rotational-XOR·boomerang·integral)는
미확립 → 라운드수는 잠정(§10-C).

## 10. 검증 의무 (신규 primitive — 전부 reset)

yttrium은 새 primitive다. ypsilenti의 R1–R5(저장소 README)가 *처음부터* 재수행되어야 한다.

- **A. 가역성** (§2.1): **영합 reduction으로 해결(✓)** — 2²⁴ 전수 + 구조 항등식. *닫힘.*
- **B. Farfalle bridge** (§8): tree 모드엔 직렬 roll 없음 → bridge = mask 단사(encode 단사
  ∧ P_y 가역)로 **재정의·환원(✓ 구조)**. P_y mixed-algebra의 mask 분포 편향은 D로 이월.
- **C. 라운드수 정당화** (R2): **변형 패밀리(§1.1)로 해결** — 단일 동결 대신 라운드를 이름에 명시.
  핵심 발견: **unkeyed 공개마스크에서 aligned-pair acc-충돌(비용=1/best-DP)이 R_b 단독을 결정**.
  GPU 감쇠(R2=2⁻¹⁵·⁴, R3=2⁻²³·¹ floor, slope +7.7) 외삽: best-DP≤2⁻⁶⁴ → R_b≈9. ypsilenti 상속
  4/6/8은 unkeyed acc-충돌 ≳2³¹로 **부족**(적대검증 확인) → 범용 unkeyed는 (8,12,24)~(10,14,24),
  (4,6,\*)는 keyed/비적대 전용. 한계: floor 너머 외삽·acc-비용 표준모델(§1.1 정직 블록)·절대 trail
  경계 미확립(ARX SMT timeout). 측정: `milp/yttrium_round_decay.cu`·`yttrium_degree.py`·
  `yttrium-round-count.md`.
- **D. mixed-algebra 암호분석** — **분석 완료(라운드 위협 0, `milp/yttrium-mixed-algebra.md`)**:
  RX·boomerang·differential-linear·linear-hull·structural/slide 5류 모두 직선차분보다 **얕거나 동급**
  → 라운드수 상향 불필요. RX/structural R1 소멸, boomerang R2=2⁻¹⁰·⁹, diff-linear R2=2⁻⁵·⁶, hull 동급
  (α^k 선형이라 hull 다중도 0). **load-bearing: all-8 σ**(부분 σ는 boomerang/RX 부활)·**비반복 RC**
  (주기-8이면 slide 취약). 한계: adversarial refute 미완(시간상 중단)·hull deep-round 외삽(§11).
- **E. GF primitivity(Q1)·encode 단사(Y1)·mask 단사(Y4)**: 0x400007 order=2³²−1(기검증).
  encode 단사 = 16-byte 레이아웃상 (level,pos,idx) 단사(구조). mask 단사 = encode 단사 ∧ P_y 가역
  — **P_y 가역은 레퍼런스 `round_is_invertible` 테스트로 코드 확인**(round⁻¹∘round=id). ✓ 이월·확인.
- **F. 동결 + KAT**(R4): **검증 전 동결 완료** — `PARAM_VERSION="yttrium-params-v0.2-pre"`
  (`FROZEN-PARAMS.md` §2.5), KAT 4변형×벡터(`tests/kat.rs`) + tripwire(`frozen_param_version`).
  동일 버전 ∧ 변형 → bit-exact. ⚠ `-pre`=R1/R5 전이라 검증서 결함 시 변경+버전 bump.
  교차구현 대조·u64 yttrium-large round-count 확정 후 v1 승급은 잔여.
- **G. constant-time / side-channel**(R3) — **평가 완료(`CT-AUDIT.md` §yttrium)**: 타이밍 누출 미검출
  (dudect 가혹: rdtsc·코어고정·N-sweep, |t| 유계 ~3, 키경로 포함) · 캐시 **면역**(비밀-의존 메모리접근
  0건, no-table) · 전력 CPA는 **미보호 구현**의 선형 block⊕mask 누출(generic, 마스킹=구현 의무; 프리미티브
  무관, S-box 부재로 DPA 타깃 적음) · fault 특이저항 없음(표준 대응책). 하드웨어 버그(④) 해당 없음.
  잔여: 마스킹 구현·실HW dudect·정밀 DFA(R5).
- **H. 외부 공개 암호분석**(R5): 최종 관문.

## 11. 미해결 / open

1. **라운드수**(§10-C) — **변형 패밀리(§1.1)로 분리**: `yttrium-(R_b,R_c,R_mask)`, 권고 (10,14,24)/
   (8,12,24)/(4,6,12)/(4,6,8). 잔여: floor 너머 외삽 검증(N≥2³⁶/MILP), acc-비용 `p^{-1}` vs `p^{-1/2}`
   확정, 절대 trail 경계.
2. **(α,β) 최종값** — **(8,9) 확정**(튜닝). (9,10)이 R2서 ~1.7bit 낫지만 R3 floor 동일·라운드수
   무관·cascade 불필요 → (8,9) 유지(문서화된 대안 (9,10)).
3. **σ power 집합 최적화** — **완료**: k=[1,2,3,4,5,6,7,9] (Σ=37, 37%↓) 확정(§4). 추가 최소화 여지
   작음(distinct-positive Σ 하한 근처; [1..8]은 퇴행).
4. **ε 패턴** — **교대 확정**(튜닝): alt vs block MSB-쌍 best-DP 동일(2⁻¹⁵·⁴) → ε 무관, 교대 채택.
5. **mixed-algebra 정밀 분석**(§10-D) — **완료(라운드 위협 0)**. 잔여: adversarial refute 완주,
   hull deep-round 직접측정, RX-차분 full·boomerang MITM·division property(R5/전용도구).
6. yhash 대응(u64) yttrium-large: 순열 코어·구조검증 완료(§1.2), **round-count 미확정**(256-bit
   digest→best-DP slope GPU 측정 필요)·전체 Farfalle-tree 모드 이식 잔여.
7. 동결 v1 승급 — 현재 `v0.2-pre`(검증 전). R1 형식검증·R5 외부분석 통과 후 v1.

## 13. 레퍼런스 구현

`yttrium/src/lib.rs` (Rust, edition 2024, `#![forbid(unsafe_code)]`) — 자족적 scalar 레퍼런스:
영합 LM+ARX 라운드(+`round_inv`)·GF α^k(+α⁻¹)·F·Farfalle-tree 모드·변형 패밀리
`Rounds{r_b,r_c,r_mask}`·keyed/unkeyed 빌더. 테스트 `yttrium/tests/kat.rs`: KAT 4변형×벡터 +
가역성(`round_is_invertible`)·avalanche·분리·streaming. SIMD/parallel 최적화는 후순위(미구현).
*v0.2-pre 미동결* — KAT는 파라미터 변경 시 재생성.

## 12. 변경 이력
- v0.2-pre: 라운드수 변형 패밀리(§1.1) + §10-D 혼합대수 암호분석(라운드 위협 0) + 튜닝 배치
  확정(σ-power k=[1,2,3,4,5,6,7,9] Σ=37 37%↓; (α,β)=(8,9)·ε=교대) + **Rust 레퍼런스 구현+KAT(§13)**.
- v0.1-pre: 가역성 해결(영합 Lai-Massey, Feistel 배제·F 비가역 재사용) + all-8 orthomorphism
  확정(σ-커버리지 best-DP 비교). 워크플로(설계 6렌즈·적대검증) + 오케스트레이터 GPU/LA 실측.
- v0.0-pre: Amaryllises+ARX 초안(덧셈형 Horst 비치환 발견, 갈래 A/B 미정 단계).
