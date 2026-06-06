# Farfalle-tree — 설계 노트

> 단일 permutation(예: Keccak-p[1600] 또는 Xoodoo) 위에서, Farfalle의 병렬 XOR-accumulation
> 압축과 tree-positional 마스크 기반 Merkle 구조를 결합해 **verified streaming / inclusion
> proof를 지원하는 병렬 해시·deck function**을 만들기 위한 설계 노트.
>
> 핵심 통찰 한 줄: Farfalle 압축의 accumulator `⊕_j P(m_j ⊕ k_j)`는 XOR의 결합·교환법칙
> 덕분에 임의의 분할 지점에서 `Acc = Acc_left ⊕ Acc_right`로 쪼개진다. 이 분해 가능성이
> 트리 구조를 자연스럽게 수용하는 발판이며, 표준 Farfalle의 linear rolling mask를
> tree-positional mask로 교체하는 것만으로 활성화된다.

---

## "Farfalle-tree" 구성

기호: permutation `P`(폭 `b`, 예 `b = 1600`), 노드 digest / chaining value 크기 `n`(예 `768`),
`trunc_n`은 `n`비트 절단, `⊕`는 블록 XOR. 마스크는 공개 NUMS 상수(unkeyed) 또는 비밀 키
(keyed)에서 유도하되 **트리 위치를 인코딩**한다: `mask(path)`, `maskMid(level)`.

**① linear rolling mask → tree-positional mask**

표준 Farfalle는 `k_{i+1} = P(k_i)`로 마스크를 직렬 유도하여 위치를 인코딩하지 못한다. 이를

```
k(path) = P(IV ⊕ encode(path))
```

로 바꾼다. `encode`가 단사(injective)이면 모든 위치가 고유한 마스크를 가지므로 rolling이
주던 "위치 individuation"을 그대로 보존하고, 동시에 **모든 마스크를 병렬 선계산**할 수 있어
직렬 의존성이 사라진다.

**② 각 노드 = 독립 Farfalle 인스턴스**

- **Leaf 노드** (위치 `pos`, 블록 `x_0..x_{t-1}`, `t ≤ T_max`):
  - `Acc = ⊕_{j} P(x_j ⊕ mask(pos, j))`        ← 블록 단위 병렬 누산
  - `leafDigest = trunc_n( P(Acc ⊕ maskMid(LEAF, pos)) )`
- **Internal 노드** (level `l`, 위치 `pos`, 자식 digest `d_L, d_R`):
  - `Acc = P(d_L ⊕ mask(l,pos,0)) ⊕ P(d_R ⊕ mask(l,pos,1))`   ← 2-블록 누산
  - `nodeDigest = trunc_n( P(Acc ⊕ maskMid(l, pos)) )`
- **Root**: 최상위 노드 digest가 출력. **전체 길이 + 트리 모양을 root call의 framing에 인코딩**
  (BLAKE3의 length-flag / Sakura final-node에 해당)하여, 서로 다른 메시지가 노드 충돌 없이
  동일한 node-input 트리를 만들 수 없게 한다.

**③ Level/Leaf/Root 도메인 분리(필수)**

Sakura coding이 sponge-tree에서 second-preimage를 막는 것과 동일한 이유로, level이 다른 노드의
digest는 구분되어야 한다. `maskMid`에 level/leaf/root 태그를 주입한다. 누락 시 내부 노드를
leaf로(혹은 그 역으로) 오용하는 공격이 성립한다.

**설계 노브.** Leaf arity `t`를 작게 고정(예 `T_max = 8`)하면 leaf-level XOR 누산이 large-`k`
Wagner가 아니라 small-`k` generalized birthday가 되어 분석이 통제 가능해진다. Internal 노드는 항상
`t = 2`. Chaining value 크기 `n`이 곧 보안 강도를 결정하므로 목표 강도에 맞춰 설정한다
(`n = 768` → ~`2^384` 충돌 보안).

---

## 보안 분석

보안은 keyed/unkeyed 두 모드에서 질적으로 다르다.

### keyed (예: MAC/AEAD + verified streaming 등)

마스크가 비밀 키에서 유도되므로, **Farfalle의 PRF 보안이 그대로 적용된다.** 압축 레이어의
XOR 누산과 확장 레이어의 출력 모두 비밀 마스크에 의해 의사난수화되며, 트리 합성은 키 의존
도메인 분리(level/pos 인코딩) 위에서 이루어진다. 따라서:

- **Verified streaming이 가장 자연스러운 활용처다.** Root digest를 MAC 태그로 두면, 전체
  ciphertext를 버퍼링하지 않고 **청크 단위로 O(log n) inclusion path를 통해 root 태그에 대해
  인증**할 수 있다 (스트리밍 복호화 시 청크별 선검증 후 평문 출력).
