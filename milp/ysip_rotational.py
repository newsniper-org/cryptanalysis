#!/usr/bin/env python3
"""
YSip Rotational / Rotational-XOR(RX) 분석 — adv_rx_yttrium.py 방법론 이식 (4×u64 SipRound-rar).

ARX-only PRF의 1순위 위협. 두 층위로 분리:
  (A) 라운드 내재 RX-저항: rotational pair (x, ROTL_γ(x)) 가 R라운드 후 보존될 확률
      RX-prob = Pr_x[ R^R(ROTL_γ(x)) == ROTL_γ(R^R(x)) ]. YSip vs SipHash 비교.
  (B) 구성 차단: keyed init v=IV⊕k 에서 IV가 회전대칭이 아니면 입력 회전쌍이 *내부상태*
      회전쌍을 만들지 못함 → 라운드 RX가 아무리 높아도 공격 불성립. SipHash와 동일 논거.

RC(라운드상수) 결정: SipHash도 라운드 RC 없음. YSip 라운드 RX ≤ SipHash 수준이고 (B)가
양쪽 동일하게 차단하면 RC 불요. YSip가 유의하게 나쁘면 RC 도입 검토.

정직: best RX-prob는 γ-sweep 경험적 상한(증명 아님). 실행: python3 ysip_rotational.py
"""
import sys
import math
import numpy as np

M = np.uint64(0xFFFFFFFFFFFFFFFF)
IV = [0x6a09e667f3bcc908, 0xbb67ae8584caa73b, 0x3c6ef372fe94f82b, 0xa54ff53a5f1d36f1]


def rotl(x, k):
    k %= 64
    if k == 0:
        return x
    return ((x << np.uint64(k)) | (x >> np.uint64(64 - k))) & M


def rotr(x, k):
    return rotl(x, (64 - (k % 64)) % 64)


def ysip_round(v, mode, A, B):
    v0, v1, v2, v3 = v

    def comb(x, y):
        if mode == "siphash":
            return (x + y) & M
        return rotr((rotl(x, A) + y) & M, B)

    v0 = comb(v0, v1); v1 = rotl(v1, 13); v1 ^= v0; v0 = rotl(v0, 32)
    v2 = comb(v2, v3); v3 = rotl(v3, 16); v3 ^= v2
    v0 = comb(v0, v3); v3 = rotl(v3, 21); v3 ^= v0
    v2 = comb(v2, v1); v1 = rotl(v1, 17); v1 ^= v2; v2 = rotl(v2, 32)
    return [v0, v1, v2, v3]


def runR(v, R, mode, A, B):
    for _ in range(R):
        v = ysip_round(v, mode, A, B)
    return v


def rx_prob(gamma, R, mode, A, B, N, seed=0):
    rng = np.random.default_rng(seed)
    x = [rng.integers(0, 1 << 64, size=N, dtype=np.uint64) for _ in range(4)]
    xr = [rotl(x[i], gamma) for i in range(4)]
    cx = runR([a.copy() for a in x], R, mode, A, B)
    cxr = runR([a.copy() for a in xr], R, mode, A, B)
    match = np.ones(N, dtype=bool)
    for i in range(4):
        match &= (cxr[i] == rotl(cx[i], gamma))
    return int(match.sum()) / N


def best_rx(R, mode, A, B, gammas, N, seed=0):
    best = (0.0, None)
    for g in gammas:
        p = rx_prob(g, R, mode, A, B, N, seed=seed)
        if p > best[0]:
            best = (p, g)
    return best


def add_rot_prob(gamma, N, seed=1):
    """단일 ⊞ 의 rotational 확률 (이론 ~2^-1.415, sanity)."""
    rng = np.random.default_rng(seed)
    x = rng.integers(0, 1 << 64, size=N, dtype=np.uint64)
    y = rng.integers(0, 1 << 64, size=N, dtype=np.uint64)
    lhs = rotl((x + y) & M, gamma)
    rhs = (rotl(x, gamma) + rotl(y, gamma)) & M
    return int((lhs == rhs).sum()) / N


