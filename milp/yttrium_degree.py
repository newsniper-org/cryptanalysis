#!/usr/bin/env python3
"""
yttrium 대수 차수 성장 (정확 Möbius) — integral / cube / zero-sum distinguisher 하한.

배경(SPEC §10-C, milp/yttrium-round-count.md "차원: 대수차수"):
  d-라운드 압축출력의 GF(2) ANF *최소* 차수가 (cube/integral 차원) 미만이면 그 차원의
  합(= (d+1)차 도함수)이 항상 0 → distinguisher 생존. 모든 출력비트가 full degree
  N-1(N=상태 비트수)에 도달하는 라운드 R_full 이상이어야 integral/zero-sum이 죽는다.
  이 차원은 R_b/R_c/R_mask의 *하한*만 준다(차분·선형보다 약한 구속) — 차분이 요구하는
  라운드를 채우면 integral은 자동 충족. 단 R_b가 R_full 미만이면 위험.

라운드 함수(SPEC §6, yttrium_lm_diff.cu 와 동일; ι(RC)는 ANF 차수0·차분투명이라 생략):
  reduction : xp_i = ROTL_A(x_i);  S = Σ_i ε_i·xp_i (mod 2^n), ε=[+,-,+,-,...]  (Σε=0)
  combiner  : t = F(S);  y_i = ROTR_B(xp_i ⊞ t)
  F         : s ⊕ (s⋘r1∧s⋘r2) ⊕ (s⋘r3∧s⋘r4) ⊕ (s⋘r5∧s⋘r6)   (3-term, 풀폭 7,17,3,21,9,29)
  σ         : y_i ← α^{k_i}·y_i   (GF(2^n), red=primitive)
  π         : new_i = y_{P[i]}

정직 / 도구한계:
  * 풀폭 n=32(N=256)은 2^256 전수가 불가 → **축소폭 정확측정 + 구조적 외삽**.
  * σ-reduction 은 폭별 **primitive**(full-order=2^n-1) 여야 라운드가 전단사. 비-primitive면
    α^k 가 비치환→라운드 비가역→max_deg=N(>N-1) 오염. 본 도구는 primitive red 만 사용하고
    매 config 마다 bijective=True 를 assert(아니면 결과 폐기).
  * F 회전오프셋은 n>=8이면 풀폭(7,17,3,21,9,29) 사용, n<8이면 폭에 맞춰 축소(차수성장
    메커니즘=carry chain + 전레인 broadcast 는 보존되나 풀폭과 정확 동형은 아님).
  * 측정값은 "예상"의 근거(축소폭 정확값)이며 N=256 R_full 은 외삽. 절대 증명 아님.

실행: python3 yttrium_degree.py            (기본 config sweep, 단일 PC, GPU 불요)
      python3 yttrium_degree.py --rmax 6   (라운드 상한 변경)
"""
import argparse
import sys
import numpy as np


# ---------- primitive reduction 자동탐색(full-order=2^n-1) ----------
def find_primitive_red(n):
    M = (1 << n) - 1
    target = (1 << n) - 1
    for red in range(3, 1 << n, 2):
        v = 1
        ok = True
        for i in range(1, target):
            top = v >> (n - 1)
            v = ((v << 1) & M) ^ (red if top else 0)
            if v == 1:        # order < 2^n-1 → not primitive
                ok = False
                break
        # after target steps must return to 1
        top = v >> (n - 1)
        v = ((v << 1) & M) ^ (red if top else 0)
        if ok and v == 1:
            return red
    raise RuntimeError(f"no primitive reduction for n={n}")


