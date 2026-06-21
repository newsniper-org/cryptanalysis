#!/usr/bin/env python3
"""Verify the z3 'algebraic collision' SAT results are GENUINE collisions (distinct inputs,
equal 4-word truncated output), and confirm they are just expected DoF collisions (4 known
words << 8-word input => 2^128 fiber, trivially non-empty), NOT a structural shortcut.
Extract a concrete colliding pair from z3 at R=4 and verify with the bit-exact model."""
import sys
from z3 import (BitVec, BitVecVal, RotateLeft, RotateRight, Solver, sat, LShR, Or)
from ymodel import permute as ref_permute, rc as ref_rc, SIG_K, P_PI, ROT_A, ROT_B, EPS_PLUS, RED

W = 8


def alpha_z3(v):
    top = LShR(v, 31)
    return (v << 1) ^ ((BitVecVal(0, 32) - top) & BitVecVal(RED, 32))


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


def main():
    R = 3
    a = [BitVec(f"a{i}", 32) for i in range(W)]
    b = [BitVec(f"b{i}", 32) for i in range(W)]
    oa = permute_z3(a, R)
    ob = permute_z3(b, R)
    s = Solver()
    s.set("timeout", 120000)
    for i in range(4):
        s.add(oa[i] == ob[i])
    s.add(Or(*[a[i] != b[i] for i in range(W)]))
    print(f"solving R={R} algebraic collision ...", flush=True)
    if s.check() != sat:
        print("no model"); return
    m = s.model()
    av = [m[a[i]].as_long() if m[a[i]] is not None else 0 for i in range(W)]
    bv = [m[b[i]].as_long() if m[b[i]] is not None else 0 for i in range(W)]
    oa_r = ref_permute(av, R)
    ob_r = ref_permute(bv, R)
    print("input a :", [hex(x) for x in av])
    print("input b :", [hex(x) for x in bv])
    print("a != b  :", av != bv)
    print("out a[:4]:", [hex(x) for x in oa_r[:4]])
    print("out b[:4]:", [hex(x) for x in ob_r[:4]])
    print("4-word truncated collision (model-verified):", oa_r[:4] == ob_r[:4])
    print("full 8-word equal? (should be FALSE -- DoF collision, not full):", oa_r == ob_r)
    print("\nInterpretation: a 4-word(128-bit) truncated collision of a 256-bit bijection is")
    print("EXPECTED (2^128 fiber); z3 finds one for free at low R. NOT a structural shortcut.")
    print("It does NOT produce a FULL-state collision (impossible: permute is a bijection).")


if __name__ == "__main__":
    main()
