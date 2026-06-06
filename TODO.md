# TODO — 남은 작업 목록

> *현재 v0.1 단계 이후* 진행해야 할 항목. 우선순위와 책임 영역으로 분류.
> 각 항목은 이미 분석·skeleton이 작성된 산출물을 참조하므로 *처음부터* 작성할 필요 없음.

---

## A. 내부 (이 저장소 안에서 가능)

### A1. P3-#13 — CI 자동화
*우선순위: 중간 (저장소 안정성 보장).*

- [ ] GitHub Actions workflow (`.github/workflows/ci.yml`)
  - musl 빌드 (`x86_64-unknown-linux-musl`)
  - YSC3/YSC4/YSC5 모든 테스트 실행
  - Isabelle session 빌드 (Q1/Q2/Q3 형식 검증)
  - Typst 컴파일 검사 (SPEC.pdf 생성 확인)
  - MILP 모델 실행 (glpsol 가용 시)
- [ ] `cargo audit` / `cargo deny` 통합 (의존성 보안)
- [ ] `cargo clippy --all-features -- -D warnings`
- [ ] 매트릭스 빌드: stable + nightly (simd feature)

참조: 본 저장소의 디렉토리 구조 (`README.md`).

### A2. YSC5 SIMD backend 실제 검증
*우선순위: 낮음.*

- [ ] nightly toolchain으로 `cargo +nightly build --features simd` 검증
- [ ] `tests::simd_roll_matches_soft` 실행
- [ ] x86_64 AVX2/AVX-512, ARM NEON 분기 측정
- [ ] WASM SIMD (`v128`) 호환성

참조: `ysc5/SIMD.md`, `ysc5/src/simd.rs`.

### A3. YSC5-AEAD-Seekable 모드 추가
*우선순위: 낮음 (use-case가 명확할 때).*

- [ ] Nonce를 (12 byte compress + 12 byte stream-offset)로 분할하는 변종 사양화.
- [ ] `Ysc5AeadSeekable<V>` 새 타입 추가, 같은 `key_setup`/`Compressor` 재사용.
- [ ] Random-access decryption PoC.

참조: `farfalle-gen/NOTE-aead-nonce-split.md`.

### A4. YSC3/YSC4 SPEC.md → 본문 충실한 Typst로 확장
*우선순위: 낮음 (현재 요약본만 있음).*

현재 `ysc3/SPEC.typ`, `ysc4/SPEC.typ`는 *요약본*. 마크다운 SPEC.md는 그대로 보존.
- [ ] YSC3 SPEC.md 353줄을 Typst로 *완전 변환*.
- [ ] YSC4 SPEC.md 234줄을 Typst로 *완전 변환*.

참조: 두 SPEC.md 파일 + `ysc5/SPEC.typ`을 모델로.

---

## B. Research-grade (외부 협업·발표 수준)

### B1. Bit-level MILP 차분/선형 트레일
*우선순위: 높음 (YSC5 사양의 라운드 수 결정에 핵심).*

현재 워드-수준 MILP (`milp/analysis.md`)는 *보수적 하한*만 제공. 정식 평가는:
- [ ] **F 함수의 DDT 사전 계산** — 64-bit input → 64-bit output 차분 분포.
- [ ] **Bit-level MILP 모델** — 1024 변수/라운드, 회전·AND·XOR 인코딩.
- [ ] **Gurobi / CPLEX** 같은 상용 solver 사용 권장 (GLPK는 비트-level 규모에서 느림).
- [ ] **R∈{8, 10, 12, 14, 16, 20}**에 대한 trail 확률 정량.
- [ ] **Linear hull** 분석 (LAT 기반).
- [ ] **Boomerang / integral** 변종.

참조: `milp/README.md`, `farfalle-gen/RESOLVED-q3-q8.md` Q3.

### B2. CryptHOL multi-key formal proof
*우선순위: 중간 (claim 형식화).*

- [ ] `farfalle-gen/NOTE-multikey-security.md`의 CryptHOL skeleton 완성.
- [ ] Bertoni–Daemen 2017 Farfalle 환원의 Isabelle 형식화.
- [ ] Mennink-style multi-key bound 증명.
- [ ] Single-key PRP→PRF 환원의 자세한 단계.

참조: AFP의 `CryptHOL`, 이미 빌드된 session 사용.

### B3. FHE 백엔드 실측 (tfhe-rs / OpenFHE)
*우선순위: 중간 (사양의 정량 검증).*

- [ ] **tfhe-rs**: YSC5 한 블록의 wall-clock 측정.
  - [ ] F 함수를 tfhe boolean gates로 구현.
  - [ ] α-mult이 plaintext-mult로 컴파일되는지 확인.
  - [ ] 1 PBS ≈ 10ms 가정 검증.
- [ ] **OpenFHE / Microsoft SEAL**: BFV/BGV batched 측정.
  - [ ] N_slots = 4096에서 slot당 비용.
  - [ ] AES-128 (T-table free 변종)과의 비교.
