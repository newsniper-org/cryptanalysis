# yttrium 라운드수 정량 정당화 — 변형 패밀리 `yttrium-(R_b,R_c,R_mask)`

> 워크플로(4차원 분석 + 적대검증) + **오케스트레이터 직접 GPU/CPU 실측**. SPEC §1.1·§10-C.
> 결론: 단일 동결 대신 **라운드를 이름에 명시한 변형 패밀리**. unkeyed 공개마스크에서 acc-충돌이
> R_b를 결정하며, ypsilenti 상속 4/6/8은 unkeyed로 **부족**(acc≳2³¹).

## 1. 모드 구조 & 공격 경로 (요약)

unkeyed 해시, mask=P_y(IV⊕encode), IV 고정 → **마스크 공개**. 라운드 함수 = SPEC §6(영합 LM+ARX).
- **R_b** = 블록 압축 `permute(block⊕mask, R_b)` (leaf/internal). 공격입력 진입점.
- **R_c** = finalize `permute(acc⊕mask_mid, R_c)`. acc=⊕블록(선형).
- **R_mask** = mask 유도 + **keyed 키 흡수** `permute(IV⊕encode 또는 key, R_mask)`.

공격: **(a) acc-충돌** — 두 슬롯에 같은 Δ 주입, 출력차 ∇ 일치를 birthday list-match. 차분 mask-투명
(공개마스크). **비용 = 1/best-DP(R_b)** (표준모델). **R_b 단독 방어.** **(b) digest 충돌/2nd-preimage**
— Δblock→permute(R_b)→선형누산→permute(R_c)→trunc. **R_b+R_c 합성** 방어.

## 2. 차분 best-DP 라운드별 감쇠 (지배 척도; GPU 직접측정)

`milp/yttrium_round_decay.cu` (N=2³⁰, floor~2⁻²³, all-8 σ, (α,β)=(8,9)):

```
R1=2^-0.0(MSB쌍 F-비활성 outlier)  R2=2^-15.4  R3=2^-23.1(floor)  R4..R7=2^-23.1(floor)
slope(R2→R3) = +7.7 bit/round
```
R≥3은 floor에 막혀 **선형 외삽**(절대 trail 경계 아님). 앵커 R2/R3.

**외삽 (slope +7.7, acc-비용 1/best-DP). 측정 worst-δ는 best-DP 상한 → acc-충돌은 하한(≳):**

| R_b | worst-DP | acc-충돌 | 판정 |
|----|----|----|----|
| 4 | ≈2⁻³¹ | ≳2³¹ | **깨짐** (unkeyed) |
| 8 | ≈2⁻⁶¹ | ≳2⁶¹ | ≈birthday 2⁶⁴ (측정상한이라 실제 ≥) |
| 9 | ≈2⁻⁶⁹ | ≳2⁶⁹ | 청정 >2⁶⁴ |
| 10 | ≈2⁻⁷⁷ | ≳2⁷⁷ | 마진 |

합성(path b) R_b+R_c: 2nd-preimage 2⁻¹²⁸은 합성 ≈20에서 외삽 충족(R_b=8,R_c=12 → 20).

**독립 재현(축소폭 n=8, CPU `verify_n8_slope.py`):** R1=2⁻⁰, R2=2⁻⁷·⁰² (slope +7.0, GPU n=32 +7.7과 정합).

## 3. acc-충돌 비용 모델 (적대검증 정정)

aligned-pair: ∇0(b0)=∇1(b1) birthday match. 충돌확률 c=Σ_v P(v)² ∈ [p², p] (p=best-DP),
작업 = c^{−1/2} ∈ [p⁻¹, p⁻¹ᐟ²].
- **표준(단일 지배특성, c≈p²): work = 1/best-DP = p⁻¹** ← 본 분석 채택(`rb_acc_cost_v2.py`).
  (적대검증 F1: 초기 `rb_wagner_cost.py`의 (1/p)² 제곱 비용은 **과대평가 → 폐기**.)
- **비관(분포 집중 c→p): work = p⁻¹ᐟ²** — 보안지수 절반. 출력차 분포 집중도 미측정 → §5 open.

## 4. 보조 차원

- **대수차수/integral** (`yttrium_degree.py`, 직접): 축소폭 R_full=2~3, 실제 8-워드 구조 +2/round →
  풀폭 외삽 R_full≈4~5 → integral/cube 소멸 R_b≥5. **차분(R_b≈9)보다 약함 → 차분 지배.**
- **선형 상관** (`yttrium_linear.py`, 워크플로 분석): F corr 2⁻³, 합성 외삽 ~22~26(heuristic).
  linear-hull(다중 trail 보강) 미측정 → §5 open(낙관 위험).

## 5. 변형 패밀리 & 권고

`yttrium-(R_b, R_c, R_mask)` — 임의 튜플 유효, 권고 인스턴스:

| 변형 | 용도 | unkeyed 충돌 | keyed 키혼합 | 상대속도 |
|------|------|----|----|----|
| `yttrium-(10,14,24)` | 보수 unkeyed (고마진) | acc≳2⁷⁷; 2nd-pre≳2¹²⁸ | 강 | 1.0× |
| `yttrium-(8,12,24)` | **기본** unkeyed (yhash-class) | acc≳2⁶¹ (≈birthday) | 강 | ~1.3× |
| `yttrium-(4,6,12)` | keyed-lite (키스케줄 강화) | 비저항 ≳2³¹ (**keyed 전용**) | 강(R_mask=12) | ~2× |
| `yttrium-(4,6,8)` | lite/비적대 (ypsilenti-호환) | 비저항 ≳2³¹ | 약 | ~2.2× |

keyed 모드: 마스크 비공개 → aligned-pair acc-충돌 오프라인 불가 → (4,6,\*)도 keyed 안전.
yhash 동결 (8,12,24)도 본 분석상 acc≈2⁶¹ 동급(패밀리 일관). ypsilenti (4,6,8)는 unkeyed 미달 outlier.

## 6. 한계 (정직 — 절대 trail 경계 아님)

1. **외삽**: 2⁻⁶⁴/2⁻¹²⁸은 직접측정 불가(N=2³⁰ floor~2⁻²³). slope 선형 외삽이며 plateau(→F-floor 6)/
   가속 둘 다 가능(s=6~7.7 bracket). N≥2³⁶ 또는 MILP 하한 필요(ARX SMT는 R≈6 timeout).
2. **acc-비용 모델**: `p⁻¹`(표준) vs `p⁻¹ᐟ²`(비관) 미확정 — 후자면 동일 R_b의 unkeyed 주장 약화.
3. **미측정 경로**: rotational-XOR·boomerang·linear-hull·차분 클러스터링·Wagner-혼합 (SPEC §10-D, R5).
4. δ-class는 영합 같은부호 MSB-쌍(worst-δ); 전체 δ-공간 전수 아님.

## 7. 재현

```bash
cd milp
nvcc --std=c++14 -O3 -o yttrium_round_decay yttrium_round_decay.cu && ./yttrium_round_decay  # GPU, R1..7 × σ-커버리지
python3 yttrium_degree.py --rmax 6      # 차수성장 R_full
python3 verify_n8_slope.py              # n=8 축소폭 slope 재현
python3 rb_acc_cost_v2.py               # acc-충돌 비용모델 → R_b 매핑
```
