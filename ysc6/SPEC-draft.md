# YSC6 사양 초안 (v0.0-pre)

> *경고: **설계 초안**(착수 단계). 모드/라운드수/보안분석 미확정. yttrium-large 순열 자체가
> v0.2-pre(미검증)이므로 YSC6은 그 미검증 상태를 **상속**한다. 어떤 환경에서도 사용 금지.*
>
> **YSC6** = YSC 스트림 계열(YSC2→3→4→5)의 차기. **YSC3–5의 CTR-Sponge 모드**(검증된 rate/
> capacity 분할)에 **yttrium-large 순열**(영합 Lai-Massey + ARX, 1024-bit; `yttrium/src/large.rs`,
> `milp/yttrium-large-rounds.md`)을 얹는다. σ-GLM(YSC4-p)의 확률-1 약점(R\*=8까지 생존)을 ARX의
> 빠른 확산(R=2 noise floor)으로 대체 → **YSC4보다 적은 라운드로 동등 보안** 가능성(정량 검증 필요).

## 0. 계보와 동기

| 세대 | 순열 | 모드 | 비고 |
|---|---|---|---|
| YSC2 (AuxCrypt) | Lai-Massey(affine 결함) | sponge+capacity 노출 | **폐기**(V1–V10, REPORT.md) |
| YSC3 | GFN + NORX H | CTR-Sponge(rate/cap 분할) | V1–V6 차단 |
| YSC4 | σ-GLM(XOR-reduce+F+broadcast+σ+π) | YSC3 모드 그대로 | FHE 1/8 비용; YSC4-p→yhash |
| YSC5 | YSC4-p | Farfalle(병렬) stream/AEAD/XOF | RustCrypto traits |
| **YSC6** | **yttrium-large(영합 LM+ARX+all-16 σ)** | **YSC3–5 CTR-Sponge(+Farfalle 옵션)** | ARX 빠른 확산 → 라운드↓ 목표 |

YSC4-p와 yttrium-large는 **둘 다 1024-bit(16×u64)** 라 모드가 drop-in 정합. 핵심 변경은 순열뿐.

## 1. 순열 (YSC6-p = yttrium-large)

