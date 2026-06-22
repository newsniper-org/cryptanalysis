#!/usr/bin/env python3
"""
YSip 차분 trail 탐색기 — SMT-LIB2(QF_BV 64bit) + z3. (arx_trail_z3.py 방법론 이식)

라운드(4×u64 SipRound 구조, ⊞ 위치를 rar로 치환):
  v0 = rar(v0,v1); v1=ROTL13(v1); v1^=v0; v0=ROTL32(v0);
  v2 = rar(v2,v3); v3=ROTL16(v3); v3^=v2;
  v0 = rar(v0,v3); v3=ROTL21(v3); v3^=v0;
  v2 = rar(v2,v1); v1=ROTL17(v1); v1^=v2; v2=ROTL32(v2);
  rar(x,y) = ROTR_B(ROTL_A(x) ⊞ y),  (A,B)=(8,9) 기본.

차분 모델(표준 Markov/per-op, XOR-차분):
  · ROTL/ROTR/XOR : GF(2)-선형 → 결정적(weight 0), 차분 비트만 재배치.
  · 모듈러 가산 c=a⊞b : Lipmaa–Moriai validity + weight = hw(((α⊕β)|(α⊕γ)) & (2^{n-1}-1)).
  최소 trail weight = K 증분탐색(첫 SAT). best-DP = 2^-minweight.

mode:
  ysip    — rar 결합기 (A,B)
  siphash — ⊞ 직접 (calibration: 같은 도구로 SipHash 측정 → 신뢰보정)

축소폭(--width): z3 64bit는 R≥3 timeout → n=16/32 에서 더 깊은 R 의 slope 측정.
회전상수는 round(rot·n/64) 로 **비례 스케일**(구조 보존). YSip·SipHash 양쪽에 동일 적용 →
*상대* 비교는 공정(절대수치는 축소판). (A,B)도 비례 스케일.

usage:
  python3 ysip_diff.py [ysip|siphash|both] [maxR] [A] [B] [width]
"""
import subprocess
import sys
import tempfile
import os

SIP_ROT64 = (13, 16, 21, 17)   # SipHash 회전상수 (마지막 swap은 64/2=32 고정)


def scale_rot(r64, n):
    """64bit 회전상수 r64 를 폭 n 으로 비례 스케일 (nonzero는 최소 1)."""
    r = round(r64 * n / 64) % n
    return r if r != 0 else 1


class SMT:
    def __init__(self, n):
        self.N = n
        self.ADDMASK = (1 << (n - 1)) - 1
        self.SIP = tuple(scale_rot(r, n) for r in SIP_ROT64)
        self.SWAP = n // 2
        self.L = ["(set-logic QF_BV)"]
        self.W = []
        self.n = 0

    def bv(self, x):
        return f"(_ bv{x % (1 << self.N)} {self.N})"

    def fresh(self, pfx="t"):
        self.n += 1
        v = f"{pfx}{self.n}"
        self.L.append(f"(declare-fun {v} () (_ BitVec {self.N}))")
        return v

    def bind(self, expr, pfx="t"):
        """expr를 신선 변수에 묶어 식 폭발 방지."""
        v = self.fresh(pfx)
        self.L.append(f"(assert (= {v} {expr}))")
        return v

    def assert_(self, e):
        self.L.append(f"(assert {e})")

    def rotl(self, e, k):
        k %= self.N
        if k == 0:
            return e
        return f"(bvor (bvshl {e} {self.bv(k)}) (bvlshr {e} {self.bv(self.N - k)}))"

    def rotr(self, e, k):
        return self.rotl(e, (self.N - k) % self.N)

    def xor(self, a, b):
        return f"(bvxor {a} {b})"

    def add_diff(self, a, b, pfx="g"):
        """차분 a,b 를 가산기에 통과 → 출력차분 g (fresh). validity + weight 부과."""
        g = self.fresh(pfx)
        a1 = f"(bvshl {a} {self.bv(1)})"
        b1 = f"(bvshl {b} {self.bv(1)})"
        g1 = f"(bvshl {g} {self.bv(1)})"
        # validity: eq(a<<1,b<<1,g<<1) & (a^b^g^(b<<1)) == 0
        eqv = f"(bvand (bvnot (bvxor {a1} {b1})) (bvnot (bvxor {a1} {g1})))"
        cond = f"(bvxor (bvxor (bvxor {a} {b}) {g}) {b1})"
        self.assert_(f"(= (bvand {eqv} {cond}) {self.bv(0)})")
        # weight = hw( ((a^b)|(a^g)) & ADDMASK )
        noneq = f"(bvand (bvor (bvxor {a} {b}) (bvxor {a} {g})) {self.bv(self.ADDMASK)})"
        self._popcount(noneq)
        return g

    def _popcount(self, expr):
        self.n += 1
        w = f"w{self.n}"
        self.L.append(f"(declare-fun {w} () (_ BitVec 16))")
        bits = " ".join(
            f"((_ zero_extend 15) ((_ extract {i} {i}) {expr}))" for i in range(self.N)
        )
        self.L.append(f"(assert (= {w} (bvadd {bits})))")
        self.W.append(w)


