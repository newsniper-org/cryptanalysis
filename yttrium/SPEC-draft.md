# yttrium 사양 초안 (v0.0-pre)

> *경고: 본 문서는 **설계 초안**이다. 구현·형식검증 이전 단계이며, 아래 §10·§11의
> 미해결 항목(가역성·Farfalle bridge·라운드수·전체 암호분석)이 닫히기 전에는
> 어떤 환경에서도 사용하지 말 것.*
>
> **yttrium** = `ypsilenti`의 **Amaryllises + ARX 재설계**. Y-패밀리(YSC→YHash→
> ypsilenti→yttrium, 원소 39번 Y). σ-GLM(선형 Lai-Massey broadcast)을 *비선형*
> 결합기로 교체한다. 근거: Grassi, "Generalizations of the Lai-Massey Scheme: the
> Blooming of Amaryllises" (IACR ePrint 2022/1245)의 Amaryllises 구성을, 체 곱셈
> 대신 **ARX(모듈러 가산)** 로 적응(CPU 효율 + 보편 상수시간).

## 0. 동기 — 왜 재설계인가

`ypsilenti`/σ-GLM의 라운드는 `S=⊕xᵢ; t=F(S); xᵢ⊕=t; σ; π` 로, 결합(broadcast)이
**XOR(선형)** 이다. 본 저장소 R2 분석에서 이 구조가 **확률-1 선형 차분을 R\*=w(=8)
라운드까지** 보유함을 정확히 보였다(`milp/inactive_subspace.py`). yttrium은 broadcast
XOR를 **비선형 ARX 결합기**로 바꿔 이 약점을 라운드 2 안에 제거한다(아래 §9 실측).

## 1. 매개변수 (초안 — 일부 *잠정*)

| 항목 | 값 | 비고 |
|------|----|----|
| 상태 | 8 × u32 = **256 bit** | ypsilenti와 동일 |
| 블록 = 상태 | 32 byte | Farfalle 표준 |
| chaining value / digest | 128 bit (16 byte) | truncation 규칙 §8 |
| GF 필드 | GF(2³²), p(x)=x³²+x²²+x²+x+1, red `0x400007` | *primitive ✓* (ypsilenti Q1p 재사용) |
| 결합기 회전 (α,β) | **(8, 9)** | §9 GPU 튜닝 최상위; (8,3)도 수용 |
| F 항 수 | **3-term** | 4-term은 +1 bit뿐(한계효용) |
| σ 레인 | {0, 4} ← α¹, α³ | 증설 무익(§9) |
| π | P=[7,4,1,6,3,0,5,2] = (5i+7) mod 8 | 단일 8-cycle |
| RC | SHA-256 K[r] (NUMS, 비반복) | §7 |
| 라운드 R_b/R_c/R_mask | **잠정** 4 / 6 / 8 | §10에서 정량 정당화 필요 |
| T_max, MAX_TREE_DEPTH | 8, 32 | ypsilenti와 동일 |

## 2. ARX 비선형 결합기 (핵심 변경)

라운드의 broadcast를 다음으로 교체한다 (Amaryllises의 가산 적응; SPECK식 rotate-add-rotate):

```
S = ⊕ᵢ xᵢ ;   t = F(S)
yᵢ = ROTR_β( ROTL_α(xᵢ) ⊞ t )      ∀ i ∈ {0..7},   (α,β)=(8,9),  ⊞ = mod 2³²
```

- `⊞`(모듈러 가산)가 carry로 비선형을 주입 → 라운드가 GF(2)-affine이 아님 → 넓은
  확률-1 부분공간 소멸. 회전 framing(α 전·β 후)이 가산의 **MSB-only 확률-1 차분**을
  옮겨 빠르게 무력화(§9 실측: MSB 통과확률 1.0→0.49, R=2서 weight≥2 증명).
- `RED`/GF 곱은 σ(§4)에만, 가산은 결합기에만 → **mixed-algebra**(GF(2) ∪ Z/2³²). §10 주의.

