# YHash vs ahash vs FxHash vs SipHash13 — 벤치 결과

> 측정: x86_64 (단일 thread, `cargo run --release`).
> 라이브러리 버전: `yhash` (path), `ahash 0.8`, `rustc-hash 2`, `siphasher 1`.

## 1. State size (Hasher 인스턴스 메모리)

| Hasher | bytes |
|--------|------:|
| **YHasher** | **2,240** |
| SipHasher13 | 72 |
| AHasher | 32 |
| FxHasher | 8 |

YHasher는 단일 leaf buffer (1024 B) + tree 누적 spine (32 × 33 ≈ 1 KB) + IV 등으로 큰 상태. *HashMap 내 임시 instance가 많은 경우*에는 부담.

## 2. Throughput (입력 크기별 처리 속도)

| 입력 크기 | YHash | ahash | FxHash | SipHash13 |
|----------|------:|------:|-------:|----------:|
| 16 B    |     7 |  13,493 | 20,144 |     2,778 |
| 64 B    |    26 |  21,072 | 32,935 |     4,966 |
| 256 B   |    87 |  20,922 | 36,153 |     6,172 |
| 1 KB    |   166 |  20,483 | 29,850 |     6,570 |
| 4 KB    |   156 |  19,481 | 27,709 |     6,719 |
| 16 KB   |   154 |  18,741 | 25,809 |     6,583 |
| 64 KB   |   154 |  18,889 | 26,676 |     6,573 |

(단위: MB/s)

→ **YHash는 SipHash13보다 ~40배 느림**, ahash보다 ~130배 느림. Crypto-grade DoS 저항을
얻는 대가가 *명백히* 큼.

## 3. Per-call cost (HashMap-typical 작은 키)

| 키 길이 | YHash (ns) | ahash (ns) | FxHash (ns) | SipHash13 (ns) |
|--------:|-----------:|-----------:|------------:|---------------:|
| 4       |  2,400     | 1.21       | 0.99        |  3.75          |
| 8       |  2,400     | 1.21       | 0.80        |  4.52          |
| 16      |  2,400     | 1.22       | 0.81        |  5.81          |
| 32      |  2,400     | 1.78       | 1.24        |  8.18          |
| 64      |  2,400     | 3.00       | 1.95        | 12.71          |
| 128     |  2,400     | 5.76       | 3.61        | 22.27          |

→ YHash는 입력 크기에 거의 무관하게 **~2400 ns/hash** (트리 finalize 비용 dominant).
SipHash13은 **3.75 ns**로 *YHash의 ~640배 빠름*.

## 4. 의미 해석

### YHash 위치
- *Cryptographic-grade* 256-bit MAC/digest. *HashMap 핫패스에는 부적합*.
- 적합한 사용 사례:
  - File integrity hashing (한 번 계산 후 저장)
  - Per-chunk MAC for verified streaming (검증 비용을 한 번 분산)
  - Content-addressed storage (긴 입력 hashing)
- 부적합한 사용 사례:
  - 일반 HashMap key hashing (SipHash13/ahash 사용)
  - 매우 빈번한 small-key 조회

### 다른 hasher 적합성
- **FxHash**: 가장 빠름. *No DoS resistance* (공격자 제어 키 허용 시 위험).
- **ahash**: AES-NI 가속. DoS resistance 마진은 있으나 *crypto-grade는 아님*.
- **SipHash13**: 표준 (Rust default). Crypto-grade에 *근접*, throughput도 합리적.

### YHash 사용 권고
- HashMap에 사용하지 *말 것* (성능 페널티 vs 보안 benefit이 정량적으로 맞지 않음).
- **YHash가 빛나는 곳**: Blake3-class secure hash가 필요한데 256-bit + verified streaming
  + Farfalle 병렬 가능성이 필요한 경우 (CAS 시스템, 인증 가능 backup, etc.).

## 5. CPU/RAM 사용 패턴 (관찰)

벤치 실행 중 `top` 측정:
- YHash benchmark: 단일 thread 100% CPU. RSS ~2-5 MB.
- ahash/FxHash/SipHash13: 빠르게 종료 (vector op + ALU 집중).

YHash의 throughput이 낮은 이유는 **AND 게이트가 많은 비선형 함수의 직렬 실행**이지
*memory bound*가 아님. SIMD 백엔드로 8-branch 동시 처리 시 ~2-4배 가속 기대.

## 6. 가능한 yhash 가속 경로

| 항목 | 예상 가속 | 비고 |
|------|----------|------|
| SIMD 백엔드 (portable_simd) | 2-4× | 16-branch broadcast 등 |
| 단일-leaf inline (현재도 그렇지만 더 공격적으로) | 1.2× | code-bloat |
| 라운드 수 감축 (R_b 8 → 4) | 2× | 보안 마진 감소; 별도 분석 필요 |
| AVX-512 lane 사용 | 1.5× | platform 종속 |

가속 후에도 ahash/FxHash 수준에는 도달 불가. **포지셔닝: secure hash with HashMap-compatible API**.

## 7. 결론

YHash는 HashMap의 default hasher로 채택하기에는 너무 느리지만,
- *cryptographic-grade* DoS resistance + 256-bit digest
- Farfalle-tree의 verified streaming 지원
- formal verification 기반 (Y1~Y4)

이 세 가지가 *필요한* 시나리오에서는 유일하게 합리적인 선택. 보통의 HashMap 사용에는
`ahash` 또는 std `RandomState` (SipHash13) 채택을 권장한다.
