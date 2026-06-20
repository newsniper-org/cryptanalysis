# 증명 툴체인 검토 — EasyCrypt vs Isabelle/HOL+CryptHOL

> **질문**: 형식검증 workflow에 EasyCrypt를 Isabelle/HOL+CryptHOL과 *함께* 도입할까?
> (R1=PRF/deck 보안 환원, R3=constant-time 대상)
>
> **결론 (확정)**: R1 = **CryptHOL 주(primary) + EasyCrypt 교차검증(cross-check)**,
> R3 = **Rust dudect + 정적 CT 감사**.
>
> 4-렌즈 워크플로 검토는 "R1=CryptHOL 단독, EC 보류"를 권고했고 그 *기술적* 근거
> (AFP에 building block 기성품 · T1과 단일 TCB · Y5 기존 skeleton)는 지금도 유효하다.
> 그러나 검토 후 **EasyCrypt가 설치·동작 확인**되었고(아래 §1), 사용자가 *prover
> 다양성*을 위해 EC 교차검증을 채택하기로 결정했다. 따라서 **주 증명은 CryptHOL**
> (T1 재사용·단일 세션)으로 하되, **핵심 advantage bound를 EC로 독립 재검증**한다.

## 1. 환경 실측 (결정적)

| 도구 | 상태 | 함의 |
|------|------|------|
| Isabelle2025-2 + AFP (`/home/ybi/afp`) | ✅ 즉시 사용 | T1 산출물·CryptHOL 동일 prover |
| CryptHOL (AFP `Game_Based_Crypto`) | ✅ 세션 인식 | R1 building block 다수 *기성품* |
| EasyCrypt | ✅ **설치·동작 확인** | `lemma … by smt()` 디스차지 성공 |
| why3 + cvc5/z3 (EC의 SMT 백엔드) | ✅ `why3 config detect` 등록 | EC가 cvc5@1.3.0·z3@4.16 사용 |
| alt-ergo (EC 선호 SMT) | ✗ 부재 | cvc5/z3로 대체 (Eprover는 불안정) |
| jasminc | ✗ 부재 | EasyCrypt-Jasmin CT 파이프라인 불가 → R3는 dudect |
| valgrind / ctgrind | ✗ 부재 | R3는 dudect(통계) 경로 |
| z3, cvc5 | ✅ | R2 bit-level SMT, EC 백엔드 |

## 2. R1 (PRF/deck 환원) → **CryptHOL**

결정타: **R1이 필요로 하는 정리가 AFP에 이미 형식화되어 존재**한다.

- `RP_RF.thy` — PRP→PRF switching: `advantage A ≤ q*q / card A`
  → multi-key bound의 생일 항 `q²/2^c` 직접 제공.
- `Guessing_Many_One.thy` `many_single_reduction` — `adv_multi ≤ adv_single · q`
  → single→multi-key hop(Mennink/key-isolation)의 정식 골격.
- `PRF_IND_CPA.thy` `prf_encrypt_advantage` — PRF 가정 하 reduction의 *완성된 사례*.
- `Pseudo_Random_{Function,Permutation}.thy` — 게임·advantage 정의 기성품.

추가 근거:
- **통합/단일 TCB**: T1(GF64·Q1·Q2·Y1~Y4)이 전부 Isabelle/HOL. CryptHOL은 *같은
  prover·같은 세션 그래프*라 T1 보조정리(Q2의 cycle ≥ 2⁶⁰ → mask collision-free,
  Y4 mask 단사, Y1 encode 단사)를 R1 환원의 가정으로 직접 inline 재사용. EasyCrypt를
  쓰면 이 결과들을 axiom으로 재기술해야 함 → **이중 TCB**로 보증 약화.
- **저자 의도와 직결**: `Y5_CRReduction.thy`와 `farfalle-gen/NOTE-multikey-security.md`가
  이미 `imports CryptHOL.CryptHOL` skeleton(sorry)으로 작성됨. CryptHOL 채택 = 기존
  골격 채워넣기로 통합비용 최소.

## 3. R3 (constant-time) → **Rust dudect + 정적 감사**

- EasyCrypt+Jasmin은 *Jasmin* 소스만 검증한다. 본 구현은 **Rust** → Jasmin으로
  전체 재작성해야 하고, 그러면 *출하되지 않는 코드*를 검증하게 됨(CT 정리가
  rustc 바이너리로 전이되지 않음). 부적합.
- 실측상 keyed 경로는 **설계상 이미 branchless·data-independent**:
  - `gf2_64::alpha`/`gf32::alpha`: `mask = 0.wrapping_sub(y>>(n-1))` 트릭 — 분기·테이블 없음.
  - `permutation`: `pi_layer`는 컴파일타임 상수 인덱스, σ/F/xor_reduce는 순수 산술·회전.
  - keyed init: 키를 *길이*(공개)에만 의존해 흡수, 비밀-종속 분기 없음.
- 따라서 R3은 *증명 문제가 아니라 측정·회귀 문제*: dudect(고정키 vs 랜덤키 Welch
  t-검정) + asm 육안검사(컴파일러가 branchless를 branchy로 낮추지 않는지) + lint.

## 4. EasyCrypt 채택 범위 (교차검증) + 향후 확장

이번 채택: **R1 핵심 advantage bound의 독립 재검증**(prover 다양성). 주 증명·T1
재사용·multi-key 합성은 CryptHOL. EC는 PRP→PRF switching / 생일 bound 등
*도구-독립적으로* 진술 가능한 핵심 부등식을 EC 자체 라이브러리로 다시 증명해,
한 prover의 형식화 오류가 결과를 좌우하지 않게 한다.

EC 범위를 더 넓힐 조건:
1. 외부 감사자가 R1 *전체*에 독립 TCB를 요구 → EC로 환원 전체 재형식화.
2. **구현 레벨(source→binary) CT**가 hard requirement → Jasmin 재작성 + EC로
   R1·R3를 함께 묶음 (현재 R3는 Rust라 부적합).
3. sponge/indifferentiability/Farfalle의 **성숙한 EC 기성 라이브러리** 필요.

## 5. 분업 요약

| 의무 | 도구 | 산출물 |
|------|------|--------|
| T1 대수 정확성 | Isabelle/HOL | (완료) Q1/Q2/Y1~Y4 |
| **R1** PRF/deck 환원 | **CryptHOL 주 + EasyCrypt 교차검증** | Y5 채워넣기(AFP 인스턴스화) + EC 핵심 bound 재검증 |
| **R2** bit-level 트레일 | z3/cvc5 (+glpsol) | SMT 차분 모델 |
| **R3** constant-time | **Rust dudect + 정적감사** | dudect 하니스 + CT 감사 + CI |
| T4 구체 순열 보안 | (형식검증 불가) | 공개 암호분석(R5) |

## 6. 필수 caveat (R1 결과와 함께 명시할 것)

- **R1은 ideal-permutation 가정(T3) 하의 조건부 결과**다. 구체 YSC4-p가 RP에
  가깝다는 것(T4)은 CryptHOL/EasyCrypt 어느 쪽도 증명 불가 — MILP/공개분석 영역.
- R1 형식화 전에 **R4 파라미터 동결**이 선행돼야 함(증명 모델 = 출하 코드 일치).
  → 본 저장소는 R4를 먼저 완료(`FROZEN-PARAMS.md`).
- dudect는 *통계적 미검출*이지 부재 증명이 아님. `target-cpu`/`opt-level`별 재실행,
  WASM 타깃 별도 측정(또는 CT 주장을 native로 한정) 필요.
