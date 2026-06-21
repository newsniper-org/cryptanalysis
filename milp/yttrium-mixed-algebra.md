# yttrium 혼합대수 정밀 암호분석 (§10-D)

> 비-직선-차분 공격류가 라운드수 근거(직선차분 best-DP, R_b≈9 for 2⁻⁶⁴)를 **위협하는가**.
> 워크플로(5 공격류 병렬 분석) + 오케스트레이터 직접 검증. **결론: 어느 류도 직선차분보다
> 깊지 않음 → 라운드수 상향 0.** 단 **all-8 σ + 비반복 RC가 load-bearing**.
>
> 정직: adversarial **refute 단계는 미완**(diff-linear 분석 에이전트 지연 → 워크플로 중단). 결론은
> *분석 단계의 직접 측정* + *오케스트레이터 재현(RX·boomerang·diff-linear 3/5)* 에 근거하며,
> 전용 distinguisher 확장 탐색은 잔여(절대 경계 미확립 caveat과 동일 선상).

## 혼합대수
한 라운드에 (i) Z/2³² 가산 ⊞ (broadcast + 영합 2의보수), (ii) GF(2³²) 곱 α^k (σ), (iii) GF(2)
(F·회전)이 얽힘. 단일대수보다 분석 난해. 라운드 = SPEC §6.

## 공격류별 결과 (vs 직선차분: R3 floor, slope +7.7)

| 공격류 | vs 직선차분 | 최심 도달 | 측정 | 검증 |
|------|------|------|------|------|
| **RX (rotational-XOR)** | 얕음·안전 | **R0~R1** | all-8 σ: R1..6 rot-prob=0 (≤2⁻²⁹·⁹). empty-σ는 R1=2⁻⁶·¹·slope+? 깊이 생존 | 오케스트레이터 직접 ✓ |
| **boomerang (BCT)** | 얕음·안전 | R1(prob-1 outlier), R2=2⁻¹⁰·⁹ | 가산 BCT prob-1 폭증(자유 switch)·but σ⁻¹(MSB) 高HW 차단; 중간층 R2=2⁻¹⁰·⁸⁷ | 오케스트레이터 직접 ✓ |
| **differential-linear** | 얕음·안전 | R1(outlier), R2=2⁻⁵·⁶⁴ | C_DL R1=2⁻⁰, R2=2⁻⁵·⁶⁴ (slope +5.6) | 오케스트레이터 직접 ✓ |
| **linear hull** | **동급(deeper 아님)** | R≈8~10 (corr²≤2⁻⁶⁴) | σ=α^k는 GF(2)-선형 → hull 다중도 0(마스크만 재배치); ⊞만 hull원; toy hull-gain 폭증은 <10bit 포화 인공물(32bit 전이 안 됨) | 워크플로 측정 (외삽) |
| **혼합불변/slide/structural** | 얕음·안전 | R0~R1 | 불변부분공간·비선형2차불변·회전고정점 R1 전 0개; slide는 비반복 RC가 차단(SHA256_K[r] distinct 확인, 구 주기-8 RC는 slide 취약) | 워크플로 측정 |

### 메커니즘 요지
- **RX 죽음**: α^k(GF곱)가 회전 비보존 — commute-prob k=1:2⁻², k=17:2⁻¹⁷; all-8이 8레인 동시에 회전정렬 파괴 → 결합 ≪2⁻³⁰. α^k는 GF-선형이라 XOR-δ 보정 불가.
- **boomerang 죽음**: 가산 BCT의 free switch(dx=MSB→256/256 prob-1)가 위협이나, σ⁻¹가 MSB를 高HW로 펼쳐 switch 정렬 파괴. R1 prob-1은 영합 同부호 MSB쌍(ΔS=0·F비활성) outlier로 직선차분이 이미 가진 것과 동일 — 추가 라운드 0~1.
- **hull 동급**: 결정적 — α^k가 선형이라 hull 다중도를 만들지 않음(carry-chain 마스크를 비트위치+레인(π) 양쪽으로 desync). 실폭 corr² 감쇠가 직선차분과 동급 R≈8~10.
- **structural/slide 죽음**: all-8 distinct-power α^k가 대각 정렬·불변부분공간 파괴; 비반복 RC가 slide 차단.

## 라운드 영향 = 0 (단 load-bearing 의존성)

직선차분이 라운드 하한을 지배(R_b≈9 for 2⁻⁶⁴). 어느 혼합대수 류도 이를 압박하지 않음 →
변형 (10,14,24)/(8,12,24)/(4,6,12)/(4,6,8) **모두 §10-D로 상향 불필요**. 단:

- **all-8 σ 필수**: 부분 σ는 boomerang free-switch·RX·structural을 부활(§4 best-DP·본 분석 ablation 일치).
- **비반복 RC 필수**: 주기-8 RC면 slide 취약 재현(r=r+8 일치). SHA256_K[r] (r<64 distinct) 강제.
- Amaryllis/σ 재설계 시 이 두 방어가 동반 재검증되어야 함(σ가 단일 killer).

## 한계 (정직)

1. **refute 미완**: 전용 adversarial distinguisher-확장 탐색은 워크플로 중단으로 미수행. 결론은
   측정(prob=0/floor)에 근거하나, RX/boomerang을 더 깊이 끌 정교한 구성의 부재를 *증명*하진 못함.
2. **hull·합성은 외삽**: linear-hull deep-round corr²≤2⁻⁶⁴(R≈8~10)는 floor 너머 외삽. toy hull-gain은
   포화 인공물 — 실폭 측정불가(=작음 추정).
3. **축소폭**: RX/boomerang/diff-linear 직접측정은 n=8/n=32 floor(2⁻¹⁶~2⁻³⁰). 깊은 라운드는 floor에 가림.
4. 미측정(잔여): rotational-XOR-차분 full 탐색, boomerang multi-round MITM, diff-linear hull 결합,
   division property/integral 정밀. → R5/전용 도구.

## 재현 (milp/, 직접 실행 가능; GPU 불요)

```bash
python3 adv_rx_yttrium.py        # RX R1..6 (all-8 σ = 0)
python3 boomerang_decisive.py    # boomerang R1 prob-1, R2=2^-10.9
python3 dl_confirm.py            # diff-linear C_DL R1=2^0, R2=2^-5.6
python3 yttrium_lm_hull.py       # linear hull (정확 상관행렬 거듭제곱)
```
