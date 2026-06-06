#import "template.typ": *

#show: spec.with(
  title: [YSC5 사양서],
  subtitle: [σ-Generalized Lai-Massey 순열 위의 Farfalle PRF 구조],
  authors: ("NEWSNIPER", "(cryptanalysis 결과 기반)"),
  version: "v0.1 (draft)",
  date: datetime(year: 2026, month: 6, day: 6),
)

= 개요

YSC5는 *YSC4의 σ-Generalized Lai-Massey 순열*과 *Bertoni–Daemen 방식의 Farfalle 구조*를
결합한 #emph[FHE 친화 PRF/Stream/AEAD 통합 스위트] 다.

#table(
  columns: (auto, 1fr),
  [*전제 라이브러리*], [`ysc4` (= σ-GLM 순열 `YSC4-p` + GF($2^64$) α-곱)],
  [*전제 검증*], [Isabelle/HOL `YSC_Probe` session (Q1·Q2의 기계 검증)],
  [*전제 메타*], [`farfalle-gen/META.md` (설계 공간 분해), `farfalle-gen/NOTE-…` (정합성 노트)],
  [*핵심 동기*], [
    YSC4가 *직렬* sponge이라면 YSC5는 *병렬* Farfalle. FHE 백엔드에서 블록간 batch 가능.
  ],
  [*변경 자유도*], [순열·α는 YSC4 그대로. 라운드 수·도메인 분리자만 신규 결정.],
)

#remark[
  본 사양서는 YSC4와의 *조합* 사양이지 신규 primitive 도입이 *아님*.
  순열 `YSC4-p`, GF($2^64$) α-곱, σ-orthomorphism의 모든 산술은 `ysc4` 크레이트와 동일.
]

= 설계 목표

본 사양은 다음 다섯 요건을 *동시에* 만족하도록 설계됨.

+ *FHE 친화*. AND 게이트, XOR, 상수 회전·이동만 사용. 모듈러 덧셈 없음. blocks 간 *완전 병렬*.
+ *S-box 미사용*. 테이블 룩업 없음 → cache-timing/branch-prediction 부채널 면역.
+ *Sponge 대비 우위*. 압축·확장 *모두* 병렬. incremental update 자명.
+ *YSC4와 산술 통합*. α-곱·순열·zeroize 정책 모두 동일. 구현 단일화.
+ *no_std 기본, musl 타깃*. YSC3/YSC4와 동일한 운영 약속.

= 표기

#table(
  columns: (auto, 1fr),
  [기호], [의미],
  [$b$], [상태 비트 폭 = $1024$],
  [$N$], [$2^64 - 1 = 18,446,744,073,709,551,615$. GF$(2^64)^*$의 차수.],
  [$α$], [GF$(2^64)$의 단위원 $x mod p(x)$, $p(x) = x^64 + x^4 + x^3 + x + 1$.],
  [$α #h(2pt) dot.c y$], [GF$(2^64)$에서의 곱. $α-$곱.],
  [$"YSC4-p"_r$], [$r$ 라운드의 YSC4-p 순열. (`ysc4::permutation::permute`)],
  [$"roll"$], [마스크 갱신 함수. 워드별 α-곱.],
  [$K, "Nc", "Ad", "Pt"$], [키 / 논스 / 부가데이터 / 평문.],
  [$plus.o$], [비트별 XOR (= GF($2$) 덧셈).],
)

= 매개변수 집합

YSC5는 두 매개변수 집합을 정의한다.

#table(
  columns: (auto, auto, auto),
  [매개변수], [*YSC5-128*], [*YSC5-256*],
  [키 크기], [256 비트], [512 비트],
  [Nonce 크기], [192 비트], [192 비트],
  [태그 크기 (AEAD)], [128 비트], [256 비트],
  [상태 비트 폭 $b$], [1024], [1024],
  [Rate (출력) per call], [512 비트 (8 워드)], [256 비트 (4 워드)],
  [Capacity], [512 비트], [768 비트],
  [라운드 수 $R_b$ (압축)], [12], [16],
  [라운드 수 $R_c$ (키 확장)], [24], [32],
  [라운드 수 $R_d$ (전이)], [ 8], [12],
  [라운드 수 $R_e$ (확장)], [12], [16],
)

