#!/usr/bin/env python3
"""
R_b 차원 — acc-충돌의 Wagner k-tree(generalized birthday) 비용 모델.

acc-충돌(unkeyed leaf, T_max=8): 공격자가 8개 슬롯에 차분을 넣어
  ⊕_{j=0..7} P_b(block_j ⊕ mask_j) = ⊕_{j} P_b(block'_j ⊕ mask_j)
즉 ⊕_j [ P_b(in_j) ⊕ P_b(in_j ⊕ Δ_j) ] = 0  를 노린다(mask 공개라 in_j 자유 선택).

두 충돌 양식:
  (A) 정렬쌍(aligned-pair) — 짝수 슬롯에 같은 (Δ→∇) 특성을 강제해 두 슬롯 출력차가
      동일→XOR소거. 각 활성쌍은 best-DP^2 비용(독립). T_max=8 → 최대 4쌍.
  (B) 진짜 8-way Wagner — 각 슬롯 출력차 ∇_j 를 자유롭게 두고 8개의 ∇_j 가 XOR=0.
      ∇_j 분포가 균일(이상적)이면 비용 = generalized-birthday on 256-bit, 8 lists.

핵심: P_b 가 acc-충돌을 막으려면, 위 비용 둘 다 birthday bound 2^64(collision)를
넘겨야 한다. digest는 128-bit truncate라 collision 보안 목표 = 2^64(birthday).
실제로 acc(256-bit) 충돌이 곧 digest 충돌 충분조건이므로 acc-충돌이 2^64 미만이면 깨짐.
"""
import math

def wagner_ktree_cost(bits, k):
    """k-list generalized birthday(Wagner). k=2^a 일 때 최적 비용 ~ k * 2^{bits/(1+log2 k)}.
    각 리스트 크기 = 2^{bits/(1+log2 k)}. (Wagner 2002)."""
    a = math.log2(k)
    listlog = bits/(1+a)
    return listlog, k*(2**listlog)

if __name__=="__main__":
    print("=== Wagner 8-way generalized-birthday 기준선 (256-bit acc, 이상적 P_b) ===")
    for k in (2,4,8):
        ll, cost = wagner_ktree_cost(256, k)
        print(f"  k={k} lists: list-size 2^{ll:.1f}, total work ~2^{math.log2(cost):.1f}")
    print("  => 이상적 순열이면 8-way Wagner도 list-size 2^{:.1f} >> 2^64. acc 폭(256)이 마진.".format(wagner_ktree_cost(256,8)[0]))
    print()

    print("=== 차분-특성 기반 정렬쌍(aligned-pair) acc-충돌 비용 (R_b 의존) ===")
    print("    한 활성쌍 비용 ~ 1/best-DP^2 (양 슬롯 동일 Δ→∇ 강제). 4쌍 동시는 곱.")
    print("    best-DP(R_b) 후 단일슬롯 worst-δ DP 가정값으로 표 작성.\n")
    # 측정값(yttrium_lm_diff.cu / rb_acc_collision.py): R2서 floor(2^-23 겉보기, 실제 더 낮음 추정)
    # 보수적으로 best-DP(R) = noise floor 가 아니라 trail-weight 외삽 사용.
    # 단일슬롯 weight 외삽: R1~weight2.6, R2 floor. 보수 가정: per-round +~11~13 (n=8 slope로 보정).
    scenarios = {
        "측정 floor (관측상한, R>=2: <=2^-23, 보수)": {2:23,3:23,4:23},
        "trail 외삽 (per-round +12, R1=2.6)": {1:2.6,2:14.6,3:26.6,4:38.6},
        "보수 trail 외삽 (per-round +8)": {1:2.6,2:10.6,3:18.6,4:26.6},
    }
    for name, dpw in scenarios.items():
        print(f"  [{name}]")
        for R in sorted(dpw):
            w = dpw[R]
            pair = 2*w           # aligned pair: best-DP^2
            # acc-충돌 최소: 1쌍이면 2 슬롯 활성; 그 1쌍을 만족시키는 작업 = 2^pair
            print(f"    R_b={R}: single-slot DP 2^-{w:.1f} -> aligned-pair acc-충돌 작업 ~2^{pair:.1f}"
                  + ("  >=2^128 (preimage)" if pair>=128 else ("  >=2^64 (collision OK)" if pair>=64 else "  < 2^64 (부족)")))
        print()
    print("주의: aligned-pair 는 단일 특성 비용. 실제 공격자는 다중 특성 클러스터/Wagner 혼합 가능.")
    print("digest 충돌 목표 2^64 (128-bit truncate, birthday). R_b 단독이 acc-충돌 방어.")
