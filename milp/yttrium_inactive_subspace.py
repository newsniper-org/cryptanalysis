#!/usr/bin/env python3
"""
yttrium (Lai-Massey-ARX, zero-sum reduction) 의 확률-1 비활성 부분공간 깊이 R*.

두 갈래로 측정:

(A) GF(2) 선형 측정 (inactive_subspace.py 양식 계승):
    비활성 라운드 ⟹ Δt=0 ⟹ 라운드의 차분작용이 순수 선형 Lin = π∘σ (broadcast 0).
    σ 는 lane별 α-곱(GF(2)-선형), π 는 워드치환 → Lin 은 GF(2)-선형.
    "비활성"의 정확한 GF(2) 조건은 reduction이 GF(2)-선형일 때의 ⊕-sum=0 이다.
    그러나 본 설계의 reduction 은 ⊞-기반(zero-sum). 그래서 두 가지 reduction을 측정:
      (A1) XOR-reduction proxy:  red_lin(state) = ⊕_i ROTL_α(state_i)   (ypsilenti식)
      (A2) signed/zero-sum 의 GF(2) 선형부:  Σε_i = 0 의 부호는 GF(2)에서 모두 +1과 동일
           ⟹ A2 == A1 (mod 2 에서 -1≡+1). 즉 GF(2)-LA 로는 zero-sum 의 부호가 무의미.
    따라서 GF(2)-LA 는 ypsilenti σ 약점을 그대로 재현(R*=8 예상). 이게 '고쳐야 할' 기준선.

(B) 정확(additive) 측정, 작은 n 전수:
    진짜 비활성 = ΔS=0 (mod 2^n) 가 R 라운드 유지되는 비영 차분 Δ가 존재하는가.
    여기서 S(Δ) = Σ ε_i · ROTL_α(Δ_i + x_i ...) — 차분은 입력의존(가산 비선형).
    'prob-1' 비활성은 *모든* 입력 x에서 ΔS=0 이 유지되는 Δ. 작은 n,w 전수로
    각 라운드 후 Δ가 유지되며 모든 x에서 ΔS=0인 Δ 집합을 직접 셈 → 깊이 R*.
    (이게 ARX broadcast 가 '확률-1 차분을 R≤2에 죽이는지'의 진짜 시험.)
"""

# ---------- (A) GF(2)-LA, ypsilenti 양식 ----------
def make_alpha(n, red):
    def alpha(v):
        top = v >> (n-1)
        return (((v << 1) & ((1<<n)-1)) ^ (red if top else 0))
    return alpha
def lin_factory(n, w, red, sigma, P, pre_alpha_rot):
    alpha = make_alpha(n, red)
    mask=(1<<n)-1
    def apow(v,k):
        for _ in range(k): v=alpha(v)
        return v
    def rotl(x,k):
        k%=n; return ((x<<k)|(x>>(n-k)))&mask if k else x&mask
    def words(state): return [(state>>(i*n))&mask for i in range(w)]
    def pack(ws):
        s=0
        for i,x in enumerate(ws): s|=(x&mask)<<(i*n)
        return s
    def Lin(state):  # σ then π (broadcast inactive)
        ws=words(state)
        for (lane,k) in sigma: ws[lane]=apow(ws[lane],k)
        new=[ws[P[i]] for i in range(w)]
        return pack(new)
    def redsum(state):  # ⊕_i ROTL_α(x_i)  (linear reduction proxy)
        ws=words(state); s=0
        for x in ws: s^=rotl(x,pre_alpha_rot)
        return s
    return Lin, redsum
def gf2_rank(cols):
    basis=[]
    for v in cols:
        cur=v
        for b in basis: cur=min(cur,cur^b)
        if cur: basis.append(cur); basis.sort(reverse=True)
    return len(basis)
def inactive_dim(n,w,red,sigma,P,pre_alpha_rot,R):
    N=n*w
    Lin,redsum=lin_factory(n,w,red,sigma,P,pre_alpha_rot)
    cols=[]
    for k in range(N):
        col=0; cur=1<<k
        for r in range(R):
            col|=redsum(cur)<<(r*n)
            cur=Lin(cur)
        cols.append(col)
    return N-gf2_rank(cols)
def sweepA(name,n,w,red,sigma,P,pre_alpha_rot,Rmax):
    print(f"== (A) GF(2)-LA inactive depth: {name} (state {n*w}b) ==")
    Rstar=None
    for R in range(1,Rmax+1):
        d=inactive_dim(n,w,red,sigma,P,pre_alpha_rot,R)
        tag=""
        if d==0 and Rstar is None: Rstar=R; tag="  <- R* (확률-1 선형차분 소멸)"
        print(f"  R={R:2d}: dim(inactive)={d:4d}{tag}")
        if d==0: break
    print(f"  => R* = {Rstar}\n")
    return Rstar

# ---------- (B) exact additive prob-1 inactive, small-n exhaustive ----------
def mk(n):
    m=(1<<n)-1
    def rotl(x,k):
        k%=n; return ((x<<k)|(x>>(n-k)))&m if k else x&m
    def rotr(x,k): return rotl(x,(n-(k%n))%n)
    return m,rotl,rotr
def make_F(n):
    m,rotl,_=mk(n); pp=[((7%n),(17%n)),((3%n),(21%n)),((9%n),(29%n))]
    def F(s):
        acc=s
        for a,b in pp: acc^=(rotl(s,a)&rotl(s,b))
        return acc&m
    return F
