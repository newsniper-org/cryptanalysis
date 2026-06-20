# Check primitivity of the n=32 alpha-mult with reduction constant 0x400007.
# poly p(x) = x^32 + (low bits from 0x400007). 0x400007 = bits set: let's decode.
red=0x400007
bits=[i for i in range(32) if (red>>i)&1]
print("red=0x400007 set bits:", bits, "-> p(x)=x^32 +", " + ".join(f"x^{b}" for b in sorted(bits,reverse=True)) if bits else "1")

def make_alpha(n,red):
    M=(1<<n)-1
    def a(v): return (((v<<1)&M)^(red if (v>>(n-1))&1 else 0))
    return a

n=32; a=make_alpha(n,red)
# multiplicative order: alpha must have order 2^32-1 to be primitive.
order_full = (1<<32)-1
# factor 2^32-1 = 3 * 5 * 17 * 257 * 65537
factors=[3,5,17,257,65537]
# alpha is primitive iff alpha^((2^32-1)/q) != 1 for all prime factors q.
def apow(x,e):
    # exponent by repeated squaring in GF(2^32): need multiply, but we only have *alpha (=*x).
    # Instead compute alpha^e applied to 1 via repeated multiply-by-x is O(e) -- too big.
    # Use matrix exponentiation of the 32x32 companion matrix over GF(2).
    pass

# Build alpha as 32x32 GF(2) matrix, matrix-power to test order.
def alpha_mat(n,red):
    cols=[]
    for k in range(n):
        x=1<<k; top=(x>>(n-1))&1
        y=((x<<1)&((1<<n)-1))^(red if top else 0)
        cols.append(y)
    return cols
def applym(cols,x,n):
    y=0
    for k in range(n):
        if (x>>k)&1: y^=cols[k]
    return y&((1<<n)-1)
def matmul(A,B,n):  # columns form
    return [applym(A,B[j],n) for j in range(n)]
def matpow(A,e,n):
    R=[1<<j for j in range(n)]; base=A
    while e:
        if e&1: R=matmul(base,R,n)
        base=matmul(base,base,n); e>>=1
    return R
def is_identity(M,n):
    return all(M[j]==(1<<j) for j in range(n))

A=alpha_mat(n,red)
M_full=matpow(A,order_full,n)
print("alpha^(2^32-1) == I :", is_identity(M_full,n))
prim=True
for q in factors:
    e=order_full//q
    Mq=matpow(A,e,n)
    isid=is_identity(Mq,n)
    print(f"  alpha^((2^32-1)/{q}) == I : {isid}  {'(NOT primitive if True)' if isid else ''}")
    if isid: prim=False
print("=> red=0x400007 PRIMITIVE at n=32:", prim and is_identity(M_full,n))

# XOR-orthomorphism at n=32 cannot be exhaustive (2^32). But alpha^k+id perm <=> (alpha^k+1) invertible matrix.
def add_id(M,n): return [M[j]^(1<<j) for j in range(n)]
def gf2_rank_cols(cols,n):
    basis=[]
    for v in cols:
        cur=v
        for b in basis: cur=min(cur,cur^b)
        if cur: basis.append(cur); basis.sort(reverse=True)
    return len(basis)
print("\nXOR-orthomorphism (alpha^k + id invertible) at n=32:")
for k in [1,2,3,4,5,6,7,8]:
    Ak=matpow(A,k,n)
    Mk=add_id(Ak,n)
    r=gf2_rank_cols(Mk,n)
    print(f"  k={k}: rank(alpha^k + I)={r}  XOR-ortho={r==32}")