#remark[
  *4종 라운드 수가 모두 다른 이유*는 Kravatte (Farfalle 인스턴스)의 표준 권고를 차용 —
  핵심 압축·확장은 충분한 라운드, 키 확장은 더 길게, 전이는 짧게.
  같은 *순열*을 라운드 수 매개변수만 달리하여 4개 역할에 재사용한다.
]

= 빌딩 블록

== YSC4-p 순열

상세는 `ysc4/SPEC.md`. 본 사양에서는 *블랙박스*로 인용.

#definition[YSC4-p][
  $"YSC4-p"_r : \{0,1\}^1024 -> \{0,1\}^1024$ 는 다음 단계의 합성으로 $r$ 라운드 반복:
  + 라운드 상수 주입 ($"RC"[r mod 16]$).
  + 16-branch Lai-Massey reduce-broadcast ($T = F(plus.o.big_i s_i)$, $s_i := s_i plus.o T$).
  + σ-층 (branches $\{0,4,8,12\}$에 $α^1, α^3, α^5, α^7$ 적용).
  + 워드 순열 $P[i] = (5i + 7) mod 16$.

  $F(s) := s plus.o (s lt.tri.eq 13 and s lt.tri.eq 37) plus.o (s lt.tri.eq 5 and s lt.tri.eq 23)$ — *비전단 보장은 구조적*.
]

== α-곱 (orthomorphism / roll primitive)

#definition[α-곱][
  GF$(2^64)$ = GF$(2)[x]\/p(x)$, $p(x) = x^64 + x^4 + x^3 + x + 1$. $α = x mod p$.
  $α dot.c y := $ GF$(2^64)$에서 $y$를 $α$만큼 곱한 결과. 명시적으로:
  $ α dot.c y = (y << 1) plus.o ((-(y >> 63)) and "0x1B") $
  단, $- (y >> 63)$ 은 $y$의 최상위 비트가 1이면 $2^64 - 1$ (= 전체 1), 0이면 $0$.
]

#verified[
  $α$는 GF$(2^64)^*$의 *primitive element*, 즉 곱셈 차수 $N = 2^64 - 1$. \
  (Isabelle/HOL `Q1_primitive_certificate` — `isabelle-verify/Q1_Primitivity.thy`.)
  이로부터 두 따름정리가 자동:
  + $α$, $α + 1$ 모두 GF$(2^64)^*$의 단위원 → α-곱은 *Vaudenay orthomorphism* 조건 만족.
  + $α^k$의 차수 $= N \/ gcd(k, N) > 2^60$ for $k in \{1, …, 16\}$ (`Q2_all_orders_practical`).
]

== 마스크 roll 함수 γ

#definition[γ][
  마스크 상태 $k = (k_0, k_1, …, k_15)$, $k_i in$ GF$(2^64)$. roll 함수:
  $ γ(k_0, k_1, …, k_15) := (α^1 dot.c k_0, α^2 dot.c k_1, …, α^16 dot.c k_15). $
  즉 *워드별 distinct α-거듭제곱*에 의한 동시 multiplication.
]

#remark[
  본 정의는 YSC4의 σ-층 (4개 워드만 처리)을 *16개 워드 전체*로 확장한 형태.
  Q2에 의해 모든 $α^(i+1)$은 차수 $> 2^60$, 따라서 cycle 측면에서 collision-free.
]

= Farfalle 골격

YSC5는 Bertoni–Daemen Farfalle 구조의 표준 인스턴스다 (참고문헌 참조).

== 입력 모델

함수 $"YSC5-PRF" : K times M -> {0,1}^*$ 가 기본 모델.
실제 사용은 다음의 4-튜플 입력을 1-차원으로 인코딩:
$ "input" = (K, "Nc", "Ad", "Pt") $
도메인 분리자 (§ @sec-domain)는 각 채널의 경계에 위치.

== 초기 키 확장 ($p_c$)

#algo[KeySetup][
  ```
  function KeySetup(K):
      state ← LoadKeyToCapacity(K)
      state ← state ⊕ DomainSeparator(STREAM, |K|)
      state ← YSC4-p(state, R_c)
      return  state    // 마스크 시드
  ```
]
- `LoadKeyToCapacity`는 YSC4/sponge 적재와 동일: 키를 capacity 워드에 LE 배치.
- `DomainSeparator(STREAM, |K|)`는 capacity의 마지막 워드에 도메인 라벨 + 키 길이 비트를 XOR.