- [ ] **HEXL / GPU 가속** 검증.

참조: `farfalle-gen/NOTE-fhe-cost.md`의 해석적 추정과의 일치 여부.

### B4. 외부 학계 검토 회부 + 정식 발표
*우선순위: 낮음 (사양 안정화 후).*

- [ ] 영문 사양서 작성 (Typst → 영문 번역).
- [ ] *FSE / ToSC / CRYPTO* submission 준비.
- [ ] arXiv pre-print.
- [ ] *Real World Crypto*, *PQC* 등 conference 발표.
- [ ] CFRG / NIST 표준화 흐름 (cryptographic suite로 등록 후보).

참조: 본 저장소 `README.md` §"외부 검토 요청 항목".

---

## C. 보조·인프라

### C1. ysc4 SIMD backend 실제 구현
*우선순위: 낮음.*

현재 `ysc4`의 `simd` feature는 `#![feature(portable_simd)]` 활성화만 하고 *별도 SIMD 코드 없음*.
- [ ] `ysc4/src/simd.rs` 추가: σ-층 16개 워드를 `u64x4 × 4`로 병렬화.
- [ ] α-mult의 vector intrinsic 활용.
- [ ] soft 백엔드와의 비트 동일성 단위 테스트.

### C2. SIMD 백엔드 cross-version 일관성 보장 (V7 회피)
*우선순위: 중간 (사양 위생).*

- [ ] YSC3/YSC4/YSC5 모든 simd 변종이 soft와 *비트 단위 동일*함을 CI에서 강제.
- [ ] `auxcrypt_simd_vs_soft_consistency` 같은 회귀 테스트 패턴.

참조: 본 보고서 §5.2 V7 결함.

### C3. ysc2 cryptanalysis attack PoC 정리
*우선순위: 낮음.*

현재 `attack/`의 PoC는 YSC2 cryptanalysis 결과를 재현. 외부 검토자가 쉽게 실행할 수 있도록:
- [ ] `attack/README.md` 추가.
- [ ] 각 공격을 한 줄 설명 + 예상 출력 포함.
- [ ] CI에서 attack PoC도 통과 확인.

---

## D. 문서·표준화

### D1. SECURITY.md
*우선순위: 중간.*

- [ ] 위협 모델 명시 (single-key, related-key out of scope, etc.)
- [ ] 알려진 한계 (v0.1 stage warnings).
- [ ] vulnerability 보고 절차.

### D2. CONTRIBUTING.md
*우선순위: 낮음 (협업자 진입 시).*

- [ ] 코드 스타일 (musl + no_std + RustCrypto).
- [ ] PR 절차 + CI 통과 요구사항.
- [ ] commit 메시지 컨벤션.

### D3. RFC 문서화 (CFRG / IETF)
*우선순위: 낮음 (표준화 단계).*

본 작업이 외부 채택 단계에 이르면:
- [ ] draft-ysc5-prf-stream-aead-XX.txt 형식.
- [ ] Test vectors 표준화.
- [ ] Reference implementation 인증.

---

## 우선순위 매트릭스

| 항목 | 우선순위 | 작업량 | 외부 의존 |
|------|---------|--------|----------|
| A1 CI | 중간 | 2~4시간 | GitHub Actions |
| A2 SIMD 실제 빌드 | 낮음 | 1~2시간 | nightly toolchain |
| A3 Seekable AEAD | 낮음 | 1일 | — |
| A4 SPEC.typ 확장 | 낮음 | 1일 | — |
| **B1 bit-level MILP** | **높음** | 1~2주 | Gurobi or CPLEX |
| B2 CryptHOL proof | 중간 | 1~2개월 | AFP, formal methods 전문가 |
| **B3 FHE 실측** | **중간** | 1~2주 | tfhe-rs / OpenFHE |
| B4 학계 회부 | 낮음 | 3~6개월 | conference 사이클 |
| C1 ysc4 SIMD | 낮음 | 1일 | nightly |
| C2 SIMD 일관성 CI | 중간 | 2~4시간 | A1 의존 |
| C3 attack README | 낮음 | 2시간 | — |
| D1 SECURITY.md | 중간 | 1시간 | — |
| D2 CONTRIBUTING.md | 낮음 | 1시간 | — |
| D3 RFC | 낮음 | 1~2개월 | 표준화 단계 |

---

## 권장 진행 순서

1. **A1 CI + D1 SECURITY.md + C3 attack README** — 저장소 안정화 (1~2일).
2. **B1 bit-level MILP** — 사양 라운드 수의 정량 검증 (핵심 연구).
3. **B3 FHE 실측** — 비용 모델 검증 (이론과 실제 일치 확인).
4. **B4 학계 회부 준비** — 영문 사양 + pre-print.
5. **B2 CryptHOL 정식 증명** — 학술 협업 시.

각 항목 진행 시 `git checkout -b todo/<항목 코드>` (예: `todo/B1-milp-bitlevel`) 권장.
