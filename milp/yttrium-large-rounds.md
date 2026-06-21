# yttrium-large (u64) 라운드 보안레벨 정당화

> u32 변형 라운드수가 yttrium-large(1024-bit 상태, 256-bit digest)에서 어떤 충돌저항을 주는가.
> 결론: **u64는 u32의 ~2배 가파른 per-round 감쇠**(16레인) → **(10,14,24)-large가 full 128-bit
> 충돌저항**(256-bit digest 상한)을 줌. 새 고라운드 변형 불필요.
> (정정: 초기 "R_b≈16~17 필요"는 u32 slope 오적용 — u64 slope 2배라 무효.)

## 측정 (직접)

| 측정 | 도구 | R1 | R2 | slope |
|---|---|---|---|---|
| u32/8-lane (기준) | `yttrium_round_decay.cu` GPU | 2⁻⁰ | 2⁻¹⁵·⁴ | +7.7 (R2→R3) |
| **u64/16-lane** GPU | `yttrium_large_decay.cu` N=2³⁰ | — | **2⁻²¹·⁵** | R3+ floor(2²⁴-bucket) |
| u64/16-lane reduced | `verify_large_slope.py` n=16, N=6e5 | 2⁻²·⁵⁷ | **≤2⁻¹⁹·²**(floor) | **R1→R2 ≥ +16.6** |

- GPU n=64: R2=2⁻²¹·⁵ (floor 2⁻²³ 위, 실측 앵커). R3+는 fold-floor라 미측정.
- reduced n=16: R2가 floor(2⁻¹⁹·²) 아래로 내려가 **slope(R1→R2) ≥ 16.6**. (u32 reduced n8 +7.4 ≈
  GPU n32 +7.7로 width-transfer 검증된 기법 — slope는 폭에 둔감.)
- **두 측정 모두 u64가 R2에 이미 매우 깊이 확산** → per-round slope ≈ **2× u32**(~15~17). 원인:
  16레인이라 broadcast t가 2배 워드로 퍼져 라운드당 활성워드·weight가 ~2배.

## acc-충돌 외삽 (256-bit digest, birthday 2¹²⁸)

acc-충돌 비용 = 1/best-DP(R_b) (§yttrium-round-count). 목표: 256-bit digest 충돌저항 = 2¹²⁸ →
best-DP(R_b) ≤ 2⁻¹²⁸. GPU R2 앵커(2⁻²¹·⁵) + slope s≈16 (보수 15~17):

| 변형 | R_b | w(R_b)=21.5+s·(R_b−2) | 충돌저항 | 256-bit digest 충족 |
|---|---|---|---|---|
| **yttrium-large-(10,14,24)** | 10 | 2⁻¹³⁹~¹⁵⁵ | ~**139~155-bit** | **✓ full 128-bit (마진)** |
| yttrium-large-(8,12,24) | 8 | 2⁻¹¹¹~¹²³ | ~111~123-bit | ≈full (약간 미달) |
| yttrium-large-(4,6,12) | 4 | 2⁻⁵²~⁵⁶ | ~52~56-bit | keyed 전용 |
| yttrium-large-(4,6,8) | 4 | 동 | 동 | keyed/비적대 |

⟹ **현 변형 패밀리가 yttrium-large에 충분**: (10,14,24)가 full 128-bit 충돌저항(256-bit digest
상한). (8,12,24)는 ~111-123-bit(거의 full). 별도 고라운드 large 변형 불요.

## 더 긴 출력(384/512-bit)

가변출력은 truncation이라 충돌저항은 acc-충돌(R_b)이 상한 — (10,14,24)서 ~150-bit. 따라서 384/512-bit
**출력**의 충돌저항도 ~150-bit(출력폭이 아니라 R_b가 결정). SHA3-512(256-bit 충돌)와 동급을 원하면
R_b↑ 필요(별도). preimage(2nd)는 합성 R_b+R_c가 담당, 출력폭만큼 확장.

## 한계 (정직)

1. **slope는 하한+외삽**: GPU·reduced 둘 다 R2서 floor. slope≥16.6(reduced R1→R2)은 *floored R2까지의
   하한*이며 deep-round 정밀 slope는 미측정. 단 하한 16.6만으로도 (10,14,24)=full 128-bit 성립(견고).
2. **width-transfer 가정**: reduced n=16 slope ≈ n=64 slope (u32서 검증됐으나 u64 재확인은 N↑ GPU 필요).
3. 절대 trail 경계 아님(R5). acc-비용 모델 p⁻¹(§round-count caveat 동일).
4. R_c(2nd-preimage 합성)·R_mask는 u32 비례 이월(별도 u64 측정 미수행) — 보수적.

## 재현
```bash
cd milp
nvcc --std=c++14 -O3 -o yttrium_large_decay yttrium_large_decay.cu && ./yttrium_large_decay  # R2 앵커(R3+ floor)
python3 verify_large_slope.py    # reduced n=16 slope 하한
```