def rar_diff(s, vx, vy, A, B):
    """rar 차분: a=ROTL_A(Δx), b=Δy, g=add(a,b), out=ROTR_B(g). (A,B)는 폭 비례 스케일."""
    a = s.bind(s.rotl(vx, scale_rot(A, s.N)), "a")
    g = s.add_diff(a, vy)
    return s.bind(s.rotr(g, scale_rot(B, s.N)), "r")


def sip_round(s, v, mode, A, B):
    r1, r2, r3, r4 = s.SIP
    sw = s.SWAP
    v0, v1, v2, v3 = v

    def combine(x, y):
        if mode == "siphash":
            return s.add_diff(x, y)
        return rar_diff(s, x, y, A, B)

    v0 = combine(v0, v1)
    v1 = s.bind(s.rotl(v1, r1), "v1")
    v1 = s.bind(s.xor(v1, v0), "v1")
    v0 = s.bind(s.rotl(v0, sw), "v0")

    v2 = combine(v2, v3)
    v3 = s.bind(s.rotl(v3, r2), "v3")
    v3 = s.bind(s.xor(v3, v2), "v3")

    v0 = combine(v0, v3)
    v3 = s.bind(s.rotl(v3, r3), "v3")
    v3 = s.bind(s.xor(v3, v0), "v3")

    v2 = combine(v2, v1)
    v1 = s.bind(s.rotl(v1, r4), "v1")
    v1 = s.bind(s.xor(v1, v2), "v1")
    v2 = s.bind(s.rotl(v2, sw), "v2")
    return [v0, v1, v2, v3]


def build(rounds, mode, A, B, K, n):
    s = SMT(n)
    v = [s.fresh(f"dv{i}_") for i in range(4)]
    s.assert_("(or " + " ".join(f"(not (= {d} {s.bv(0)}))" for d in v) + ")")
    for _ in range(rounds):
        v = sip_round(s, v, mode, A, B)
    if s.W:
        tot = s.W[0]
        for w in s.W[1:]:
            tot = f"(bvadd {tot} {w})"
        s.assert_(f"(bvule {tot} (_ bv{K} 16))")
    s.L.append("(check-sat)")
    return "\n".join(s.L)


def run(smt, timeout):
    with tempfile.NamedTemporaryFile("w", suffix=".smt2", delete=False) as f:
        f.write(smt)
        p = f.name
    try:
        r = subprocess.run(
            ["z3", f"-T:{timeout}", p], capture_output=True, text=True, timeout=timeout + 15
        )
        out = (r.stdout or "").strip().splitlines()
        return out[0] if out else "unknown"
    except subprocess.TimeoutExpired:
        return "timeout"
    finally:
        os.unlink(p)


def min_weight(rounds, mode, A, B, n, Kmax=80, timeout=60):
    for K in range(0, Kmax + 1):
        res = run(build(rounds, mode, A, B, K, n), timeout)
        if res == "sat":
            return K, "exact"
        if res in ("timeout", "unknown"):
            return K, f"undet(>={K},z3={res})"
    return Kmax + 1, f">{Kmax}"


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "both"
    maxR = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    A = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    B = int(sys.argv[4]) if len(sys.argv) > 4 else 9
    width = int(sys.argv[5]) if len(sys.argv) > 5 else 64
    modes = ["siphash", "ysip"] if mode == "both" else [mode]
    print(f"min trail weight (=-log2 best-DP; 높을수록 강함). 'undet'=z3 한계 하한.")
    print(f"  width={width}, (A,B)=({A},{B})→스케일({scale_rot(A, width)},{scale_rot(B, width)}), "
          f"SipRot={tuple(scale_rot(r, width) for r in SIP_ROT64)}")
    print(f"{'mode':<10}" + "".join(f" R={r:<8}" for r in range(1, maxR + 1)))
    for m in modes:
        row = f"{m:<10}"
        for r in range(1, maxR + 1):
            k, note = min_weight(r, m, A, B, width)
            tag = f"{k}" if note == "exact" else f"{k}*"
            row += f" {tag:<10}"
        print(row, flush=True)
    print("(* = z3 timeout 하한; 실제 weight ≥ 표기값. 축소폭은 상대비교용.)")