- 키가 비밀인 한 XOR 누산 충돌은 마스크를 모르는 적에게 계산적으로 불가능하므로, 이전 턴에서
  논의한 unkeyed 모드의 generalized-birthday 우려가 발생하지 않는다.

요약: **keyed 모드는 기존 Farfalle 보안의 직접 상속 + 트리 도메인 분리**로 닫힌다(상대적으로
깔끔한 길).

### unkeyed (예: content-addressed hash 등)

비밀 키가 없으므로 보안은 **[permutation의 이상적 무작위성 → collision resistance]으로
환원된다.** `P`를 이상적 random permutation으로 모델링(RPM)하면, TF의 충돌 저항은 다음 두 의무로
분해된다(직접 CR reduction):

1. **노드 함수의 충돌 저항** — `node`가 `trunc_n(P(Acc ⊕ maskMid))` 형태이므로,
   - 절단 birthday 항: `≤ q²/2^(n+1)` (지배항),
   - XOR-누산 충돌 항 `ε_acc`: internal 노드(`t=2`)는 `≤ q²/2^b`로 무시 가능, leaf 노드는
     `T_max`에 의존하는 generalized-birthday(Wagner) 항 — `≪ q²/2^n`이 되도록 arity를 통제.
2. **트리 인코딩 단사성** — `encode : msg → node-input tree`가 단사이면 충돌은 오직 노드 충돌에서만
   발생(비확률적 의무, Sakura decodability에 해당).

합쳐서:

```
Adv^{CR}_{TF}(A)  ≤  q²/2^(n+1)  +  ε_acc(q, T_max)  +  0
```

`n = 768`에서 ~`2^384` 충돌 보안(PQ ~`2^192`).

**열린 공백(정직하게).** Farfalle는 본래 *keyed* deck function으로 설계됐고, **unkeyed
instantiation의 보안에 대한 출판된 증명은 없다.** 위 reduction, 특히 leaf XOR-누산의
generalized-birthday 항이 `q²/2^n`보다 작게 눌리는지는 *증명되어야 할* 연구 대상이다. 이
환원의 machine-checked 검증(EasyCrypt, Formosa의 Keccak-p[1600] / sponge-indifferentiability
형식화 위에 구축)이 별도 프로젝트로 준비되어 있으며, 만약 `ε_acc`가 지배적이라면 정직한 결론은
(a) arity 추가 통제, (b) accumulator에 feedforward 도입(순수 선형성 제거), (c) keyed/salted
변종으로의 후퇴 중 하나다.

---

## 타 스킴들과의 비교

### vs K12 (KangarooTwelve)

| 항목 | K12 (tree-sponge) | Farfalle-tree |
|---|---|---|
| 노드 내부 | sponge 흡수(직렬) | Farfalle 압축(블록 단위 병렬) |
| 청크 내 병렬성 | 없음(청크 내 순차) | 있음(leaf 내부 누산 병렬) |
| 기반 permutation | Keccak-p[1600] (TurboSHAKE는 12라운드) | 동일하게 사용 가능 |
| 표준화/증명 | RFC 9861, sponge indifferentiability 증명 보유 | 미표준·unkeyed 미증명 |

K12는 sponge가 본질적으로 직렬이라 청크 *내부*가 순차 처리된다. Farfalle-tree는 leaf 내부의
압축 레이어가 병렬이라 **청크 내 블록을 동시에 fan-out**할 수 있다 — FPGA/PE 어레이에서 단위
면적당 throughput 우위가 기대되는 지점. 다만 그 우위는 "이미 검증된 K12 대비 미검증"이라는
대가와 맞바꾼 것이다. 라운드 감축(TurboSHAKE의 12라운드)은 양쪽 모두에 동일하게 적용 가능.

### vs BLAKE3

| 항목 | BLAKE3 | Farfalle-tree |
|---|---|---|
| 노드 압축 | ARX 7라운드 compression(가벼움) | full permutation 호출(무거움) |
| 트리 | 이진 Merkle | positional-mask Merkle |
| 모드 | unkeyed/keyed/KDF 단일 프리미티브 통합 | keyed=deck function, unkeyed=hash |
| verified streaming | 지원 | 지원(설계 목표) |
| 보안 강도 | 256-bit | `n`으로 조정(예 768→384-bit) |

BLAKE3는 노드당 ARX 7라운드라 노드 레이턴시가 낮고 구조가 단순하며 실전 검증이 풍부하다.
Farfalle-tree는 노드당 full Keccak-p 호출이라 노드당 비용이 크지만, leaf 내부 병렬성과 큰
permutation 폭(여유 있는 누산 birthday 마진)을 얻는다. 라운드 감축 없이는 BLAKE3보다 무겁고,
Xoodoo 기반(Xoofff식)으로 가면 permutation 자체가 훨씬 가벼워 이 격차가 좁혀진다.