== 압축 단계 ($p_b$ × roll)

입력 메시지를 rate 크기로 청크화 ($M_0 ∥ M_1 ∥ … ∥ M_(n-1)$). 각 블록을 *병렬*로 처리한 후 XOR-누적:

#algo[Compress][
  ```
  function Compress(k, M_0..M_{n-1}):
      Y ← 0
      for i = 0, 1, …, n-1 do in parallel:
          mask_i ← γ^i(k)
          Y ← Y  ⊕  YSC4-p(M_i ⊕ mask_i, R_b)
      return Y
  ```
]

- `γ^i(k)` 는 roll을 $i$회 적용한 마스크 (§ @sec-mask).
- `YSC4-p(·, R_b)` 호출은 $i$ 별로 *완전 독립*. FHE batch / SIMD 자명.
- 최종 누적 $Y$는 입력의 collision-free PRF-거리에 의한 함수.

== 전이 단계 ($p_d$)

#algo[Transition][
  ```
  function Transition(Y, k):
      Y' ← YSC4-p(Y, R_d)
      Y' ← Y' ⊕ γ^n(k)            // 압축 끝-마스크
      Y' ← Y' ⊕ DomainSeparator(EXPAND)
      return Y'
  ```
]

- $R_d$ 는 가장 작은 라운드 수 (8 또는 12).
- 끝-마스크 $γ^n(k)$ 는 압축 시 사용된 마지막 마스크 직후로 cycle 연속성 유지.

== 확장 단계 ($p_e$ × roll)

원하는 출력 길이만큼 키스트림을 *병렬* 생성:

#algo[Expand][
  ```
  function Expand(Y', j):
      mask_j ← γ^j(Y')
      Z_j    ← YSC4-p(mask_j, R_e)
      return Z_j[0..rate_bytes]    // rate 만큼만 출력
  ```
]

- $j = 0, 1, 2, …$ 각각이 독립. 임의 길이의 키스트림.
- 출력은 `YSC4-p` 결과의 *rate*만 — capacity는 영원히 비밀 (Sponge-식 비밀 유지).

== 종합: YSC5 함수

#algo[YSC5-PRF][
  ```
  function YSC5_PRF(K, M, ℓ):           // ℓ-비트 출력
      k  ← KeySetup(K)
      Y  ← Compress(k, Split(M, rate))
      Y' ← Transition(Y, k)
      // ℓ/rate 개의 출력 블록을 병렬 생성
      out ← []
      for j = 0, 1, …, ⌈ℓ/rate⌉ - 1 do in parallel:
          out.append(Expand(Y', j))
      return Truncate(out, ℓ)
  ```
]

= 모드

== Stream Cipher

$"YSC5-Stream"(K, "Nc", "Pt") = "Pt" plus.o "YSC5-PRF"(K, "Nc" ∥ "DOMAIN-STM", |"Pt"|)$.

- Nonce를 입력에 포함하고 도메인 분리자로 다른 모드와 격리.
- 임의 길이 평문에 대해 keystream 절단 사용.

== AEAD

#algo[YSC5-AEAD-Encrypt][
  ```
  function AEAD_Encrypt(K, Nc, Ad, Pt):
      k_main ← KeySetup(K)
      Y      ← Compress(k_main, Nc ∥ Ad ∥ DOMAIN-AD-CT-SEP ∥ Pt)
      Y'     ← Transition(Y, k_main)
      Ct     ← Pt ⊕ Expand_blocks(Y', |Pt|, DOMAIN-CT)
      tag    ← Expand_blocks(Y' ⊕ DOMAIN-TAG, tag_size, DOMAIN-TAG-EXP)
      return (Ct, tag)
  ```
]

- Compression 단계에 $"Ad" ∥ … ∥ "Pt"$ 모두 들어감 → 평문이 인증에 포함.
- Tag는 별도 도메인의 expand.
- 복호화: 동일하게 $Y, Y'$ 계산 → tag 일치 검증 → 일치 시 $"Pt" = "Ct" plus.o "ks"$.

== Hash / XOF

키 없는 모드:
$ "YSC5-XOF"(M, ℓ) := "YSC5-PRF"(0^256, M ∥ "DOMAIN-XOF", ℓ). $

== MAC

$ "YSC5-MAC"(K, M) := "YSC5-PRF"(K, M ∥ "DOMAIN-MAC", "tag-size"). $

