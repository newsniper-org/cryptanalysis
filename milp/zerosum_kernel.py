#!/usr/bin/env python3
"""
NOVEL ANGLE on the ZERO-SUM reduction: exploit that eps=[+,-,+,-,+,-,+,-] has SUM 0
*over the integers / mod 2^32*, NOT just over GF(2). The GF(2) observability analysis
collapses eps signs (mod 2: -1==+1) and thus OVERESTIMATES activation. The real
additive reduction S = sum_i eps_i ROTL8(x_i) can have EXACT prob-1 inactive differences
that the GF(2) model declares 'observed'.

Concretely: framing is LINEAR (ROTL8 is GF(2)/Z-linear bijection on words). So
   S = sum_i eps_i ROTL8(x_i),   and for a difference D (XOR delta) the reduction is
   NOT linear (XOR vs +). BUT if we consider an ADDITIVE difference (x_i -> x_i + d_i mod 2^32)
   then S -> S + sum_i eps_i ROTL8(d_i) exactly (ROTL8 linear over Z/2^32? NO - rotation is
   NOT Z-linear). Rotation IS GF(2)-linear (bit permutation) but mixes the integer value.

KEY TEST 1 (additive-difference, zero-sum cancellation):
   Take additive differences. ROTL8 is a bit-permutation -> Z-linear only if it were a
   shift; rotation wraps MSBs to LSBs so it is NOT Z-linear. So additive structure breaks.
   => measure: pick d such that the +lanes and -lanes cancel. Simplest: d_i = same value v
   on a +lane and a -lane pair. Then eps cancellation needs ROTL8(v) - ROTL8(v) = 0 -> TRUE
   if the additive difference is EXACTLY equal on a (+,-) lane pair AND propagation is via +.
   But the round mixes via XOR injection (block^mask) and the difference we control is XOR.

KEY TEST 2 (the real one): XOR-difference D that is EQUAL on a (+lane, -lane) pair and
   zero elsewhere. Over the additive reduction:
     S(x+D-via-xor) - S(x) = eps_i*(ROTL8(x_i^d) - ROTL8(x_i)) + eps_j*(ROTL8(x_j^d)-ROTL8(x_j))
   with eps_i=+1, eps_j=-1, same d. Since x_i, x_j independent random, the two terms are
   i.i.d. but with OPPOSITE sign -> they do NOT cancel pointwise (different x_i,x_j).
   So prob(ΔS=0) is NOT 1 in general. BUT measure it: is it elevated vs generic?

KEY TEST 3 (the actually-prob-1 case): a difference confined to a SINGLE lane that, after
   ROTL8, lands entirely in bit positions where ... no. The only exact-cancel is D on a
   (+,-) pair with IDENTICAL x on those lanes -> not a free difference.

We measure prob(ΔS=0) for a sweep of structured XOR differences and compare to the GF(2)
prediction. If any structured class gives prob >> 2^-32 (e.g. low-weight near MSB), that's
a high-prob inactive class feeding a near-prob-1 linear/differential trail -> potentially
DEEPER than the generic best-DP. Honesty: we measure, we don't assume.
"""
import numpy as np

N = 32
W = 8
MASK = (1 << N) - 1
ROT_A = 8
EPS = [1, -1, 1, -1, 1, -1, 1, -1]


def rotl(x, k):
    k %= N
    return x & MASK if k == 0 else ((x << k) | (x >> (N - k))) & MASK


def Sval(words):
    s = 0
    for i in range(W):
        t = rotl(words[i], ROT_A)
        s = (s + t) & MASK if EPS[i] > 0 else (s - t) & MASK
    return s


