#!/usr/bin/env python3
"""
The bit23-pair differences give EXACT prob-1 ΔS=0 (because ROTL8 sends word-bit23 -> S-bit31,
and flipping S's MSB changes it by ±2^31, and any even-with-eps-cancel combination sums to 0
mod 2^32, carry-free since MSB has no carry-out). This is a TRUE additive prob-1 inactive
class the GF(2) model mislabels as 'observed'.

Define the exact additive-inactive (round-1) class explicitly:
  A difference D (XOR) is round-1 prob-1 inactive iff ΔS = sum_i eps_i*(ROTL8(x_i^D_i)-ROTL8(x_i))
  is 0 for ALL x. Since ROTL8 is a bit-permutation, ROTL8(x^d) - ROTL8(x) as an INTEGER depends
  on x EXCEPT for the MSB position of S: bit31 of S only gets a +/-2^31 (no carry out, no carry in
  dependence on x for the top bit's CONTRIBUTION modulo 2^32)...
  Empirically: D supported only on word-bit23 of any lanes, with signed multiplicity
  m = sum over active lanes of eps_lane, gives ΔS = m * 2^31 mod 2^32 = 0 iff m even.
  (m even => m*2^31 ≡ 0 mod 2^32.) This is EXACT and x-independent. Verified prob=1.

So the exact additive round-1 inactive subspace (within single-bit-position families) =
  { D on word-bit23 across an EVEN-eps-weighted set of lanes }.
dim: 8 lanes, free choice of subset with even signed count. eps alternates +,-,+,-...
Signed count parity = (#+active) - (#-active) mod 2 = (#active) mod 2. So 'even m' = even #active.
=> 2^7 = 128 such differences (even-size subsets of 8 lanes), dim 7 over GF(2) (the bit23 slice).

NOW: propagate this exact-inactive class through the round. When Δt=0, round acts as linear A.
We track how long a bit23-even difference stays inside the exact additive-inactive set under A
(prob-1 each round requires the *propagated* difference to ALSO be exact-additive-inactive AND
to keep ΔS=0 at every round). Build the additive-inactive predicate exactly and iterate.
"""
import numpy as np
from ssm_eigen import build_A_dense
from ssm_unobservable import STATE, N_BITS, W, rotl, rotr, alpha_pow, P_PI, SIG_K, ROT_A, ROT_B, MASK

EPS = [1, -1, 1, -1, 1, -1, 1, -1]


def words_of_vec(v):
    return [int(sum(int(v[i * N_BITS + b]) << b for b in range(N_BITS))) for i in range(W)]


def vec_of_words(ws):
    v = np.zeros(STATE, dtype=np.uint8)
    for i in range(W):
        for b in range(N_BITS):
            if (ws[i] >> b) & 1:
                v[i * N_BITS + b] = 1
    return v


def exact_additive_inactive(D, trials=80000, seed=0):
    """Return measured P(ΔS=0) over random x; prob-1 within sampling => exact-inactive."""
    rng = np.random.default_rng(seed)
    x = rng.integers(0, 1 << N_BITS, size=(trials, W), dtype=np.uint64)
    Dn = np.array(D, dtype=np.uint64)
    xd = x ^ Dn

    def rsum(arr):
        s = np.zeros(arr.shape[0], dtype=np.uint64)
        for i in range(W):
            col = arr[:, i] & np.uint64(MASK)
            t = ((col << np.uint64(ROT_A)) | (col >> np.uint64(N_BITS - ROT_A))) & np.uint64(MASK)
            if EPS[i] > 0:
                s = (s + t) & np.uint64(MASK)
            else:
                s = (s - t) & np.uint64(MASK)
        return s
    return float(np.mean(rsum(x) == rsum(xd)))


def main():
    A = build_A_dense()
    print("=== exact additive prob-1 inactive class: bit23 even-support ===")
    # generator: bit23 on lanes {0,2} (both +, m=+2 even)
    base = [0] * W
    base[0] = 1 << 23
    base[2] = 1 << 23
    p = exact_additive_inactive(base)
    print(f"seed diff bit23@{{0,2}}: round-1 P(ΔS=0)={p:.5f}")

    # Now propagate through A (the dt=0 linear backbone) and at EACH step test exact-inactivity.
    # prob-1 multi-round inactive requires the difference at every round to be exact-additive-inactive.
    print("\nPropagating bit23@{0,2} through backbone A; per-round exact P(ΔS=0):")
    D = base[:]
    v = vec_of_words(D)
    surviving = True
    for r in range(1, 13):
        p = exact_additive_inactive(D, trials=120000, seed=r)
        msb_pattern = all((D[i] == 0) or (D[i] == (1 << 23)) or bin(D[i]).count("1") <= 2 for i in range(W))
        wt = sum(bin(D[i]).count("1") for i in range(W))
        print(f"  round {r}: P(ΔS=0)={p:.5f}  total-HW={wt}  {'(still prob-1 inactive)' if p>0.999 else '(ACTIVATES F -> trail breaks here)'}")
        if p <= 0.999:
            surviving = False
            break
        # advance difference by linear backbone A (valid only while inactive)
        v = (A @ v) % 2
        D = words_of_vec(v)
    print()
    if surviving:
        print(">>> UNBOUNDED prob-1 inactive trail found (would be a full break).")
    else:
        print(">>> prob-1 inactive trail dies after the rounds shown (bounded).")

    # Also: enumerate the full round-1 exact-inactive subspace dimension (bit23 even-support)
    print("\n=== round-1 exact-additive-inactive subspace (full enumeration over bit23 slice) ===")
    import itertools
    cnt = 0
    examples = []
    for r in range(1, 9):
        for combo in itertools.combinations(range(8), r):
            D = [0] * W
            for c in combo:
                D[c] = 1 << 23
            # signed multiplicity
            m = sum(EPS[c] for c in combo)
            if m % 2 == 0:  # predicted exact-inactive (m*2^31 = 0 mod 2^32)
                cnt += 1
                if len(examples) < 3:
                    examples.append(combo)
    print(f"predicted exact-inactive bit23 combos (even signed mult): {cnt} (=2^{np.log2(cnt):.0f})")
    # verify a couple
    for combo in examples:
        D = [0] * W
        for c in combo:
            D[c] = 1 << 23
        p = exact_additive_inactive(D, trials=60000)
        print(f"  verify lanes {combo}: P(ΔS=0)={p:.4f}")
    # cross-check an ODD combo (should NOT be inactive)
    D = [0] * W
    D[0] = 1 << 23
    p = exact_additive_inactive(D, trials=60000)
    print(f"  odd combo lanes (0,): P(ΔS=0)={p:.5f}  (expected NOT prob-1)")


if __name__ == "__main__":
    main()