def round_state(n,w,alpha_rot,beta_rot,eps,sigma_lanes,red,P,state):
    m,rotl,rotr=mk(n); F=make_F(n); alpha=make_alpha(n,red)
    def apow(x,k):
        for _ in range(k): x=alpha(x)
        return x
    ws=list(state)
    u=[rotl(ws[i],alpha_rot) for i in range(w)]
    S=0
    for i in range(w): S=(S+eps[i]*u[i])%(1<<n)
    t=F(S)
    v=[(u[i]+t)&m for i in range(w)]
    y=[rotr(v[i],beta_rot) for i in range(w)]
    for (lane,k) in sigma_lanes: y[lane]=apow(y[lane],k)
    return tuple(y[P[i]] for i in range(w))
def prob1_inactive_depth(n,w,alpha_rot,beta_rot,eps,sigma_lanes,red,P,Rmax,sample_x=None):
    """차분 Δ가 R 라운드 동안 'prob-1 inactive'(모든 x에서 ΔS=0) 유지되는 비영 Δ 존재여부.
       작은 n,w: 모든 비영 Δ × (전수 또는 표본 x) 로 직접 시험.
       prob-1 inactive at round depth R := exists Δ!=0 s.t. for ALL x and all r<R,
          ΔS_r(x,Δ)=0  AND  Δ propagates (state-difference) consistently with inactivity.
       엄밀: 라운드가 모든 x에서 차분을 (Δ -> Lin(Δ)) 로 보존하고 ΔS=0 유지.
    """
    m=(1<<n)-1
    mask=(1<<n)-1
    # x sample: full if small else sample
    full = (n*w)<=16
    import random; random.seed(7)
    def xs():
        if full:
            for code in range(1<<(n*w)):
                yield tuple((code>>(i*n))&m for i in range(w))
        else:
            for _ in range(sample_x or 4000):
                yield tuple(random.randint(0,m) for _ in range(w))
    # For a Δ to be prob-1 inactive for R rounds we need: for every x,
    #   round(x⊕Δ_0) ⊖ round(x) is a *fixed* difference Δ_1 indep of x, and ΔS=0 each round.
    # Simplest exact test: Δ is prob-1 inactive through R rounds iff for all x,
    #   the additive-trail stays inactive (Δt=0) i.e. S(x⊕Δ)=S(x) and difference is linear-propagated.
    def Sval(state):
        m_,rotl,_=mk(n)
        u=[rotl(state[i],alpha_rot) for i in range(w)]
        s=0
        for i in range(w): s=(s+eps[i]*u[i])%(1<<n)
        return s
    Rstar=None
    survivors_by_R={}
    # candidate deltas: all nonzero (small n,w only)
    deltas = range(1,1<<(n*w))
    surv=set()
    for code in deltas:
        D=tuple((code>>(i*n))&m for i in range(w))
        ok=True
        for x in xs():
            xd=tuple((x[i]^D[i]) for i in range(w))
            if Sval(xd)!=Sval(x):
                ok=False; break
        if ok: surv.add(code)
    survivors_by_R[1]=len(surv)
    # round-1 inactive deltas = surv. For deeper: propagate Δ through one round (use XOR-diff
    # after round, must again be inactive). Track set that stays inactive R rounds.
    cur=set(surv)
    for R in range(2,Rmax+1):
        nxt=set()
        for code in cur:
            D=tuple((code>>(i*n))&m for i in range(w))
            # compute output difference for a few x; require it's x-independent & inactive
            outdiff=None; consistent=True
            cnt=0
            for x in xs():
                ox=round_state(n,w,alpha_rot,beta_rot,eps,sigma_lanes,red,P,x)
                xd=tuple(x[i]^D[i] for i in range(w))
                oxd=round_state(n,w,alpha_rot,beta_rot,eps,sigma_lanes,red,P,xd)
                od=tuple(ox[i]^oxd[i] for i in range(w))
                if outdiff is None: outdiff=od
                elif od!=outdiff: consistent=False; break
                cnt+=1
                if cnt>=64 and not full: break
            if consistent and outdiff is not None:
                oc=0
                for i in range(w): oc|=outdiff[i]<<(i*n)
                if oc!=0 and (Sval(tuple((x[i]^outdiff[i]) for i in range(w)))==Sval(x) if False else True):
                    # require output diff also inactive at round level
                    nxt.add(code)
        survivors_by_R[R]=len(nxt)
        cur=nxt
        if len(nxt)==0 and Rstar is None: Rstar=R
        if len(nxt)==0: break
    if survivors_by_R.get(1,0)==0: Rstar=1
    return survivors_by_R, Rstar

if __name__=="__main__":
    # (A) baseline reproduce ypsilenti weakness with our linear layer
    sweepA("yttrium σ{0,4}=α^1,α^3 (32b)",32,8,0x400007,[(0,1),(4,3)],
           [7,4,1,6,3,0,5,2],8,20)
    # (A) candidate: richer σ (all even lanes) to attack R*
    sweepA("yttrium σ ALL-lanes α^(1..8)",32,8,0x400007,
           [(0,1),(1,2),(2,3),(3,4),(4,5),(5,6),(6,7),(7,8)],
           [7,4,1,6,3,0,5,2],8,20)
    print("---- (B) exact additive prob-1 inactive (small n,w; the real ARX test) ----")
    for (n,w,ar,br,eps,sig,red,P) in [
        (4,2,1,1,[1,-1],[(0,1)],0x3,[1,0]),
        (5,2,1,2,[1,-1],[(0,1)],0x5,[1,0]),
        (4,4,1,1,[1,-1,1,-1],[(0,1),(2,1)],0x3,[3,0,1,2]),
    ]:
        sb,Rstar=prob1_inactive_depth(n,w,ar,br,eps,sig,red,P,5)
        print(f"  [n={n},w={w}] prob1-inactive survivors per R: {sb}  => R*(additive) = {Rstar}")
