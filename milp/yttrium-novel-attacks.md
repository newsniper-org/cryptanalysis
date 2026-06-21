# yttrium 참신한 attack 시도 — state-space model 방법론 외 (신규 위협 없음)

> 워크플로(6각도 + 적대검증) + 오케스트레이터 직접 검증(`yttrium_ssm.py --real 20000`).
> **결론: 어떤 참신한 attack도 §10-D를 넘지 못함. SSM은 기존 결과를 새 경로로 재현·정밀화.**
> 극단 stress(커널패닉류)·하드웨어 공격은 범위 외(후순위). 하드웨어 발견 없음 → 비누출 프로토콜 미발동.

## 시도한 각도 (스펙 파라미터 전부 활용)

| 각도 | severity | 적대검증 | 비고 |
|------|------|------|------|
| SSM (control-theoretic) | none | not-a-weakness | 관측/도달성·불변부분공간·A 고유구조 |
| SSM (시퀀스/BM) | structural-obs | not-a-weakness | 짧은 선형복잡도·예측성 없음 |
| 대수적 (z3 SAT/다항식) | none | not-a-weakness | constrained R≈2·collision R=4 (직선차분보다 얕음) |
| 스펙-상수 구조 | none | not-a-weakness | 약점은 상수特異 아닌 아키텍처 generic |
| 비선형 불변/부분공간 | none | not-a-weakness | 저차 불변 0개(전수) |
| 자유(additive-exact) | structural-obs | not-a-weakness(primitive) | bit23 7차원 exact prob-1 (1라운드뿐) |

## State-space model 핵심 (직접 검증, `yttrium_ssm.py`)

라운드를 `x_{t+1} = A·x_t ⊕ B·F(C·x_t) ⊕ rc_t` 로 모델 — A = π∘σ(α^k)∘ROTR₉∘ROTL₈ (256×256 GF(2),
스펙상수로 정확 구성), C = 영합 reduction functional(32행), B = t-broadcast 상.

| # | 검증 | 결과 |
|---|------|------|
| [1] | backbone 정확성 | ROTR₉∘ROTL₈=ROTR₁ ✓, α-행렬==alpha()(2000) ✓, rank(A)=256 ✓, A^8 레인 block-diag ✓, A==(t=0 라운드)(500) ✓ |
| [2] | **관측성=도달성 포화** | obs rank [32,64,…,224,255,256], reach [32,…,254,256] → **R\*=9** (§10-D GF(2)-선형 R\*=9 재현, 제어이론 경로) |
| [4] | A 고유구조 | Fix(A)=ker(A−I) **dim 2**; ker((A−I)^p)=2,4,…,16,17,…,20 → λ=1 일반화고유공간 **24 (Jordan 16⊕8)** |
| [5] | **영구 불변 부재** | ker(C) 내 최대 A-불변부분공간 (=unobservable Q via O₉) **dim 0** → **영구 선형 distinguisher 없음** |
| [6] | **결정적 음성(귀속)** | null(O₈) δ(hw=138)가 kernel이나 **실라운드 차분==A·δ : 0/20000** → R\*=9 모드는 **mod-2³² carry로 소멸** = SSM 과대평가, **프리미티브 결함 아님** |
| [7] | exact prob-1 class | bit23 even-support(S-MSB carry-free): lanes{0,2} P(dS=0)=**1.0**, odd-support 0.0, bit22 0.499 → 7차원 exact prob-1 **이나 1라운드뿐**(R2서 F 완전활성, DP→generic floor) |

order(A) = 2⁴·3²·5·7·17·257 ≈ 2²⁴·⁴ (선형 cycle로 악용 불가). α primitive라 GF(2¹⁶) 등 부분체 불변 없음.

## 귀속 (정직, 엄수)

- **R\*=9 관측성 mode**: ②/④가 아니라 **carry-blind GF(2)-선형 과대평가**([6] 0/20000 실증) — 설계 의도대로
  carry/F가 막음. 프리미티브 결함으로 **오귀속 금지**.
- **bit23 7차원 prob-1**: ①프리미티브의 *구조적 성질*(exact prob-1)이나 **1라운드 한정·R2 사망** →
  weakness 아님(round-count floor R_b≈9 무위협).
- 나머지 전부 약점 아님. **하드웨어(④)·측정 아티팩트(③) 해당 없음.**

## 설계 영향: 0

어떤 변형(R_b=4 포함)의 라운드수도 위협받지 않음. SSM의 가치는 **새 attack이 아니라 구조적 엄밀화**:
§10-D의 "invariant subspace 0개"를 exact rank로 닫고(Q=0), 관측성=도달성 이중성·Jordan·order(A)·
exact prob-1 class를 신규 규명. all-8 σ가 A의 불변을 F-observable로 만드는 load-bearing임을 재확인.

## 한계 / 잔여 (모두 음성 예상)

- carry-gap 형식화(C를 carry-augmented로 lift), bit23 class·Jordan 고유공간 seed full-width Walsh/DP(GPU),
  small-field 전수(order·carry 소멸 추세), Gröbner 대규모 — 전부 기존 음성의 규모확장 sanity(결론 불변).
- 절대 trail 경계 미확립(R5). 극단 stress·하드웨어는 범위 외.

## 재현
```bash
cd milp
python3 yttrium_ssm.py --real 20000   # 통합 SSM 검증([1]~[7])
python3 yttrium_ssm.py --order        # order(A) factor-test
# 보조: ssm_analysis.py, ssm_backbone.py, ssm_unobservable.py, zerosum_kernel.py 등
```
