#import "template.typ": *

#show: spec.with(
  title: [YSC4 사양서],
  subtitle: [σ-Generalized Lai-Massey 기반 FHE 최적화 sponge],
  authors: ("NEWSNIPER",),
  version: "v0.1",
  date: datetime(year: 2026, month: 6, day: 6),
)

= 개요

YSC4는 *16-branch σ-Generalized Lai-Massey* 순열을 사용하는 sponge-mode 변종.
YSC3 대비 *FHE AND 카운트 1/6 절감*이 주된 동기.

#table(
  columns: (auto, 1fr),
  [*상태*], [1024 비트 = 16 × `u64`],
  [*순열 구조*], [16-branch Lai-Massey + σ-orthomorphism + π],
  [*모드*], [Sponge],
  [*기본 매개변수*], [YSC4-128 (R=16), YSC4-256 (R=20)],
  [*FHE 비용*], [블록당 2,048 AND (R=16)],
  [*형식 검증*], [α primitivity (Q1), 차수 분포 (Q2) Isabelle/HOL by eval],
)

#remark[
  자세한 알고리즘 텍스트는 `ysc4/SPEC.md` (Markdown) 참조.
  형식 검증 결과: `isabelle-verify/LOG.md`.
]

= 빌딩 블록

== α-곱 (GF($2^64$) orthomorphism)

```
α-mult(y) = (y << 1) ⊕ ((-(y >> 63)) AND 0x1B)
```

GF$(2)[x]\/(x^64 + x^4 + x^3 + x + 1)$ 위 곱셈. Q1로 α는 *primitive element* (ord = $2^64 - 1$).

== F 함수

$ F(s) = s plus.o (s lt.tri.eq 13 and s lt.tri.eq 37) plus.o (s lt.tri.eq 5 and s lt.tri.eq 23). $

알고리즘 차수 2. AND 게이트 128 (= 2 × 64).

== 라운드

```
1) ι: state[r mod 16] ⊕= RC[r mod 16]
2) T = F(⊕ᵢ state[i])            # F 호출 1회
3) for all i: state[i] ⊕= T       # broadcast
4) σ-층:  state[0] = α¹·state[0]
         state[4] = α³·state[4]
         state[8] = α⁵·state[8]
         state[12] = α⁷·state[12]
5) π: state[i] = state[P[i]]    where P[i] = (5i+7) mod 16
```

#verified[
  *순열 비전단성*은 σ-GLM의 *구조적 보장*. F가 affine이어도 (테스트 단계의 실수 시나리오)
  순열은 여전히 bijection — 단 *전체 affine으로 잘못 빠짐*. F의 비선형성은
  `Isabelle/Q3_RollMatrix.thy::Q3_roll_distinct_for_ones` 등으로 sanity check.
]

= 매개변수

#table(
  columns: (auto, auto, auto),
  [매개변수], [*YSC4-128*], [*YSC4-256*],
  [키 크기], [256 비트], [512 비트],
  [Nonce 크기], [192 비트], [192 비트],
  [Rate], [512 비트], [256 비트],
  [Capacity], [512 비트], [768 비트],
  [라운드 (init/block)], [32 / 16], [40 / 20],
)

= FHE 비용 비교 (vs YSC3)

#table(
  columns: (auto, auto, auto),
  [항목], [YSC3], [*YSC4*],
  [라운드당 AND], [1,024], [*128*],
  [라운드당 비선형 호출], [H × 16], [*F × 1*],
  [블록당 AND], [12,288], [*2,048*],
  [블록당 AND 깊이], [48], [*16*],
)

= 형식 검증 인용

| 정리 | 명제 | 위치 |
|------|------|------|
| `Q1_primitive_certificate` | α는 GF$(2^64)^*$의 primitive | `Q1_Primitivity.thy` |
| `Q2_all_orders_practical` | $forall k in {1..16}, "ord"(α^k) > 2^60$ | `Q2_Cycles.thy` |
| `Q3_roll_distinct_for_ones` | γ 1-단계 결과가 distinct | `Q3_RollMatrix.thy` |

자세한 빌드 결과: `isabelle-verify/LOG.md`.

= 변경 이력

- v0.1 (2026-06-06): σ-GLM 순열로 YSC3에서 FHE 비용 1/6 절감. Sponge 모드 유지.

= 참고

자세한 사양: `ysc4/SPEC.md`. 본 Typst는 *요약본*.