### 2.1 가역성 — *미해결(§10-A)*
σ-GLM은 `⊕(xᵢ⊕t)=⊕xᵢ`(t 상쇄, n 짝수)로 S 복구가 자명해 가역이었다. ARX 결합기는
이 상쇄가 깨진다. 가역(= 순열) 유지에는 **덧셈형 Horst 조건** `S ↦ S ⊞ w·F(S)` 가
mod 2ⁿ 치환이어야 하며, rotate-add-rotate 형태에서 이것이 충분한지 *형식적으로 미확립*.
대안: **비가역 압축(random-function 모델)** 채택 — 해시 용도엔 가역이 불필요하며
preimage 저항엔 오히려 유리. 둘 중 하나를 §10에서 확정한다.

## 3. F 함수 (비선형, 단일 워드 S에 적용)

```
F(s) = s ⊕ (s⋘7 ∧ s⋘17) ⊕ (s⋘3 ∧ s⋘21) ⊕ (s⋘9 ∧ s⋘29)
```

- AND 게이트 3쌍(no S-box; rotate·AND·XOR만). 회전 오프셋 {10,18,20}이 *서로 다름*
  → 최소 차분 weight **6**(정확, `milp/trail_fweight.py`). (ypsilenti 원본 (7,17,3,13)은
  17−7=13−3=10 충돌로 weight 2였음 — 본 설계가 그 결함을 수정.)

## 4. σ-층 (불변 부분공간 차단)

```
y0 = α¹ · y0 ;   y4 = α³ · y4     (GF(2³²) α-곱; 나머지 레인 불변)
```
α-곱(branchless): `mask = 0 − (y≫31); (y≪1) ⊕ (mask ∧ 0x400007)`. Amaryllises도 대각
불변 부분공간을 가지므로(ePrint 2022/1245 §7.2) σ(distinct-μ)+RC가 *여전히 필요*.

## 5. π-층

`new[i] = y[P[i]]`, P=[7,4,1,6,3,0,5,2].

## 6. 라운드 함수 (종합)

```
round(state, r):
    state[r mod 8] ⊕= RC[r]              # ι (RC: §7, 비반복)
    S = ⊕ᵢ state[i]
    t = F(S)
    for i in 0..8: state[i] = ROTR_9(ROTL_8(state[i]) ⊞ t)   # ARX 결합기
    state[0] = α¹·state[0] ;  state[4] = α³·state[4]          # σ
    new[i] = state[P[i]] ;  state = new                       # π
```

## 7. RC 스케줄 (비반복 NUMS)

> RC는 XOR 주입이라 **차분 투명**(MSB 약점은 §2의 (α,β)가 담당). RC의 목표는
> **slide·rotational·invariant-subspace** 저항이다.

```
RC[r] = SHA256_K[r]                  (r < 64; SHA-256 라운드상수, NUMS·불규칙·전부 distinct)
주입 레인 = r mod 8                  (상수·레인 모두 라운드마다 변화)
r ≥ 64 (사실상 불필요): RC[r] = SHA256_K[r mod 64] ⊕ (r as u32)
```
현행 ypsilenti의 `RC[r&7]`(라운드 ≥8서 반복 → slide 취약)를 **비반복 K[r]** 로 교체.

## 8. Farfalle-tree — *재사용 + bridge 재설계 필수(§10-B)*

leaf/internal/root·encode·mask 유도(`mask = P_y(IV ⊕ encode)`)·XOR 누적·truncation·
LE 엔디안은 ypsilenti와 **동일 구조 이월**. 단:

> **⚠ Farfalle bridge 재설계 필수.** ypsilenti/YSC 계열의 우아함은 σ=GF α-곱이 동시에
> (i) Lai-Massey orthomorphism과 (ii) Farfalle mask-roll을 충족하는 "natural bridge"였다.
> yttrium의 결합기가 GF 곱이 아닌 **모듈러 가산(mixed-algebra)** 이 되면서 이 bridge가
> 깨진다 → **mask-roll/orthomorphism을 새로 설계·정당화**해야 한다(α-roll 유지 또는
> ARX 구조에 맞는 새 bridge 발굴). 순열만 교체한 drop-in은 불가.

