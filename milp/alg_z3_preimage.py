#!/usr/bin/env python3
"""
yttrium ALGEBRAIC attack (my angle): GF(2)/word-level polynomial system + z3 SAT for
reduced-round state-recovery / preimage. Spec-exact (F/sigma/eps/pi/RC).

Approach
--------
Model R rounds of permute() as a z3 BitVec(32)x8 system, exactly matching lib.rs round():
    state[r%8] ^= RC[r]
    xp_i = ROTL8(state_i)
    S = sum eps_i * xp_i (mod 2^32)        (zero-sum reduction; signed add/sub)
    t = F(S) = S ^ (S<<<7 & S<<<17) ^ (S<<<3 & S<<<21) ^ (S<<<9 & S<<<29)
    y_i = ROTR9(xp_i + t)                  (modular add)
    new_i = alpha^{k_i}(y_{P[i]})          (sigma is GF(2)-linear; expand as XOR of rotated/reduced bits)

State-recovery query: given output of permute(in, R) for a known input, can z3 recover
the input? (sanity: must be unique since permute is a bijection.) The cryptanalytic
question is *cost growth*: how many rounds R before z3 (CDCL-SAT) can no longer solve a
PREIMAGE in reasonable time. The modular-add carries + F's AND quadratic terms drive this.

We measure: solve time vs R for (a) full state preimage (8 known output words),
(b) the realistic hash setting (only 4 of 8 output words known = 128-bit digest truncation),
attacking the COMPRESSION permute (r_b rounds) as if to find a block mapping to a target
internal state.

Honest: z3 on a single PC; this gives the *reduced-round algebraic frontier*, not a full break.
"""
import time
import sys

try:
    from z3 import (BitVec, BitVecVal, RotateLeft, RotateRight, Solver, sat, unsat,
                    LShR, simplify, Extract, Concat)
except ImportError:
    print("z3 not available", file=sys.stderr)
    sys.exit(1)

from ymodel import (permute as ref_permute, rc as ref_rc, SIG_K, P_PI, ROT_A, ROT_B,
                    EPS_PLUS, RED)

W = 8
NL = 32


def alpha_z3(v):
    # alpha(y) = (y<<1) ^ (RED if msb(y) ) ; GF(2)-linear, expressed via select on msb bit
    top = LShR(v, 31)  # 0 or 1 in low bit
    # mask = 0 - top  (all ones if top==1)
    mask = BitVecVal(0, 32) - top
    return (v << 1) ^ (mask & BitVecVal(RED, 32))


def alpha_pow_z3(v, k):
    for _ in range(k):
        v = alpha_z3(v)
    return v


def F_z3(s):
    acc = s
    for (a, b) in [(7, 17), (3, 21), (9, 29)]:
        acc = acc ^ (RotateLeft(s, a) & RotateLeft(s, b))
    return acc


def round_z3(state, r):
    st = list(state)
    st[r % W] = st[r % W] ^ BitVecVal(ref_rc(r), 32)
    xp = [RotateLeft(st[i], ROT_A) for i in range(W)]
    S = BitVecVal(0, 32)
    for i in range(W):
        if EPS_PLUS[i]:
            S = S + xp[i]
        else:
            S = S - xp[i]
    t = F_z3(S)
    y = [RotateRight(xp[i] + t, ROT_B) for i in range(W)]
    y = [alpha_pow_z3(y[i], SIG_K[i]) for i in range(W)]
    return [y[P_PI[i]] for i in range(W)]


def permute_z3(state, rounds):
    st = list(state)
    for r in range(rounds):
        st = round_z3(st, r)
    return st


def solve_preimage(R, known_words=8, timeout_s=60, target_in=None):
    """Find x with permute(x,R) matching target (known_words of 8). Returns (status, secs, recovered)."""
    if target_in is None:
        target_in = [0x01234567 + 0x11111111 * i & 0xffffffff for i in range(W)]
    target_out = ref_permute(target_in, R)

    xin = [BitVec(f"x{i}", 32) for i in range(W)]
    out = permute_z3(xin, R)
    s = Solver()
    s.set("timeout", timeout_s * 1000)
    for i in range(known_words):
        s.add(out[i] == BitVecVal(target_out[i], 32))
    # forbid the trivial known answer to force a *search* (preimage difficulty proxy):
    # actually keep it; we want to test if z3 finds *a* preimage. For full 8 words it's unique.
    t0 = time.time()
    res = s.check()
    dt = time.time() - t0
    rec = None
    if res == sat:
        m = s.model()
        rec = [m[xin[i]].as_long() if m[xin[i]] is not None else None for i in range(W)]
        # verify
        if known_words == 8 and None not in rec:
            chk = ref_permute(rec, R)
            ok = all(chk[i] == target_out[i] for i in range(W))
        else:
            ok = True
    return (str(res), dt, rec, target_in, target_out)


if __name__ == "__main__":
    print("### yttrium algebraic preimage via z3 (reduced rounds) ###")
    print("# full-state (8 known words) preimage: unique => tests pure algebraic invertibility cost\n")
    for R in range(1, 9):
        status, dt, rec, tin, tout = solve_preimage(R, known_words=8, timeout_s=90)
        ok = (rec == tin) if (rec and None not in rec) else False
        print(f"  R={R}: 8-word preimage  status={status:6s}  time={dt:7.2f}s  recovered==input:{ok}")
        if dt > 80:
            print("  (hit timeout frontier)")
            break
