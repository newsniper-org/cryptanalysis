#import "template.typ": *

#show: spec.with(
  title: [YSC3 사양서],
  subtitle: [ChaCha/NORX 기반 generalized Feistel network sponge],
  authors: ("NEWSNIPER",),
  version: "v0.1",
  date: datetime(year: 2026, month: 6, day: 6),
)

= 개요

YSC3는 *NORX 스타일 H 함수*와 *ChaCha 스타일 column/diagonal 더블 라운드*를 결합한
*16-워드 generalized Feistel network (GFN)*를 핵심 순열로 사용하는 sponge-mode 스트림/AEAD/XOF 스위트.

#table(
  columns: (auto, 1fr),
  [*상태*], [1024 비트 = 16 × `u64`],
  [*순열 구조*], [NORX H + ChaCha column/diagonal QR],
  [*모드*], [Sponge (절반 rate / 절반 capacity)],
  [*기본 매개변수*], [YSC3-128 (256-비트 키, R=12), YSC3-256 (512-비트 키, R=16)],
  [*FHE 비용*], [블록당 12,288 AND (R=12)],
  [*상태 zeroize*], [모든 비밀 상태에 `ZeroizeOnDrop`],
)

#remark[
  본 사양은 v0.1. 정식 표준이 아니며, MILP 분석·외부 검토 후 갱신될 예정.
  자세한 알고리즘 텍스트는 `ysc3/SPEC.md` (Markdown) 참조.
]

= 설계 목표

+ *FHE 친화* — AND, XOR, 상수 회전·이동만 사용 (모듈러 덧셈 없음)
+ *S-box 미사용* — 테이블 룩업 없음 → cache-timing 면역
+ *no_std 기본, musl 타깃* — 임베디드·정적 빌드 지원

= 빌딩 블록

== H 함수 (NORX quasi-addition)

$ H(x, y) = x plus.o y plus.o ((x and y) lt.tri.eq 1). $

알고리즘 차수 2. 모듈러 덧셈의 1-비트 carry 근사.

== Quarter Round (NORX-style)

```
QR(a, b, c, d):
    a = H(a, b);   d = rot(d ⊕ a, R0)
    c = H(c, d);   b = rot(b ⊕ c, R1)
    a = H(a, b);   d = rot(d ⊕ a, R2)
    c = H(c, d);   b = rot(b ⊕ c, R3)
```

R0=8, R1=19, R2=40, R3=63 (NORX64).

== Permutation

```
permute(state, ROUNDS):
    for r in 0..ROUNDS:
        ι: round constant 주입
        if r is even: column round (4×QR)
        else: diagonal round (4×QR)
```

= 매개변수

#table(
  columns: (auto, auto, auto),
  [매개변수], [*YSC3-128*], [*YSC3-256*],
  [키 크기], [256 비트], [512 비트],
  [Nonce 크기], [192 비트], [192 비트],
  [Rate], [512 비트 (8 워드)], [256 비트 (4 워드)],
  [Capacity], [512 비트], [768 비트],
  [라운드 (init/block)], [24 / 12], [32 / 16],
)

= 모드

- *Stream cipher*: sponge-CTR, 카운터는 capacity 워드에 주입.
- *AEAD*: duplex sponge, 각 단계 도메인 분리자.
- *XOF*: 키 없는 sponge.
- *MAC*: 키-prefix sponge.

= 보안 인용

- META.md §1 ChaCha/NORX 패밀리의 광범위한 외부 분석.
- avalanche 측정: 12라운드 후 1비트 → 499/1024 (random PRF에 근사).
- affinity 위반: 487/1024 (linear 분리됨).
- bench/compare: 576 MB/s (musl release, 단일 thread).

= 변경 이력

- v0.1 (2026-06-06): 최초 사양화. YSC2 v1.0 cryptanalysis 결과를 반영한 재설계.

= 참고

자세한 사양·논의는 `ysc3/SPEC.md` 참조. 본 Typst는 *요약본*.
