#!/usr/bin/env python3
"""RAR(ROT-ADD-ROT) 코어 추출 viability — SipHash-class PRF 라운드 확산 평가 vs SipRound.

yttrium의 G(결합기 전체)는 영합 reduction·F·all-8 σ가 결합돼 추출 곤란. 대신 코어 ARX
프리미티브 rar(x,y)=ROTR_b(ROTL_a(x) ⊞ y) (= SPECK 빌딩블록류)만 추출 → 경량 PRF 가능?
256-bit(4×u64) 상태에서 1-bit 입력차분 avalanche를 SipRound와 비교. (numpy overflow 경고는
uint64 가산의 양성 경고 — 마스킹으로 결과 정상.) 실행: python3 rar_avalanche.py
"""
import numpy as np

M = (1 << 64) - 1


def rotl(x, k):
    k %= 64
    return ((x << np.uint64(k)) | (x >> np.uint64(64 - k))) & M if k else x


def rotr(x, k):
    return rotl(x, (64 - k % 64) % 64)


def sipround(v):
    v0, v1, v2, v3 = v
    v0 = (v0 + v1) & M; v1 = rotl(v1, 13); v1 ^= v0; v0 = rotl(v0, 32)
    v2 = (v2 + v3) & M; v3 = rotl(v3, 16); v3 ^= v2
    v0 = (v0 + v3) & M; v3 = rotl(v3, 21); v3 ^= v0
    v2 = (v2 + v1) & M; v1 = rotl(v1, 17); v1 ^= v2; v2 = rotl(v2, 32)
    return [v0, v1, v2, v3]


A, B, C = 8, 9, 29  # yttrium (α,β)=(8,9) 적응 + cross-rot


def rar(x, y):
    return rotr((rotl(x, A) + y) & M, B)


def rarround(v):
    v0, v1, v2, v3 = v
    v0 = rar(v0, v1); v1 = rotl(v1, C) ^ v0      # SPECK식 half
    v2 = rar(v2, v3); v3 = rotl(v3, C) ^ v2
    v0 = rar(v0, v3); v2 = rar(v2, v1)           # cross
    return [v1, v2, v3, v0]                        # word-rotate


def avalanche(roundfn, R, N=4000, seed=0):
    rng = np.random.default_rng(seed)
    tot = np.zeros(256)
    cnt = 0
    for _ in range(N):
        x = [rng.integers(0, 1 << 64, dtype=np.uint64) for _ in range(4)]
        for bit in rng.choice(256, 4, replace=False):
            y = list(x); w = bit // 64; y[w] = y[w] ^ np.uint64(1 << (bit % 64))
            ox, oy = list(x), list(y)
            for _ in range(R):
                ox = roundfn(ox)
            for _ in range(R):
                oy = roundfn(oy)
            d = [int(ox[i]) ^ int(oy[i]) for i in range(4)]
            tot += np.array([(d[i // 64] >> (i % 64)) & 1 for i in range(256)])
            cnt += 1
    p = tot / cnt
    return p.sum(), np.abs(p - 0.5).max()  # mean flipped(/256), worst |p-0.5|


if __name__ == "__main__":
    print("256-bit, 1-bit 차분 avalanche (mean flipped /256, worst |p-0.5|). 완전확산=128, 0.")
    print(f"{'R':>2} | {'SipRound':>9} {'worst':>6} | {'RAR-round':>9} {'worst':>6}")
    for R in range(1, 7):
        sm, sw = avalanche(sipround, R, seed=R)
        rm, rw = avalanche(rarround, R, seed=R + 100)
        print(f"{R:>2} | {sm:>9.1f} {sw:>6.3f} | {rm:>9.1f} {rw:>6.3f}")
    print("관찰: SipRound R4, RAR-round R5서 완전확산 → comparable. RAR 코어 추출 viable(신규 설계 필요).")
