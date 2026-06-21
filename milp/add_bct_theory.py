#!/usr/bin/env python3
"""
Exact add-BCT / FBCT structure (n small, exhaustive) + how σ=α^k breaks switch access.

(1) For the broadcast combiner v_i = xp_i ⊞ t, the per-lane switch is a modular-add
    boomerang. Compute the FULL add-BCT table over XOR diffs and count prob-1 cells.
    Known theory (Boura-Canteaut FBCT): modular add has many BCT entries =max because
    the add boomerang switch subtracts the shared carry-perturbation symmetrically.

(2) σ = α^k (GF(2^n), red). It is GF(2)-LINEAR. A switch diff δ that is prob-1 for the
    NEXT round's add (e.g. δ=MSB) must, after passing σ^-1=α^-k backward, ARRIVE at the
    PREVIOUS round's add output as α^-k(δ). We tabulate: starting from a clean add-BCT-1
    diff δ at one round, what diff α^-k(δ) lands on the adjacent add — and whether THAT
    is still a prob-1 add-BCT diff. If α^-k smears a single MSB into a multi-bit pattern
    that has add-BCT << 1, the switch cannot chain for free => boomerang collapses.

Exhaustive at n=8 (red 0x1D). GPU not needed.
"""
import math

n = 8
M = (1 << n) - 1
RED = 0x1D


def alpha(v):
    top = (v >> (n - 1)) & 1
    return (((v << 1) & M) ^ (top * RED)) & M


def alpha_inv(v):
    if v & 1:
        return ((v ^ RED) >> 1) | (1 << (n - 1))
    return v >> 1


def alfp(v, k):
    for _ in range(k):
        v = alpha(v)
    return v


def alfp_inv(v, k):
    for _ in range(k):
        v = alpha_inv(v)
    return v


def add_bct(dx, dz):
    """per-lane add boomerang return rate over (x,t), t fixed across faces (dy=0)."""
    cnt = 0
    for x in range(1 << n):
        for t in range(1 << n):
            v1 = (x + t) & M
            v2 = ((x ^ dx) + t) & M
            x3 = ((v1 ^ dz) - t) & M
            x4 = ((v2 ^ dz) - t) & M
            if (x3 ^ x4) == dx:
                cnt += 1
    return cnt / (1 << (2 * n))


def hw(x):
    return bin(x).count("1")


if __name__ == "__main__":
    print("### add-BCT prob-1 census (dy=0, broadcast combiner), n=8 ###")
    # count prob-1 cells per dx (sample dz over all 256? heavy: 256*256*65536). Do dx few.
    for dx in [0x80, 0x40, 0x01, 0x02, 0x81, 0xC0, 0xFF]:
        ones = 0
        examples = []
        for dz in range(1 << n):
            r = add_bct(dx, dz)
            if abs(r - 1.0) < 1e-12:
                ones += 1
                if len(examples) < 6:
                    examples.append(dz)
        print(f"  dx=0x{dx:02X}: #{{dz: BCT=1}} = {ones}/256   e.g. {['0x%02X' % e for e in examples]}")

    print("\n### σ=α^k maps a clean MSB switch diff to what lands on adjacent add ###")
    print("# A switch diff δ that is add-BCT-1 must survive σ^-1 to reach the prev add.")
    print("# We show α^-k(MSB) and its add-BCT against the SAME column, per σ power.")
    for k in [1, 2, 3, 5, 7, 11, 13, 17]:
        dpre = alfp_inv(0x80, k)          # what MSB at round-output maps to before σ
        # the adjacent add sees dpre; is dpre a prob-1 add-BCT diff (with dz=dpre)?
        r_self = add_bct(dpre, dpre)
        r_msb = add_bct(dpre, 0x80)
        print(f"  k={k:2d}: α^-k(0x80)=0x{dpre:02X} (hw={hw(dpre)})  "
              f"add-BCT(δ,δ)=2^-{(-math.log2(r_self)) if r_self>0 else float('inf'):.2f}  "
              f"add-BCT(δ,MSB)=2^-{(-math.log2(r_msb)) if r_msb>0 else float('inf'):.2f}")