`yttrium/src/large.rs`의 1024-bit 순열을 그대로 사용:
- 16 × u64 = 1024-bit 상태. GF(2⁶⁴) red 0x1B.
- 라운드: ι(RC=SHA-512 K[r], 레인 r%16) → x'ᵢ=ROTL₈(xᵢ) → S=Σεᵢ·x'ᵢ(영합, ε=[+,−]×8) →
  t=F(S) → yᵢ=ROTR₉(x'ᵢ⊞t) → σ: yᵢ←α^{kᵢ}·yᵢ(all-16, k=[1..15,17]) → π=(5i+7)mod16.
- F(s)=s⊕(s⋘7∧s⋘17)⊕(s⋘3∧s⋘21)⊕(s⋘9∧s⋘29).
- 가역(영합), GF(2)-선형 R\*=17·prob-1 R\*=2, per-round 감쇠 ~u32의 2배(§yttrium-large-rounds).

> YSC6은 순열을 *해시*가 아닌 *스트림*에 쓰므로 라운드수는 **독립 재정당화**(§5). yttrium-large의
> 해시-acc-충돌 분석은 그대로 적용 안 됨(스트림은 capacity-비노출이 추가 방어).

## 2. CTR-Sponge 스트림 모드 (YSC3–5 이월)

```
상태 1024-bit = rate ‖ capacity.
  init:   capacity ← key (LE);  rate ← nonce ‖ 0;  최상위 워드 ⊕= DOMAIN_STREAM
          permute(state, R_init)
  block i: working = state
           working[capacity 워드] ⊕= i        # 카운터는 capacity에만(rate 비접촉)
           permute(working, R_block)
           keystream_block = working[rate 워드]  # rate 절반만 출력, capacity 비노출
  암호문 = 평문 ⊕ keystream
```

핵심 보안 불변(YSC2 결함 교정 이월):
- **키는 capacity 전용 → 키스트림에 직접 노출 안 됨**(YSC2 V1/V2 차단).
- **순열은 가역이나 capacity 비노출로 상태복구 차단**(rate만 보임; capacity ≥ 보안수준).
- **도메인 분리**(stream/AEAD/XOF 태그)로 cross-protocol 차단(YSC3 V10).
- **카운터=capacity 주입**(rate 직접 접촉 없음).

## 3. 매개변수 (초안 — *잠정*)

| 항목 | YSC6-128 | YSC6-256 |
|---|---|---|
| 키 | 256-bit (capacity) | 512-bit (capacity) |
| nonce | 192-bit (rate) | 192-bit |
| rate / capacity | 512 / 512 | 256 / 768 |
| keystream/block | 512-bit (rate) | 256-bit |
| R_init / R_block | **잠정** (§5) | 잠정 |
| 도메인 | `"YSC6-S\0\0"` 등 (stream/aead/xof) | 동 |

> R_init/R_block: YSC4는 32/16(σ-GLM). yttrium-large는 ~2배 빠른 확산이라 **더 적게**(예: R_block
> 8~12) 가능할 것으로 *예상*하나 §5 정량 정당화 전엔 미정. 보수적으로 YSC4값(32/16)에서 출발.

## 4. 모드 확장 (YSC5 이월 — 후속)

- **AEAD**: duplex(흡수 AD → 암호화 → tag). 도메인 분리.
- **XOF**: 임의길이 출력(rate squeeze).
- **RustCrypto traits**: `StreamCipherCore`·`AeadCore` 호환(YSC5 convention).

## 5. 검증 의무 (신규 — 전부 reset)

YSC6은 새 primitive다. 더해 **yttrium-large 순열의 미검증 상태를 상속**한다.

- **A. 순열 상속 검증**: yttrium-large의 R1(형식검증)·R5(외부분석)·deep-slope가 선행. (현 v0.2-pre.)
- **B. 스트림 모드 라운드수**(R_init/R_block): capacity-비노출 + nonce 처리 기준 차분/선형 trail로
  정당화. yttrium ARX 빠른 확산으로 YSC4(32/16) 대비 감소 가능성 정량화.
- **C. nonce 정책**: nonce 재사용 시 keystream 재사용(2-time pad) — 정책 명시(unique nonce 필수).
  nonce 길이·도메인.
- **D. 상태복구/구분자**: capacity-비노출 sponge 표준 환원(rate q²/2^cap 등) + ARX 특이공격.
- **E. AEAD 위조/무결성**: tag 위조 저항, AD 처리 단사.
- **F. 동결 + KAT + RustCrypto KAT 교차**.
- **G. constant-time**: yttrium-large 순열 상수시간(yttrium §10-G) 이월 + 모드 CT.
- **H. 외부 공개 암호분석**.

## 6. 미해결 / open

1. **순열 선택**: yttrium-large(1024-bit) 확정 vs yttrium(256-bit) 경량 YSC6-lite 여부.
2. **R_init/R_block** 잠정(§5-B).
3. **rate/capacity 분할** 최종(보안수준 대비).
4. Farfalle(YSC5식 병렬) vs 단일-sponge 선택.
5. AEAD/XOF 사양.

## 7. 변경 이력
- v0.0-pre: 착수. YSC3–5 CTR-Sponge + yttrium-large 순열 골격. 모드·라운드·분석 미확정.

---

# 부록 A. 파생 아이디어 — yttrium G로 SipHash 직접 대체 가능성 (검토)

**질문**: yttrium(not -large)의 **G 함수(ARX 결합기)** 를 추출해 SipHash 직접 대체재 설계에 쓸 수 있나?

## A.1 사실 관계

- **G는 독립 함수가 아니다**(`yttrium/src/lib.rs` round): "framing(ROTL₈) → 영합 ±reduce → F(S) →
  ⊞broadcast(ROTR₉) → all-8 σ → π"의 4-계층 시퀀스. 추출이 무의미한 이유:
  - **영합 reduction이 가역에 load-bearing**(Σε=0 항등식) — 떼면 구조 붕괴.
  - **σ all-8 distinct power가 보안에 필수**(부분 σ는 MSB-쌍 약점 부활, 실측).
  - F는 전체 상태가 아니라 *축약값 S 단일 워드*에 적용.
- **속도**: yttrium-(8,12,24) ~39–72 MB/s vs **SipHash-2-4 ~3659 MB/s** → **~50–93× 느림**
  (`yttrium/BENCH.md`). SipRound = 워드당 add-rotate-xor 1회로 극경량; yttrium 라운드는 F(AND 3쌍)
  + σ(α-step 37) + 영합으로 훨씬 무겁다.
- **인터페이스**: SipHash = 직렬 압축·128-bit 키·64-bit 출력·2–4라운드. yttrium = Farfalle-tree·
  변형별 키·128-bit 출력. 직접 정합 안 됨.

## A.2 판정

| 시나리오 | 가능성 | 사유 |
|---|---|---|
| **G 추출 → SipRound 대체(drop-in)** | **불가** | G는 결합·중량. SipHash 속도 니치(짧은 입력 초고속)에 부적합 |
| **yttrium keyed를 SipHash 용도(DoS 해시테이블)로** | 기능적으론 가능, **비권장** | yttrium-(4,6,8) keyed+64-bit truncate로 동작은 하나 ~20–90× 느려 SipHash의 *속도* 이점을 잃음. 보안마진은 더 큼 |
| **yttrium 아이디어 기반 *신규* 경량 ARX PRF** | **별도 설계로 가능** | 영합 LM + ARX broadcast 아이디어를 *최소 라운드*(F 없이 또는 경량, σ 생략, 작은 상태)로 재구성한 SipHash-class PRF. "G 추출"이 아니라 새 설계 |

## A.3 결론(정직)

- **"G 추출 → SipHash 직접 대체"는 비현실적** — G가 라운드에 고착·중량이고 yttrium은 SipHash보다
  ~2자릿수 느리다. SipHash의 가치는 *짧은 입력 초고속 keyed*인데 yttrium은 그 반대 프로파일.
- **대안**: SipHash 대체가 목표라면 yttrium의 *설계 아이디어*(영합 가역 LM + ARX carry 비선형)를
  빌려 **새 경량 PRF**(작은 상태 2–4×u32, F 제거·경량 σ, 2–4라운드, 64-bit 출력, RustCrypto `Mac`)를
  설계하는 편이 정도. 이는 "추출"이 아닌 별도 프로젝트(YSip?)이며 자체 암호분석 필요.
- 단, **SipHash가 비암호학적(64-bit) DoS용**임을 감안하면, 굳이 yttrium 계열로 대체할 동기가 약함
  (속도가 핵심 가치). yttrium 계열은 *암호학적 keyed 해시/스트림*(YSC6)에 집중하는 게 합리적.

## A.4 정밀화 — G 전체 대신 **RAR(ROT→ADD→ROT) 코어만** 추출 (유망)

G 전체 추출이 막히는 건 영합 reduction·F·all-8 σ의 *결합* 때문. **코어 ARX 프리미티브**
`rar(x,y) = ROTR_β(ROTL_α(x) ⊞ y)` 만 떼면 이야기가 다르다 — rar은 **자기완결적**(SPECK 빌딩블록류,
3 ALU op: rotl·add·rotr)이라 결합 없이 추출 가능.

**viability 실측(`milp/rar_avalanche.py`, 256-bit 4×u64, 1-bit 차분 avalanche):**

| R | SipRound (mean/256, worst\|p−0.5\|) | RAR-round (mean, worst) |
|---|---|---|
| 4 | 127.9 / 0.013 | 115.8 / 0.070 |
| 5 | 128.0 / 0.015 | **127.3 / 0.014** (완전확산) |

→ SipRound R4 vs **RAR-round R5** 완전확산 — **1라운드 차로 comparable**. rar은 F·σ·GF 없이
ARX(테이블無·CT)라 **SipHash-급 속도 잠재**(full yttrium의 50–93× 둔화와 정반대).

**판정**: **RAR 코어 추출 = viable.** "G 추출"의 현실적 답은 이것 — rar을 라운드 프리미티브로 한
경량 keyed PRF(작은 상태·~5라운드·128-bit 키·64-bit 출력·RustCrypto `Mac`). 단:
- **yttrium 분석 상속 안 됨** — rar-네트워크의 차분/선형/회전 trail·라운드수·키스케줄을 **자체 암호분석**.
  (rar은 SPECK 핵심이라 ARX 분석 문헌 활용 가능.)
- (α,β)·cross-rot·워드믹싱 패턴은 SipHash/SPECK 대비 **재튜닝**(본 실측은 (8,9)+c=29 임시값).
- 별도 프리미티브(가칭 **YSip / RAR-PRF**)이지 yttrium "추출물"의 보안이 아님 — 정직히 신규 설계로.

**결론**: full-G는 비현실적이나 **RAR-코어 추출은 SipHash-class 경량 PRF의 실질적 출발점**이다.
추진 시 별도 프로젝트(YSip)로 자체 설계·분석. (yttrium은 암호학적 keyed 해시/스트림(YSC6)에 집중.)