= 도메인 분리 <sec-domain>

도메인 분리자는 8-byte ASCII 문자열을 LE u64로 인코딩:

#table(
  columns: (auto, auto, auto),
  [도메인], [ASCII], [u64],
  [STREAM], [`YSC5-STM`], [`0x4D54532D35435359`],
  [AEAD], [`YSC5-AEA`], [`0x4145412D35435359`],
  [AEAD-AD], [`YSC5-AD\0`], [`0x00444141352D5359`],
  [AEAD-CT], [`YSC5-CT\0`], [`0x00544352352D5359`],
  [AEAD-TAG], [`YSC5-TAG`], [`0x4741542D35435359`],
  [XOF], [`YSC5-XOF`], [`0x464F582D35435359`],
  [MAC], [`YSC5-MAC`], [`0x43414D2D35435359`],
  [EXPAND], [`YSC5-EXP`], [`0x5058452D35435359`],
)

도메인 분리자는 매개변수 집합(`128`/`256`)도 함께 인코딩:
$ "domainWord" = "DOMAIN" plus.o ("KeyBits" lt.tri.eq 0) plus.o ("NonceBits" lt.tri.eq 32). $

= 마스크 derivation <sec-mask>

압축의 $i$번째 마스크와 확장의 $j$번째 마스크 모두 동일한 $γ$로 정의:

$ "mask"_i = γ^i (k), quad γ((k_0, …, k_15)) = (α dot.c k_0, α^2 dot.c k_1, …, α^16 dot.c k_15). $

#verified[
  *마스크의 cycle 길이*는 `Q2_all_orders_practical`에 의해 $> 2^60$. 어떤 실용적
  사용 시나리오에서도 collision-free.
]

= FHE 비용 분석

== 단위 비용

#table(
  columns: (auto, auto, auto, auto),
  [블록], [블록당 AND], [블록당 깊이], [비고],
  [YSC4-p, $R_b = 12$], [1,536], [12], [F의 AND 128 × 12 라운드],
  [YSC4-p, $R_b = 16$], [2,048], [16], [],
  [γ (16개 워드 α-곱)], [≈ 0], [0], [plaintext-mult (FHE 무비용)],
  [기타 (XOR, broadcast)], [0], [0], [선형],
)

== 메시지·키스트림 단위

#table(
  columns: (auto, auto, auto, auto),
  [모드], [N블록 메시지 비용], [N블록 wall-clock], [병렬도],
  [YSC4-Stream (sponge)], [$N$ × 1,536 AND, 직렬], [$N$ × 12 depth], [1],
  [*YSC5-Stream (Farfalle)*], [$N$ × 1,536 AND, *batch*], [$≤$ 12 depth (배치)], [$N$],
)

→ 같은 *연산량*이지만 YSC5는 *latency/병렬도*에서 $N$배 우위.

== YSC3 vs YSC4 vs YSC5 (128-비트 변종)

#table(
  columns: (auto, auto, auto, auto),
  [지표], [YSC3 (GFN)], [YSC4 (σ-GLM)], [*YSC5 (Farfalle)*],
  [순열당 AND], [12,288], [2,048], [2,048 (= YSC4-p × $R_b$)],
  [순열당 깊이], [48], [16], [16],
  [N블록 N번 호출 시 depth], [$48 N$], [$16 N$], [*16* (병렬)],
  [Random access (seek)], [O], [O], [O],
  [Incremental update (append)], [△ (재시작)], [△], [*O* (자명)],
  [수학적 단일성], [], [], [α-곱 = σ = γ (단일 primitive)],
)

= 보안 논의

본 사양은 *형식 증명*을 제공하지 않고 *기존 결과의 인용*과 *몇 가지 새 가정의 명시*로 보안 주장:

#table(
  columns: (auto, 1fr),
  [PRF distinguishability], [Bertoni et al. 2017의 Farfalle PRF 환원에 의거. 가정: $p_b, p_c, p_d, p_e$가 *random permutation*.],
  [순열의 PRP 근사], [YSC4-p가 $R$ 라운드에서 PRP-indistinguishable이라는 가정. YSC4 SPEC §2 참조.],
  [Mask collision-free], [Isabelle/HOL `Q2_all_orders_practical`로 형식 보증.],
  [Key recovery 저항], [Capacity 512비트 (128) 또는 768비트 (256) 비밀 유지 → 키 복구 비용 ≥ $2^"capacity"/2$.],
  [Multi-key 보안], [Mennink-style 분석 필요. *미해결*.],
  [Differential / Linear], [MILP 트레일 경계 — *미해결*, $R_b$ 값 결정의 근거가 됨.],
)