def prob_inactive(D, trials=300000, seed=0):
    rng = np.random.default_rng(seed)
    xs = rng.integers(0, 1 << N, size=(trials, W), dtype=np.uint64)
    # vectorized
    Dn = np.array(D, dtype=np.uint64)
    cnt = 0
    # do in chunks for memory
    chunk = 50000
    total = 0
    hit = 0
    for st in range(0, trials, chunk):
        x = xs[st:st + chunk]
        xd = x ^ Dn
        # ROTL8 each column then signed-sum
        def rsum(arr):
            s = np.zeros(arr.shape[0], dtype=np.uint64)
            for i in range(W):
                col = arr[:, i] & np.uint64(MASK)
                t = ((col << np.uint64(ROT_A)) | (col >> np.uint64(N - ROT_A))) & np.uint64(MASK)
                if EPS[i] > 0:
                    s = (s + t) & np.uint64(MASK)
                else:
                    s = (s - t) & np.uint64(MASK)
            return s
        S = rsum(x)
        Sd = rsum(xd)
        hit += int(np.sum(S == Sd))
        total += x.shape[0]
    return hit / total


def main():
    print("=== Zero-sum reduction: additive prob(ΔS=0) for structured XOR differences ===")
    print("(generic random delta -> ~2^-32; we hunt elevated classes)\n")

    tests = []
    # (a) MSB on a single lane (carry-free top bit; flipping MSB == add/sub 2^31 -> ΔS=±2^31*?)
    msb = 1 << (N - 1)
    # after ROTL8, the MSB (bit31) goes to bit (31+8)%32 = bit7. So flipping word MSB flips bit7 of t.
    tests.append(("single-lane MSB (lane0)", [msb, 0, 0, 0, 0, 0, 0, 0]))
    # (b) MSB on a +/- pair lanes 0,1 (eps +,-)
    tests.append(("MSB on lanes 0&1 (+,-)", [msb, msb, 0, 0, 0, 0, 0, 0]))
    # (c) MSB on ALL 8 lanes (all equal) -> after ROTL8 all flip bit7; signed sum:
    #     sum eps_i * (flip of bit7) ; bit7 flip = +/-2^7 depending on carry. zero-sum eps?
    tests.append(("MSB on ALL 8 lanes", [msb] * 8))
    # (d) the bit that ROTL8 maps to MSB of S: to flip S's MSB (carry-free) we want bit
    #     that lands at S bit31 = word bit (31-8)=23. flipping word bit23 -> S bit31 (±2^31).
    b23 = 1 << 23
    tests.append(("bit23 single lane (->S MSB)", [b23, 0, 0, 0, 0, 0, 0, 0]))
    # (e) bit23 on +/- pair: ΔS = ±2^31 ∓2^31 = 0 IF carries align -> measure
    tests.append(("bit23 on lanes 0&1 (+,-)", [b23, b23, 0, 0, 0, 0, 0, 0]))
    # (f) bit23 on lanes 0&2 (both +) -> ΔS = ±2^31 ±2^31 = 0 mod 2^32 (2^31+2^31=2^32=0!)
    tests.append(("bit23 on lanes 0&2 (+,+) [2^31+2^31=0]", [b23, 0, b23, 0, 0, 0, 0, 0]))
    # (g) bit23 on all 8 lanes
    tests.append(("bit23 on ALL 8 lanes", [b23] * 8))
    # (h) low bit single lane
    tests.append(("bit0 single lane", [1, 0, 0, 0, 0, 0, 0, 0]))
    # (i) identical full-random-ish low delta on +/- pair
    tests.append(("0x1 on lanes 0&1 (+,-)", [1, 1, 0, 0, 0, 0, 0, 0]))

    for name, D in tests:
        p = prob_inactive(D, trials=400000, seed=hash(name) & 0xffff)
        import math
        w = -math.log2(p) if p > 0 else float("inf")
        flag = ""
        if p > 2 ** -20:
            flag = "  <-- ELEVATED"
        if p > 0.4:
            flag = "  <-- PROB-1-ish!!"
        print(f"  {name:42s}: P(ΔS=0)={p:.6g} = 2^-{w:.2f}{flag}")


if __name__ == "__main__":
    main()
