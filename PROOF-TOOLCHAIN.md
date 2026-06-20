# 증명 툴체인 검토 — EasyCrypt vs Isabelle/HOL+CryptHOL

> **질문**: 형식검증 workflow에 EasyCrypt를 Isabelle/HOL+CryptHOL과 *함께* 도입할까?
> (R1=PRF/deck 보안 환원, R3=constant-time 대상)
>
> **결론**: **이번 라운드는 도입하지 않는다.**
> R1 = **Isabelle/HOL + CryptHOL**, R3 = **Rust dudect + 정적 CT 감사**.
> EasyCrypt는 *보류(defer)* 하고, 아래 "재평가 조건"을 만족할 때만 재검토.
>
> (4-렌즈 워크플로 검토: 증명 ergonomics / R3-CT / 툴체인 비용 / 건전성·TCB —
>  네 렌즈 모두 동일 결론. 결정 근거는 환경 실측에 기반.)

## 1. 환경 실측 (결정적)

| 도구 | 상태 | 함의 |
|------|------|------|
| Isabelle2025-2 + AFP (`/home/ybi/afp`) | ✅ 즉시 사용 | T1 산출물·CryptHOL 동일 prover |
| CryptHOL (AFP `Game_Based_Crypto`) | ✅ 세션 인식 | R1 building block 다수 *기성품* |
| EasyCrypt | ✗ 미설치 (AUR 설치 중) | 이번 세션 불가 |
| alt-ergo (EasyCrypt 핵심 SMT) | ✗ 부재 | EasyCrypt 설치돼도 즉시 가용 아님 |
| jasminc | ✗ 부재 | EasyCrypt-Jasmin CT 파이프라인 불가 |
| valgrind / ctgrind | ✗ 부재 | R3는 dudect(통계) 경로 |
| z3, cvc5 | ✅ | (R2 bit-level 등 보조) |

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

## 4. EasyCrypt 보류 — 재평가 조건

다음 중 하나가 생기면 EasyCrypt를 재검토:
1. 외부 감사자가 R1에 **prover 다양성**(독립 TCB)을 요구.
2. **구현 레벨(source→binary) CT**가 hard requirement가 됨 → 이때 Jasmin 재작성 +
   EasyCrypt로 R1·R3를 *함께* 묶는 게 합리적.
3. sponge/indifferentiability/Farfalle의 **성숙한 EC 기성 라이브러리**가 필요한
   별도 의무 발생.

## 5. 분업 요약

| 의무 | 도구 | 산출물 |
|------|------|--------|
| T1 대수 정확성 | Isabelle/HOL | (완료) Q1/Q2/Y1~Y4 |
| **R1** PRF/deck 환원 | **Isabelle/HOL + CryptHOL** | Y5 채워넣기 (AFP 정리 인스턴스화) |
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
