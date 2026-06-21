#!/usr/bin/env python3
"""
Realistic algebraic frontier: TRUNCATED preimage (only 4 of 8 output words known = the
128-bit yttrium digest CV). Plus a HARDER variant: fix input to a specific structure
(e.g. require half the input words to be zero) to force a genuine search rather than
trivial propagation. Measures the reduced-round algebraic attack frontier honestly.

Also: 2-block ZERO-SUM / collision-style query -- find two distinct inputs with the SAME
truncated output after R rounds (algebraic collision via z3), to probe whether the
zero-sum reduction gives an algebraic shortcut to the acc-collision that sets R_b.
"""
import time
import sys
from z3 import (BitVec, BitVecVal, RotateLeft, RotateRight, Solver, sat, unsat, LShR, Distinct)
from ymodel import permute as ref_permute, rc as ref_rc, SIG_K, P_PI, ROT_A, ROT_B, EPS_PLUS, RED

W = 8


def alpha_z3(v):
    top = LShR(v, 31)
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
        S = S + xp[i] if EPS_PLUS[i] else S - xp[i]
    t = F_z3(S)
    y = [RotateRight(xp[i] + t, ROT_B) for i in range(W)]
    y = [alpha_pow_z3(y[i], SIG_K[i]) for i in range(W)]
    return [y[P_PI[i]] for i in range(W)]


def permute_z3(state, rounds):
    st = list(state)
    for r in range(rounds):
        st = round_z3(st, r)
    return st


def truncated_preimage(R, fix_input_zero_words=0, timeout_s=120):
    """Find x s.t. first 4 output words of permute(x,R) match a target digest.
    Optionally force `fix_input_zero_words` input words to 0 (constrains => real search)."""
    target_in = [0x243F6A88 ^ (0x9E3779B9 * i & 0xffffffff) for i in range(W)]
    tout = ref_permute(target_in, R)
    digest = tout[:4]

    xin = [BitVec(f"x{i}", 32) for i in range(W)]
    s = Solver()
    s.set("timeout", timeout_s * 1000)
    out = permute_z3(xin, R)
    for i in range(4):
        s.add(out[i] == BitVecVal(digest[i], 32))
    for i in range(fix_input_zero_words):
        s.add(xin[W - 1 - i] == BitVecVal(0, 32))
    t0 = time.time()
    res = s.check()
    dt = time.time() - t0
    return str(res), dt


def algebraic_collision(R, timeout_s=120):
    """Find x != x' with same 4-word truncated output after R rounds (algebraic collision)."""
    a = [BitVec(f"a{i}", 32) for i in range(W)]
    b = [BitVec(f"b{i}", 32) for i in range(W)]
    oa = permute_z3(a, R)
    ob = permute_z3(b, R)
    s = Solver()
    s.set("timeout", timeout_s * 1000)
    for i in range(4):
        s.add(oa[i] == ob[i])
    s.add(Distinct(*[a[i] for i in range(W)] + [b[i] for i in range(W)]) == False)  # placeholder
    # require a != b as full vectors:
    from z3 import Or
    s.add(Or(*[a[i] != b[i] for i in range(W)]))
    t0 = time.time()
    res = s.check()
    dt = time.time() - t0
    return str(res), dt


if __name__ == "__main__":
    print("### TRUNCATED (4-word/128-bit) preimage frontier ###")
    print("# many preimages exist => z3 must search the 2^128-image fiber (real difficulty)\n")
    for R in range(1, 9):
        res, dt = truncated_preimage(R, fix_input_zero_words=0, timeout_s=120)
        flag = "  <-- TIMEOUT (frontier)" if res == "unknown" else ""
        print(f"  R={R}: truncated preimage status={res:8s} time={dt:7.2f}s{flag}", flush=True)
        if res == "unknown":
            break

    print("\n### constrained preimage: force last 4 input words = 0 (forces genuine search) ###")
    for R in range(1, 9):
        res, dt = truncated_preimage(R, fix_input_zero_words=4, timeout_s=120)
        flag = "  <-- TIMEOUT (frontier)" if res == "unknown" else ""
        print(f"  R={R}: constrained status={res:8s} time={dt:7.2f}s{flag}", flush=True)
        if res == "unknown":
            break

    print("\n### algebraic collision (4-word truncated) ###")
    for R in range(1, 7):
        res, dt = algebraic_collision(R, timeout_s=120)
        flag = "  <-- TIMEOUT (frontier)" if res == "unknown" else ""
        print(f"  R={R}: collision status={res:8s} time={dt:7.2f}s{flag}", flush=True)
        if res == "unknown":
            break
