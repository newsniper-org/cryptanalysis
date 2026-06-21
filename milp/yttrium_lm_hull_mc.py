#!/usr/bin/env python3
"""
yttrium-LM linear hull — Monte-Carlo signed-correlation on REAL-WIDTH reduced cipher.

Exact matrix-power (yttrium_lm_hull.py) is limited to ~12-bit states. To see whether
the HULL (signed sum over trails) at the real width (w=8) with the real σ behaves like
the tiny-state extrapolation, we estimate corr(a·x XOR b·F^R(x)) directly by sampling.

This DOES capture the full hull (the empirical correlation = exact signed sum over all
trails, by definition). We pick mask pairs motivated by the structure:
  - Single-MSB masks on lanes (MSB is the prob-1 / linear pass-through point of add).
  - The "zero-sum" reduction kills broadcast-t parity for balanced masks => candidate
    high-correlation linear approx through the combiner.
We measure |corr| vs R for the BEST mask pair we can find via a greedy mask search,
and report the empirical floor (sampling noise = 1/sqrt(Nsamp)).

n is the word width (default 8 => 64-bit state, real ratio). GPU not used; pure numpy
on uint8/uint64. Honesty: this is SAMPLED (empirical) correlation; floor = stat noise.
Best-mask search is heuristic (not exhaustive over 2^64 masks).
"""
import numpy as np

N_WORD = 8           # word width in bits (8 => byte lanes; state = 8*8 = 64 bits)
W = 8
RED = 0x1D           # primitive-ish poly for n=8 (x^8+x^4+x^3+x^2+1)
A_ROT, B_ROT = 8 % N_WORD, 9 % N_WORD   # rotations reduced mod n
EPS = np.array([1, -1, 1, -1, 1, -1, 1, -1], dtype=np.int64)
PI = np.array([7, 4, 1, 6, 3, 0, 5, 2])
SIGMA_K = [1, 2, 3, 5, 7, 11, 13, 17]
MASKW = (1 << N_WORD) - 1


def rotl_vec(x, k):
    k %= N_WORD
    if k == 0:
        return x
    return ((x << k) | (x >> (N_WORD - k))) & MASKW


def rotr_vec(x, k):
    return rotl_vec(x, (N_WORD - (k % N_WORD)) % N_WORD)


# precompute alpha^k tables (8-bit)
def make_alpha_table(k):
    tab = np.arange(1 << N_WORD, dtype=np.uint64)

    def alpha(v):
        top = (v >> (N_WORD - 1)) & 1
        return ((v << 1) & MASKW) ^ (RED * top)
    for _ in range(k):
        tab = np.array([alpha(int(v)) for v in tab], dtype=np.uint64)
    return tab


ALPHA_TABS = [make_alpha_table(k) for k in SIGMA_K]


def F_vec(s):
    return (s
            ^ (rotl_vec(s, 7 % N_WORD) & rotl_vec(s, 17 % N_WORD))
            ^ (rotl_vec(s, 3 % N_WORD) & rotl_vec(s, 21 % N_WORD))
            ^ (rotl_vec(s, 9 % N_WORD) & rotl_vec(s, 29 % N_WORD))) & MASKW


def round_vec(state):
    # state: (W, Nsamp) uint64 array of word values
    xp = np.stack([rotl_vec(state[i], A_ROT) for i in range(W)])
    S = np.zeros_like(xp[0])
    for i in range(W):
        if EPS[i] > 0:
            S = (S + xp[i]) & MASKW
        else:
            S = (S - xp[i]) & MASKW
    t = F_vec(S)
    y = [rotr_vec((xp[i] + t) & MASKW, B_ROT) for i in range(W)]
    for i in range(W):
        y[i] = ALPHA_TABS[i][y[i].astype(np.int64)]
    out = [y[PI[i]] for i in range(W)]
    return np.stack(out)


def parity_bits(vals_word_array, mask_words):
    # vals_word_array: (W, Nsamp); mask_words: list/array length W of n-bit masks
    acc = np.zeros(vals_word_array.shape[1], dtype=np.uint64)
    for i in range(W):
        acc ^= (vals_word_array[i] & np.uint64(mask_words[i]))
    # parity of acc over its bits
    p = np.zeros_like(acc)
    a = acc.copy()
    while a.any():
        p ^= (a & 1)
        a >>= 1
    return (p & 1).astype(np.int64)


def corr(in_mask, out_mask, R, Nsamp, rng):
    x = rng.integers(0, 1 << N_WORD, size=(W, Nsamp), dtype=np.uint64)
    y = x.copy()
    for _ in range(R):
        y = round_vec(y)
    pin = parity_bits(x, in_mask)
    pout = parity_bits(y, out_mask)
    s = 1 - 2 * (pin ^ pout)
    return s.mean()


def main():
    rng = np.random.default_rng(12345)
    Nsamp = 1 << 22   # ~4M samples => stat noise ~ 2^-11
    print(f"yttrium-LM hull MC: word n={N_WORD}, W={W} (state {N_WORD*W} bit), "
          f"Nsamp=2^{int(np.log2(Nsamp))} (noise ~2^{0.5*np.log2(1/Nsamp):.1f})")
    # candidate masks
    MSB = 1 << (N_WORD - 1)
    cands = {
        "single MSB lane0": ([MSB, 0, 0, 0, 0, 0, 0, 0], [MSB, 0, 0, 0, 0, 0, 0, 0]),
        "MSB all 8 lanes":  ([MSB] * 8, [MSB] * 8),
        "MSB plus-lanes":   ([MSB, 0, MSB, 0, MSB, 0, MSB, 0], [MSB, 0, MSB, 0, MSB, 0, MSB, 0]),
        "lsb lane0":        ([1, 0, 0, 0, 0, 0, 0, 0], [1, 0, 0, 0, 0, 0, 0, 0]),
        "full lane0":       ([MASKW, 0, 0, 0, 0, 0, 0, 0], [MASKW, 0, 0, 0, 0, 0, 0, 0]),
    }
    for name, (im, om) in cands.items():
        print(f"\n  [{name}] in={im[:2]}... out={om[:2]}...")
        for R in (1, 2, 3, 4):
            c = corr(im, om, R, Nsamp, rng)
            lg = np.log2(abs(c)) if c != 0 else -99
            print(f"    R={R}: corr = {c:+.6f}  |corr| = 2^{lg:.2f}")

    # greedy 1-round-mask propagation hunt for best multi-round corr:
    print("\n  [greedy MSB-aligned search over output rotation/lane at R=2,3]")
    best = {}
    for R in (2, 3):
        bestc = 0
        bestpair = None
        # try input = single MSB on each lane, output = single bit on each lane/pos
        for li in range(W):
            im = [0] * W
            im[li] = MSB
            for lo in range(W):
                for po in range(N_WORD):
                    om = [0] * W
                    om[lo] = 1 << po
                    c = corr(im, om, R, 1 << 20, rng)
                    if abs(c) > abs(bestc):
                        bestc = c
                        bestpair = (li, lo, po)
        lg = np.log2(abs(bestc)) if bestc != 0 else -99
        print(f"    R={R}: best single-bit-mask corr = {bestc:+.5f} = 2^{lg:.2f}  "
              f"(in lane {bestpair[0]} MSB -> out lane {bestpair[1]} bit {bestpair[2]})")
        best[R] = bestc


if __name__ == "__main__":
    main()