---

## 진지하게 생각해봐야 할 지점들

### CSPRNG(예: `arc4random` 등)들과의 관련성

CSPRNG는 본질적으로 **키드 확장**(seed → 긴 의사난수 스트림)이다. Farfalle의 *확장 레이어*가
바로 이 역할 — 입력에 대한 PRF 출력을 병렬로 squeeze한다. 즉 keyed Farfalle-tree는 확장
레이어를 통해 그 자체로 CSPRNG 코어가 된다(seed+counter → 스트림). 현대 `arc4random`은
ChaCha20으로 구동되는데, 같은 자리에 Farfalle 확장을 두면 **병렬 squeeze**라는 차이가 생긴다.

다만 정직하게: `arc4random`의 가치는 단순성·fork-safety이지 병렬성이 아니므로 그 틈새엔
Farfalle-tree가 과잉이다. 그리고 **트리는 CSPRNG 용도에 아무것도 더하지 않는다**(트리는 입력
측 구조이고 CSPRNG는 출력 측 확장을 쓴다). 관련성의 핵심은 "deck function이 CSPRNG 역할을
*포함*하되, 트리는 그와 직교한다"이다. Unkeyed 해시 모드라면 CSPRNG가 아니라 Hash-DRBG
(HMAC/Hash-DRBG 패턴)로만 우회 구성 가능.

### 스트림 암호와 XOF가 동일한 암호화 프리미티브를 공유하는 것

지적한 DJB 계보는 정확하다 — ChaCha(스트림 암호, DJB)와 BLAKE 계열(해시/XOF, Aumasson 등이
설계하되 ChaCha의 ARX 코어 위에 구축)이 하나의 ARX 프리미티브를 공유한다. **Keccak/Xoodoo
세계는 이를 더 명시적으로 한다**: 단일 permutation 위에 모드만 바꿔

- sponge/tree → SHA-3 / SHAKE(해시·XOF),
- duplex → Keyak/Ketje/Xoodyak(AEAD),
- Farfalle → Kravatte/Xoofff(PRF·스트림·MAC)

가 모두 올라간다. 그리고 **Farfalle는 정의상 deck function**(Doubly-Extendable Cryptographic
Keyed function)이라 PRF/MAC/스트림/AEAD를 *설계 단계에서* 통합한다. 여기에 트리를 더하면
해시·verified streaming 측면이 추가된다.

따라서 Farfalle-tree는 **단일 permutation 위에서 DJB식 "하나의 프리미티브, 여러 역할"을 — ARX
계열보다 오히려 더 완결적으로 — 실현**한다. 단, 같은 permutation을 keyed(스트림)와
unkeyed(해시)로 동시에 쓸 때 두 용도가 간섭하지 않도록 **IV/frame 비트 도메인 분리**가
반드시 필요하다(이것이 ChaCha vs BLAKE3-XOF가 코어는 공유하되 *구성*은 분리되는 것과 정확히
대응한다).

### 추가적인 개조/응용 가능성들

#### multi-key hashing 실현 가능성

두 층위로 갈린다.

- **실용적(직관적):** 서브트리마다 다른 키로 마스크를 유도하면, 청크별/서브트리별로 서로 다른
  키로 인증하고 root에서 결합하는 구조가 곧바로 나온다. federated/multi-tenant 인증 자료구조,
  per-namespace 키 분리 등에 유용. 구현·분석 모두 무난하다.
- **사변적(아키텍처 의존):** 압축이 per-block 기여의 XOR라는 **선형성**은 key-homomorphic /
  aggregatable 방향을 유혹한다. key-homomorphic PRF는 `F(k1,x) ⊕ F(k2,x) = F(k1⊕k2, x)`를
  만족하는데, Farfalle는 키가 마스크의 *비선형* permutation을 통해 들어가므로 자명하게는
  KH가 아니다. 마스크를 선형 주입하는 변종이 근접할 수 있으나, 알려진 KH-PRF는 격자/DDH
  기반이고 **permutation 기반 KH-PRF는 사실상 미해결**이다 — PRF 보안과 충돌하기 쉬우니
  "흥미로운 열린 문제"로만 표시.

#### 순수 성능: 상한은 다소 타협하더라도 하한을 가능한 한 높게

목표를 "보장된 최소 throughput(하한)을 최대화"로 읽으면, 핵심은 **입력 의존 분산을 제거**하는
것이다.

- **데이터 독립성으로 하한이 곧 상한에 붙는다.** Keccak/Xoodoo/ARX는 입력 의존 분기·메모리
  접근이 없어 permutation 호출 단위에서 worst-case = best-case다. 즉 입력 내용에 의한 변동이
  원천 차단되어 강한 worst-case 보장을 *공짜로* 얻는다.
