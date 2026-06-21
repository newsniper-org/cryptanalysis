#!/usr/bin/env python3
"""Fast real-width best-mask hull search: run rounds ONCE, then evaluate many masks.
Reuses round from yttrium_lm_hull_mc but batches mask evaluation (no per-mask re-run)."""
import numpy as np
N_WORD = 8
W = 8
RED = 0x1D
A_ROT, B_ROT = 8 % N_WORD, 9 % N_WORD
EPS = [1, -1, 1, -1, 1, -1, 1, -1]
PI = [7, 4, 1, 6, 3, 0, 5, 2]
SIGMA_K = [1, 2, 3, 5, 7, 11, 13, 17]
MASKW = (1 << N_WORD) - 1


def rotl(x, k):
    k %= N_WORD
    return x if k == 0 else ((x << k) | (x >> (N_WORD - k))) & MASKW


def rotr(x, k):
    return rotl(x, (N_WORD - (k % N_WORD)) % N_WORD)


def make_alpha_table(k):
    tab = list(range(1 << N_WORD))

    def alpha(v):
        top = (v >> (N_WORD - 1)) & 1
        return ((v << 1) & MASKW) ^ (RED if top else 0)
    for _ in range(k):
        tab = [alpha(v) for v in tab]
    return np.array(tab, dtype=np.int64)


ALPHA = [make_alpha_table(k) for k in SIGMA_K]


def Fv(s):
    return (s ^ (rotl(s, 7 % N_WORD) & rotl(s, 17 % N_WORD))
            ^ (rotl(s, 3 % N_WORD) & rotl(s, 21 % N_WORD))
            ^ (rotl(s, 9 % N_WORD) & rotl(s, 29 % N_WORD))) & MASKW


def rnd(state):  # state list of W int-arrays
    xp = [rotl(state[i], A_ROT) for i in range(W)]
    S = np.zeros_like(xp[0])
    for i in range(W):
        S = (S + xp[i]) & MASKW if EPS[i] > 0 else (S - xp[i]) & MASKW
    t = Fv(S)
    y = [rotr((xp[i] + t) & MASKW, B_ROT) for i in range(W)]
    for i in range(W):
        y[i] = ALPHA[i][y[i]]
    return [y[PI[i]] for i in range(W)]


def par_word(arr):  # parity of each bit-position-isolated? no: parity of full word value
    p = np.zeros_like(arr)
    a = arr.copy()
    for _ in range(N_WORD):
        p ^= (a & 1)
        a >>= 1
    return p & 1


def main():
    rng = np.random.default_rng(7)
    Ns = 1 << 23  # 8M samples, noise ~2^-11.5
    print(f"fast hull MC2: n={N_WORD} W={W} state {N_WORD*W}bit Ns=2^{int(np.log2(Ns))} noise~2^{0.5*np.log2(1/Ns):.1f}")
    x = [rng.integers(0, 1 << N_WORD, size=Ns, dtype=np.int64) for _ in range(W)]
    # input parity per lane (single-lane full-word masks as basis); also per-bit
    for R in (2, 3, 4):
        y = [xi.copy() for xi in x]
        for _ in range(R):
            y = rnd(y)
        # Evaluate all single-bit input masks (lane,bit) -> all single-bit output masks (lane,bit).
        # Precompute per (lane,bit) the parity bit vector for input and output.
        in_bits = []  # (li, pi, vec)
        out_bits = []
        for li in range(W):
            for pi in range(N_WORD):
                in_bits.append((li, pi, (x[li] >> pi) & 1))
                out_bits.append((li, pi, (y[li] >> pi) & 1))
        best = 0.0
        bp = None
        # to keep it O(#in * #out * Ns) manageable: #in=#out=64 -> 4096 * 8M = 34G ops; too big.
        # Instead: for each input bit, correlate against ALL output bits at once via matrix.
        OB = np.array([ob[2] for ob in out_bits], dtype=np.int8)  # (64, Ns)
        for (li, pi, iv) in in_bits:
            # corr with each output bit: mean( 1-2*(iv xor ob) ) = 1 - 2*mean(iv xor ob)
            x_xor = OB ^ iv.astype(np.int8)  # (64, Ns)
            m = 1.0 - 2.0 * x_xor.mean(axis=1)  # (64,)
            j = int(np.argmax(np.abs(m)))
            if abs(m[j]) > abs(best):
                best = m[j]
                bp = (li, pi, out_bits[j][0], out_bits[j][1])
        lg = np.log2(abs(best)) if best else -99
        print(f"  R={R}: best single-bit linear corr = {best:+.6f} = 2^{lg:.2f}  "
              f"(in lane{bp[0]}b{bp[1]} -> out lane{bp[2]}b{bp[3]})  [noise~2^{0.5*np.log2(1/Ns):.1f}]")


if __name__ == "__main__":
    main()
