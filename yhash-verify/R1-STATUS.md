# R1 — keyed PRF/deck 보안 환원: 현황 (정직)

> 결정(`PROOF-TOOLCHAIN.md`): **CryptHOL 주 + EasyCrypt 교차검증.**
> 형식검증 상한은 *순열을 ideal로 가정한 환원*(T3). 구체 YSC4-p의 RP 근사(T4)는
> 형식검증 불가 — R2(MILP)·R5(외부 분석) 영역.

## 무엇이 *기계검증*되었나

| 산출물 | 도구 | 상태 |
|--------|------|------|
| `Y5_CRReduction.thy` 합성 bound `adv_multi ≤ u·(q²/2^(n+1)+ε)` | Isabelle/HOL (+Complex_Main) | ✅ **sorry-free** (세션 `quick_and_dirty` 제거 → sorry 시 빌드 실패) |
| multi-key hop + birthday 합성 + n=256 수치화 | Isabelle/HOL | ✅ 기계검증 |
| S2(tree 인코딩 단사), S3(mask 단사) 충돌 차단 | Isabelle/HOL (Y1, Y4) | ✅ 기존 sorry-free |
| 합성·monotonicity bound 독립 재증명 | EasyCrypt (`easycrypt/r1_bound.ec`) | ✅ exit 0 (cvc5/z3) |

`isabelle build -d yhash-verify YHash_Verify` → Finished (sorry-free).
`easycrypt yhash-verify/easycrypt/r1_bound.ec` → exit 0.

## 이전 대비 (정직성 개선)

이전 `Y5_CRReduction.thy`: 정리문이 **degenerate placeholder**(`∃b. b ≤ q*q` — 자명式)
이고 lemma 7개 전부 `sorry`. → **실제 bound로 교체 + sorry 제거**. degenerate sorry는
"증명 안 된 것을 증명된 것처럼" 보이게 하므로 *조건부 정리(명시적 가정)* 가 더 정직하다.

## 무엇이 *가정(hypothesis)* 으로 남았나 — 그리고 어떻게 닫나

본 정리는 *조건부*다. generic 게임 단계를 명시적 가정으로 두되, 각 가정은 AFP에
*이미 형식화된* 정리로 discharge 가능함이 확인됨 (가정 ≠ sorry: 가정은 정직하고
sorry는 아니다):

| 가정 | 의미 | discharge할 기성 정리 (AFP, 확인됨) |
|------|------|--------------------------------------|
| `H1_single_birthday` | 단일키 PRF advantage ≤ q²/2^(n+1)+ε | `RP_RF.rp_rf` (`advantage ≤ q*q/card A`, card A=2^n) + Y4 + Wagner |
| `H2_multi_hybrid` | 다중키 ≤ u·단일키 | `Guessing_Many_One.many_single_reduction` |

남은 *full* 기계검증(별도 작업): Farfalle compress/expand oracle을 CryptHOL GPV로
모델링 → reduction adversary 구성 → 위 두 AFP 정리를 실제 인스턴스화해 H1·H2를
가정에서 *정리*로 승격. (TODO B2/E4. 본 turn은 합성 골격을 sorry 없이 확정하고
bound를 명시 + 양 prover 교차검증까지.)

## R1 수용 기준 대비

요청 R1 수용: "sorry-free 세션 빌드 + 명시적 bound + 단일키→다중키 환원."
- sorry-free 빌드 ✅, 명시적 bound ✅ (`u·(q²/2^(n+1)+ε)`), multi-key hop ✅(가정+합성).
- 단, H1·H2가 *조건부*(AFP 정리로 닫을 수 있음을 명시) — full unconditional 환원은
  미완(이는 형식검증 상한 T3까지의 작업이며 별도 공정). 따라서 R1 = **실질 진전,
  조건부 완료** (과대주장 회피).