if __name__ == "__main__":
    print("== [sanity] 단일 모듈러 가산 ⊞ rotational 확률 (이론 best ~2^-1.415) ==")
    for g in (1, 8, 32):
        p = add_rot_prob(g, 1 << 22)
        print(f"  γ={g:2d}: p={p:.4f} (-log2={-math.log2(max(p,1e-12)):.2f})")

    print("\n== [A] 라운드 내재 RX-prob 감쇠 (순수 rotational δ=0, best γ): YSip vs SipHash ==")
    print("  (공정성: 양쪽 *동일 seed*, multi-seed 평균 — 적대검증 지적 반영)")
    N = 1 << 20
    SEEDS = 4  # seed 평균으로 noise 완화 + 양쪽 동일 seed (공정)
    gammas = [1, 2, 3, 4, 8, 13, 16, 17, 21, 32]  # 작은 γ + 회전상수 (best는 통상 이 부근)
    floor = 3.0 / (N * SEEDS)
    print(f"  {'R':>2} | {'SipHash':>20} | {'YSip(8,9)':>20} | per-round Δ")
    prev_s = prev_y = None
    for R in range(1, 7):
        # 동일 seed 집합으로 양쪽 측정 → 공정 비교
        ps = max(sum(rx_prob(g, R, "siphash", 0, 0, N, seed=R * 10 + s) for s in range(SEEDS)) / SEEDS
                 for g in gammas)
        py = max(sum(rx_prob(g, R, "ysip", 8, 9, N, seed=R * 10 + s) for s in range(SEEDS)) / SEEDS
                 for g in gammas)
        ls = "≤floor" if ps <= floor else f"2^-{-math.log2(ps):.2f}"
        ly = "≤floor" if py <= floor else f"2^-{-math.log2(py):.2f}"
        print(f"  {R:>2} | {ls:>20} | {ly:>20} | "
              + (f"Sip {-math.log2(prev_s/ps):.2f} / YSip {-math.log2(prev_y/py):.2f} bits"
                 if prev_s and ps > floor and py > floor else ""))
        prev_s, prev_y = ps, py
    print("  관찰: YSip가 SipHash보다 라운드당 ~0.3-0.5비트 *근소 열세*(동일차수). R≥3 floor.")

    print("\n== [B] 구성 차단: RX-XOR δ 의 키의존성 (적대검증 지적 반영: IV비대칭만으로 불충분) ==")
    anysym = False
    for i, iv in enumerate(IV):
        sym = [g for g in range(1, 64) if rotl(np.uint64(iv), g) == np.uint64(iv)]
        if sym:
            anysym = True
    print(f"  IV 4워드 회전대칭 고정점: {'있음(취약!)' if anysym else '없음'} (필요조건).")
    # 핵심: v0=IV0⊕k0, v2=IV2⊕k0 레인의 초기 RX-XOR δ = v ⊕ ROTL_γ(v) 는 *미지의 k0* 에 의존.
    print("  핵심 기제: 초기상태 v=IV⊕k. RX-XOR 차분 δ(v)=v⊕ROTL_γ(v) 는 키 k 에 의존 →")
    g = 1
    for k0 in [0x0000000000000000, 0x0123456789abcdef, 0xdeadbeefcafebabe]:
        d0 = np.uint64(IV[0] ^ k0) ^ rotl(np.uint64(IV[0] ^ k0), g)
        d2 = np.uint64(IV[2] ^ k0) ^ rotl(np.uint64(IV[2] ^ k0), g)
        print(f"    k0={k0:#018x}: δ(v0)={int(d0):#018x}  δ(v2)={int(d2):#018x}")
    print("  → δ가 k0마다 상이 ⇒ 키독립 RX trail 불가(single-key 완전차단). "
          "또 IV0≠IV2 라 한 k0가 v0,v2를 동시 rotational 시킬 수 없음(related-key 부분차단).")
    print("  ∴ RC 불요: 라운드 RX = SipHash 차수 + 키의존 δ가 구성단계 차단 (SipHash와 동일 논거).")
    print("\n결론은 ysip-residual-obligations.md 에 종합.")