- 남는 변동은 **구조적**이다 — (a) 아주 작은 입력에서 트리 고정 오버헤드가 per-byte를 망치고,
  (b) 병렬 폭이 낮은 입력. 대응: **single-leaf fast path**(메시지 ≤ 청크면 트리 생략, K12가 하는
  방식), **최소 SIMD lane 수 고정**(작은 입력도 패딩해 일정 병렬 폭 보장 → peak는 희생하되 floor
  확보), arity 상한.
- 추가 레버: TurboSHAKE식 라운드 감축은 호출당 비용을 균일하게 낮춰 floor·ceiling을 동시에
  올리되 보안 마진을 깎는다(상한 타협↔하한 상승의 명시적 거래).

정리하면, 데이터 독립 프리미티브가 입력 의존 분산을 무너뜨리므로, 남는 일은 **고정 트리
오버헤드 amortize + 최소 병렬 폭 강제**다.

#### universal hashing (keyed 또는 unkeyed)

Wegman–Carter 패턴이 정확히 들어맞는다: **빠른 universal hash(UH)로 데이터를 압축 → permutation
으로 finalize.**

- Leaf를 대수적 UH(예 다항식 평가, NH/UMAC식 multilinear)로 두면 leaf 레벨이 거의
  메모리 대역폭 속도가 되고, **permutation은 (훨씬 작은) 트리 노드 레벨에서만** 호출된다 →
  앞의 "성능 하한 확보"와 직결되는 강력한 조합.
- Farfalle 압축 *자체*는 깨끗한 ε-almost-universal 족이라기보다 의사난수적으로 행동한다. 대수적
  ε-AU 보장(예 충돌확률 `≤ (#blocks)/2^n`)이 필요하면 leaf를 명시적 다항식/multilinear UH로
  교체하는 게 정공법이다. keyed면 평가점이 키, unkeyed면 NUMS 상수 + permutation 의존 보안.

#### 각종 수학적 구조/체계와의 결합

UH leaf의 대수적 substrate 선택 문제로 귀결되며, 실증성 순으로:

- **유한체 위 단변수 다항식 (검증됨·최우선):** Poly1305(`GF(2^130−5)`), GHASH(`GF(2^128)`)
  스타일. leaf = 메시지 블록을 계수로 한 다항식을 비밀점에서 평가, ε-AU. 트리와 가장
  깔끔하게 결합되는 실전 1순위.
- **다변수/multilinear (검증됨·최대 병렬):** UMAC의 NH `Σ (m_{2i}+k_{2i})(m_{2i+1}+k_{2i+1})`,
  VMAC류. Δ-universal이며 SIMD 친화적 → leaf 병렬성 극대화, "하한 확보"와 시너지.
- **유한체 일반 (substrate):** `GF(2^n)`는 carryless mult(PCLMULQDQ / FPGA LUT에 저렴)로
  하드웨어 친화 — FPGA 가속기 맥락에서 유의미. `GF(p)`(Mersenne 류)는 범용 ALU 친화.
- **가우스 정수 `Z[i]` / 아이젠슈타인 정수 `Z[ω]` (사변적·표현 차원):** 정직하게, 이들의
  몫환 `Z[i]/(π)`·`Z[ω]/(π)`은 적절한 소수에서 **결국 유한체 `GF(p)`가 되므로** 암호학적
  강도를 새로 더하진 않는다. 가치는 *표현/구조*에 있다 — (i) 격자·6중/4중 대칭 구조가
  특정 NTT/transform-domain 연산에 매핑되어 큰 블록의 FFT 기반 곱셈을 가속할 여지,
  (ii) **병익님의 DOST/spectral·WarpedDOST 작업과 맞닿는 transform-domain 해싱**이라는 연결
  고리(주파수 영역에서 누산하는 leaf hash 등), (iii) 구조화 격자 가정과의 접점(원하면 PQ
  flavor). 새 보안이 아니라 하드웨어 매핑·변환영역 표현으로서의 탐색 가치로 한정해 볼 것.

---

## 상태 / 주의

- 본 문서는 *설계 제안*이다. keyed 모드는 기존 Farfalle 보안 + 트리 도메인 분리로 비교적 깔끔히
  닫히지만, **unkeyed 모드의 충돌 저항은 미증명 영역**이며 그 정형 검증이 핵심 미해결 과제다.
- 모든 보안 논의는 `P`의 이상적 random-permutation 모델 가정을 상속한다(SHA-3 indifferentiability
  증명과 동일한 idealization caveat). 실제 Keccak-p[1600]는 이상적이지 않다 — 가정을 숨기지 말 것.
- "수학적 구조" 절의 가우스/아이젠슈타인 방향은 명시적으로 사변적이며, 채택 전 실증
  벤치마크와 ε-AU 경계 증명이 선행되어야 한다.