## 9. 설계 근거 (본 세션 실측; `milp/`)

| 결정 | 근거(측정) | 도구 |
|------|-----------|------|
| 결합기 = ARX (vs σ-GLM) | R=2 best-DP **σ-GLM 2⁻⁴ vs ARX 2⁻¹⁶** (~2¹² 강함); ARX는 R=2서 **weight≥2 증명**, σ-GLM은 prob-1을 R\*=8까지 보유 | `arx_gpu`, `arx_trail_z3`(z3 UNSAT), `inactive_subspace`(정확 LA) |
| (α,β)=(8,9) | sweep 196쌍 + 정밀 재순위: best≈2⁻¹⁷, worst≈2⁻¹³·⁸(~3.2bit 스프레드); (8,9) 최상위, (8,3) 수용 | `arx_gpu_tune`, `arx_gpu_refine` (GPU) |
| F=3-term | per-active weight 3-term **6** vs 4-term **7**(+1뿐) | `trail_fweight`(정확 rank) |
| σ 레인 {0,4} | 레인 0,4→0,2,4,6 증설해도 R\*=8 불변 | `inactive_subspace` |
| RC 비반복 | RC는 차분 투명 → slide/rotational용; K[r] distinct | (설계) |

측정 한계(정직): GPU best-DP는 *δ-부분집합 탐색의 경험적 상한*(증명 아님); z3는
full-width ARX에서 R≥2 trail 최소화가 timeout(증명은 R=2 weight≥2까지). 절대 trail
경계는 R5/전용 탐색 영역.

## 10. 검증 의무 (신규 primitive — 전부 reset)

yttrium은 새 primitive다. ypsilenti의 R1–R5(저장소 README)가 *처음부터* 재수행되어야 한다.

- **A. 가역성 확정** (§2.1): 덧셈형 Horst로 순열 유지 *증명* 또는 비가역(random-function)
  모델 채택. 보안 모델(R1)의 전제.
- **B. Farfalle bridge 재설계** (§8): mask-roll/orthomorphism을 ARX 구조와 정합.
- **C. 라운드수 정당화** (R2): mixed-algebra(ARX+GF) bit-level 차분/선형 trail로 R_b·R_c·
  R_mask 확정. 현재 4/6/8은 *잠정*(ARX의 빠른 강화로 충분할 가능성↑이나 미검증).
- **D. mixed-algebra 암호분석**: ARX↔GF 상호작용(carry vs α-곱·σ)은 단일-대수보다 분석
  난해. rotational·boomerang·integral 별도.
- **E. GF primitivity(Q1)·encode 단사(Y1)·mask 단사(Y4)** 등 대수 의무는 ypsilenti에서
  이월 가능(F·결합기와 무관)하나 재확인.
- **F. 동결 + KAT**(R4): 단일 권위 파라미터 + 교차구현 KAT.
- **G. constant-time**(R3): 결합기가 ROTL/ADD/ROTR(보편 1c CT) → ypsilenti보다 *유리*
  (곱셈 없음). dudect + 정적 감사.
- **H. 외부 공개 암호분석**(R5): 최종 관문.

## 11. 미해결 / open

1. **가역성**(§2.1, §10-A) — 가장 시급. 미정 시 보안 모델 자체가 바뀜.
2. **Farfalle bridge**(§8, §10-B) — 순열만 교체 불가.
3. **라운드수**(§10-C) — 잠정값.
4. **(α,β) 최종값** — (8,9) vs (8,3); N=2³⁴ 재분리로 확정 가능(실익 작음).
5. yhash 대응(u64) yttrium-large 여부.

## 12. 변경 이력
- v0.0-pre: 본 세션 설계 탐색(Amaryllises+ARX, GPU/z3/LA 실측)을 초안화. 구현·검증 전.