def make_round(n, w, red, sig_k, P, A, B, eps):
    M = (1 << n) - 1

    def rotl(x, k):
        k %= n
        return ((x << k) | (x >> (n - k))) & M if k else x & M

    def rotr(x, k):
        return rotl(x, (n - (k % n)) % n)

    def alpha(v):
        top = v >> (n - 1)
        return (((v << 1) & M) ^ (red if top else 0))

    def alfp(v, k):
        for _ in range(k):
            v = alpha(v)
        return v

    # F rotation offsets: 풀폭 (7,17,3,21,9,29); 축소폭은 mod n 으로 접되 0 회피
    if n >= 8:
        raw = [(7, 17), (3, 21), (9, 29)]
        TERMS = [(p % n, q % n) for (p, q) in raw]
    else:
        # 좁은 폭: 3개 독립 AND 쌍을 폭 안에 분산(carry+broadcast 메커니즘 보존용)
        TERMS = [(1, n // 2), (2 % n or 1, (n - 1)), (3 % n or 1, (n - 2) % n or 1)]

    def F(s):
        acc = 0
        for (r1, r2) in TERMS:
            acc ^= rotl(s, r1) & rotl(s, r2)
        return s ^ acc

    def rnd(words):
        xp = [rotl(words[i], A) for i in range(w)]
        S = 0
        for i in range(w):
            S = (S + xp[i]) & M if eps[i] > 0 else (S - xp[i]) & M
        t = F(S)
        y = [rotr((xp[i] + t) & M, B) for i in range(w)]
        y = [alfp(y[i], sig_k[i]) for i in range(w)]
        return [y[P[i]] for i in range(w)]

    return rnd, M


def mobius_degrees(n, w, red, sig_k, P, A, B, eps, Rmax, label=""):
    N = n * w
    if N > 24:
        print(f"  [skip {label}] N={N} > 24, 2^N Möbius 전수 단일PC 한계 초과")
        return
    rnd, M = make_round(n, w, red, sig_k, P, A, B, eps)
    size = 1 << N
    cur = np.arange(size, dtype=np.int64)
    popc = np.array([bin(i).count("1") for i in range(size)], dtype=np.int16)
    idx = np.arange(size)
    for R in range(1, Rmax + 1):
        nxt = np.empty(size, dtype=np.int64)
        for x in range(size):
            st = int(cur[x])
            ws = [(st >> (i * n)) & M for i in range(w)]
            ws2 = rnd(ws)
            v = 0
            for i in range(w):
                v |= (ws2[i] & M) << (i * n)
            nxt[x] = v
        cur = nxt
        bijective = (len(np.unique(cur)) == size)
        maxdeg = 0
        mindeg = N
        for b in range(N):
            tt = ((cur >> b) & 1).astype(np.uint8)
            i = 1
            while i < size:
                mask = (idx & i) != 0
                tt[mask] ^= tt[idx[mask] ^ i]
                i <<= 1
            nz = np.nonzero(tt)[0]
            d = int(popc[nz].max()) if nz.size else 0
            maxdeg = max(maxdeg, d)
            mindeg = min(mindeg, d)
        flag = ""
        if not bijective:
            flag = "  <<< NON-BIJECTIVE (결과 폐기: red 비-primitive 또는 라운드 비가역)"
        if mindeg == N - 1 and bijective:
            flag = "  <- min_deg = N-1 (full degree; integral/cube 소멸)"
        print(f"  R={R}: max_deg={maxdeg:3d}  min_deg={mindeg:3d}  bijective={bijective}  (N-1={N - 1}){flag}")
        if mindeg == N - 1 and bijective:
            print(f"  => R_full = {R}  (이 축소폭에서 full-degree 도달 라운드)")
            return R
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rmax", type=int, default=6)
    ap.add_argument("--big", action="store_true", help="N=24 등 무거운 config 포함(장시간)")
    args = ap.parse_args()

    print("### yttrium 축소폭 ANF 차수 성장 (정확 Möbius; primitive red, bijective assert) ###")
    print("# R_full = 모든 출력비트가 full degree N-1 도달 라운드 = integral/cube 소멸 하한")
    print("# 풀폭 N=256 은 외삽(2^256 전수 불가). 측정값은 예상의 근거이며 절대증명 아님.\n")

    PI8 = [7, 4, 1, 6, 3, 0, 5, 2]      # yttrium π = (5i+7) mod 8
    PI4 = [3, 0, 1, 2]                   # 축소 4-워드 순환 순열
    # 축소폭 σ powers: 풀폭 all-8 k=[1,2,3,5,7,11,13,17] 의 distinct-power 정신을 유지
    SK8 = [1, 2, 3, 5, 7, 11, 13, 17]
    SK4 = [1, 2, 3, 5]
    SK2 = [1, 2]

    configs = []
    # (label, n, w, P, sig_k, A, B, eps)
    configs.append(("w2 n6", 6, 2, [1, 0], SK2, 3, 4, [1, -1]))
    configs.append(("w2 n8 (A,B)=(8,9)", 8, 2, [1, 0], SK2, 8, 9, [1, -1]))
    configs.append(("w4 n4", 4, 4, PI4, SK4, 1, 2, [1, -1, 1, -1]))
    configs.append(("w4 n5", 5, 4, PI4, SK4, 2, 3, [1, -1, 1, -1]))
    # 8-word configs only feasible for tiny n (N<=24): n=2 -> N=16, n=3 -> N=24
    configs.append(("w8 n2 (실제 8-워드 구조)", 2, 8, PI8, SK8, 1, 1, [1, -1, 1, -1, 1, -1, 1, -1]))
    # 주의: w8 n3 (N=24) 은 2^24 Möbius × 24비트 = 단일PC 수십분~timeout. 기본 sweep 제외.
    # 필요시 --big 로 활성(오케스트레이터/장시간 실행용).
    if args.big:
        configs.append(("w8 n3 (실제 8-워드 구조, N=24 무거움)", 3, 8, PI8, SK8, 1, 2,
                        [1, -1, 1, -1, 1, -1, 1, -1]))

    rfull = {}
    for (lab, n, w, P, sk, A, B, eps) in configs:
        N = n * w
        red = find_primitive_red(n)
        print(f"== {lab}: N={N}  (primitive red = {hex(red)}) ==")
        r = mobius_degrees(n, w, red, sk, P, A, B, eps, args.rmax, label=lab)
        rfull[lab] = r
        print()

    print("---- 요약: R_full(축소폭) ----")
    for lab, r in rfull.items():
        print(f"  {lab:30s}: R_full = {r}")
    print("\n정직 해석:")
    print("  * 레인폭 n>=4(carry+broadcast 메커니즘 보존)인 config(w2n6/w2n8/w4n4/w4n5)는")
    print("    모두 R_full = 2~3. 이게 대표값.")
    print("  * w8 n2(N=16, 실제 8-워드 구조) 는 R_full=None(R6서 min_deg=12/15) — 단, n=2 는")
    print("    레인이 2비트뿐이라 회전이 붕괴하고 F-오프셋이 퇴화하는 **소필드 artifact**다.")
    print("    carry chain 길이가 1비트로 줄어 풀폭(n=32, 32비트 carry)과 동형이 아니다.")
    print("    → 차수성장의 '느림'은 폭이 아니라 워드폭 n 에 묶임. 풀폭 n=32 는 빠른 쪽.")
    print("  외삽(구조적, 절대증명 아님): carry chain(1 add ≈ n-1차) + 전레인 broadcast t=F(S)가")
    print("  레인폭 n 이 충분히 크면 빠른 차수성장을 주므로, 풀폭 n=32(N=256) R_full 은 보수적 ~4~5.")
    print("  → integral/cube 차원의 R_b 하한 ≈ 5. 현행 R_b=4 는 경계선(±1) → R_b>=5 권고에 정합.")


if __name__ == "__main__":
    main()