= 형식 검증 인용

본 사양이 의존하는 *기계 검증된* 사실 (Isabelle/HOL 2025-2, `YSC_Probe` session):

#table(
  columns: (auto, 1fr),
  [정리], [내용],
  [`Q1_primitive_certificate`], [α는 GF$(2^64)^*$의 primitive element (ord = $2^64 - 1$)],
  [`N_factorization`], [$2^64 - 1 = 3 dot.c 5 dot.c 17 dot.c 257 dot.c 641 dot.c 65537 dot.c 6700417$],
  [`Q2_gcd_table`], [$k in \{1, …, 16\}$에 대한 $gcd(k, 2^64 - 1)$ 정확값],
  [`Q2_all_orders_practical`], [$forall k in \{1, …, 16\}, "ord"(α^k) > 2^60$],
)

상세 로그: `isabelle-verify/LOG.md`.

= 비교 — 사양 단위 (1 페이지 요약) <sec-summary>

#table(
  columns: (auto, auto, auto, auto, auto),
  [], [YSC2 (v1)], [YSC3], [YSC4], [*YSC5*],
  [상태 비트], [1024], [1024], [1024], [1024],
  [순열 구조], [Lai-Massey-유사], [Type-3 GFN (NORX)], [σ-GLM], [(= YSC4)],
  [모드 구조], [순수 keystream], [Sponge], [Sponge], [*Farfalle*],
  [비선형 게이트/라운드], [AND 1024], [AND 1024], [AND 128], [AND 128],
  [블록 간 병렬성], [순차], [순차], [순차], [*완전 병렬*],
  [보안 결함], [V1 ~ V10], [없음 (형식 가정)], [없음], [없음 (형식 가정)],
  [FHE 친화도], [낮음], [중간], [높음], [*최고* (병렬성 포함)],
)

= 미해결 사항

+ *MILP 차분/선형 트레일 경계*. $R_b = 12$, $R_e = 12$ 적절성 정량 평가.
+ *Multi-key indistinguishability*. CryptHOL 또는 별도 손증명.
+ *FHE 백엔드 구체 측정*. BFV/TFHE 인스턴스에서 plaintext-mult 비용 검증.
+ *roll cycle 충분성의 형식 증명*. Q2는 단일 워드 차수만 검증; 16개 차원 결합의 LCM 경계는 informal.
+ *AEAD nonce 분할*. nonce의 어느 부분을 압축에, 어느 부분을 확장에 둘지의 trade-off.
+ *참조 구현*. `ysc4` 크레이트와 동일 패턴으로 `ysc5` 크레이트 작성 (no_std/musl, zeroize).

= 변경 이력

#table(
  columns: (auto, auto, 1fr),
  [버전], [날짜], [요약],
  [v0.1-draft], [2026-06-06], [최초 사양화. Farfalle generalization meta-task (META.md)와 Q1·Q2 형식 검증 (Isabelle/HOL)을 토대로 한 초안.],
)

#pagebreak()

= 참고 문헌 <sec-refs>

본 사양이 인용한 문헌·문서:

- *Bertoni, Daemen, Hoffert, Peeters, Van Assche, Van Keer.* Farfalle: parallel permutation-based cryptography. ToSC 2017. 
- *Vaudenay.* On the Lai-Massey scheme. ASIACRYPT 1999.
- *Aumasson, Jovanovic, Neves.* NORX. CAESAR submission. (Quasi-addition H-function 출처.)
- *Bernstein.* ChaCha (column/diagonal round 패턴 출처).

본 저장소 내 문서:

- `farfalle-gen/META.md` — Farfalle 일반화 meta-task.
- `farfalle-gen/NOTE-orthomorphism-roll-coincidence.md` — YSC4↔Farfalle 정합성 노트.
- `ysc4/SPEC.md` — YSC4 사양서. 
- `isabelle-verify/LOG.md` — Q1·Q2 형식 검증 빌드 로그.
- `REPORT.md` — YSC2 v1.0의 cryptanalysis 보고서 (V1~V10 도출의 원천).
