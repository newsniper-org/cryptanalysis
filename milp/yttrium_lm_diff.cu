/* yttrium-LM (권고안) best-DP — 영합 reduction + 결합기 G + σ. R=2/3/4.
 *
 * 권고 라운드 (G·F·π·RC 고정; 설계 = 영합 ε + all-8 σ):
 *   reduction: xp_i = ROTL_A(w_i);  S = Σ_i ε_i·xp_i (mod 2^32), ε=[+,-,+,-,+,-,+,-]
 *   combiner : t = F(S);  w_i = ROTR_B(xp_i ⊞ t)        (A,B)=(8,9)
 *   σ        : w_i ← α^{k_i}·w_i  (GF(2^32), red 0x400007); k_i=0 이면 항등(=비활성 레인)
 *   π        : new_i = w_{PPI[i]}
 *
 * 본 파일은 **σ-커버리지 비교**를 직접 수행한다(권고 근거의 결정적 시험):
 *   all-8 σ  k=[1,2,3,5,7,11,13,17]   (권고)
 *   even-4   k=[1,0,2,0,3,0,5,0]      (lanes 0,2,4,6)
 *   sig{0,4} k=[1,0,0,0,3,0,0,0]      (현행 ypsilenti식)
 *   empty    k=[0,..]                 (framing only, ablation)
 * 두 정확-LA 척도(prob-1 MSB R*=2, GF(2)-선형 R*≈8~9)는 σ 커버리지를 변별 못 함 —
 * 변별은 오직 이 best-DP(특히 영합 같은부호 MSB-쌍 truncated 차분)에서 나온다.
 *
 * arx_gpu_refine.cu 양식(gen/fold/run/rmax/bestdp, NB_LOG=24, N=2^30 floor~2^-25) 그대로.
 * 빌드: nvcc --std=c++14 -O3 -o yttrium_lm_diff yttrium_lm_diff.cu
 * 정직: best-DP는 δ-부분집합 탐색의 경험적 상한(증명 아님), 절대 trail 경계 아님.
 */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <math.h>
#define NB_LOG 24
#define NBUCKET (1u<<NB_LOG)
#define RED 0x400007u
__device__ __constant__ int PPI[8]={7,4,1,6,3,0,5,2};
__device__ __constant__ int TERMS[6]={7,17, 3,21, 9,29};
__device__ __constant__ int EPS[8]={1,-1,1,-1,1,-1,1,-1};        /* zero-sum signed reduction */
__device__ __constant__ int SIGK[8];                            /* σ powers per lane (host-set; 0=identity) */
__device__ inline uint32_t rotl(uint32_t x,int k){k&=31;return k?(x<<k)|(x>>(32-k)):x;}
__device__ inline uint32_t rotr(uint32_t x,int k){return rotl(x,(32-(k&31))&31);}
__device__ inline uint32_t alf(uint32_t y){uint32_t m=0u-(y>>31);return (y<<1)^(m&RED);}
__device__ inline uint32_t alfp(uint32_t y,int p){for(int i=0;i<p;i++)y=alf(y);return y;}
__device__ inline void gen(uint64_t seed,uint32_t*w){
  for(int i=0;i<4;i++){seed+=0x9E3779B97F4A7C15ULL;uint64_t z=seed;
    z=(z^(z>>30))*0xBF58476D1CE4E5B9ULL;z=(z^(z>>27))*0x94D049BB133111EBULL;z^=z>>31;
    w[2*i]=(uint32_t)z;w[2*i+1]=(uint32_t)(z>>32);}}
__device__ inline void perm(uint32_t*w,int R,int A,int B){
  for(int r=0;r<R;r++){
    /* (1) per-lane ROTL_A + signed zero-sum reduction */
    uint32_t xp[8]; for(int i=0;i<8;i++) xp[i]=rotl(w[i],A);
    uint32_t S=0; for(int i=0;i<8;i++) S += (EPS[i]>0)? xp[i] : (0u-xp[i]);
    /* (2) F(S), combiner broadcast */
    uint32_t acc=0; for(int k=0;k<3;k++) acc^=rotl(S,TERMS[2*k])&rotl(S,TERMS[2*k+1]);
    uint32_t t=S^acc;
    for(int i=0;i<8;i++) w[i]=rotr(xp[i]+t,B);
    /* (3) σ per-lane α^{k_i} (k_i=0 → 항등) */
    for(int i=0;i<8;i++) w[i]=alfp(w[i],SIGK[i]);
    /* (4) π */
    uint32_t nw[8];for(int i=0;i<8;i++)nw[i]=w[PPI[i]];for(int i=0;i<8;i++)w[i]=nw[i];}}
__device__ inline uint32_t fold(const uint32_t*d){uint32_t f=0;for(int i=0;i<8;i++)f^=rotl(d[i],i*4);return f;}
__global__ void run(uint64_t N,int R,int A,int B,const uint32_t*delta,uint32_t*hist){
  uint64_t tid=blockIdx.x*(uint64_t)blockDim.x+threadIdx.x,str=gridDim.x*(uint64_t)blockDim.x;
  for(uint64_t s=tid;s<N;s+=str){uint32_t x[8],y[8];gen(s,x);for(int i=0;i<8;i++)y[i]=x[i]^delta[i];
    perm(x,R,A,B);perm(y,R,A,B);uint32_t d[8];for(int i=0;i<8;i++)d[i]=x[i]^y[i];
    atomicAdd(&hist[fold(d)&(NBUCKET-1)],1u);}}
__global__ void rmax(const uint32_t*hist,uint32_t*out){
  uint32_t tid=blockIdx.x*blockDim.x+threadIdx.x,str=gridDim.x*blockDim.x,m=0;
  for(uint32_t i=tid;i<NBUCKET;i+=str) if(hist[i]>m)m=hist[i];
  atomicMax(out,m);}
static uint32_t *d_delta,*d_hist,*d_max;
double bestdp(uint64_t N,int R,int A,int B,const uint32_t*delta){
  cudaMemcpy(d_delta,delta,8*4,cudaMemcpyHostToDevice);cudaMemset(d_hist,0,NBUCKET*4);
  run<<<4096,256>>>(N,R,A,B,d_delta,d_hist);
  cudaMemset(d_max,0,4); rmax<<<256,256>>>(d_hist,d_max); cudaDeviceSynchronize();
  uint32_t mx=0; cudaMemcpy(&mx,d_max,4,cudaMemcpyDeviceToHost);
  return (double)mx/(double)N;}
static uint32_t D[400][8]; static int nd=0;
void build_deltas(){
  int pos[8]={0,4,8,15,20,24,28,31};
  for(int wd=0;wd<8;wd++)for(int pi=0;pi<8;pi++){for(int i=0;i<8;i++)D[nd][i]=0;D[nd][wd]=1u<<pos[pi];nd++;} /*64 single-bit*/
  for(int p1=0;p1<32;p1+=8)for(int p2=p1+8;p2<32;p2+=8){for(int i=0;i<8;i++)D[nd][i]=0;D[nd][0]=(1u<<p1)|(1u<<p2);nd++;} /*2-bit word0*/
  int plus[4]={0,2,4,6},minus[4]={1,3,5,7};
  /* MSB-쌍: 영합 같은부호 레인쌍, ROTR_8(MSB)=bit23 입력차분 (부분 σ 잔존 후보) */
  for(int a=0;a<4;a++)for(int b=a+1;b<4;b++){for(int i=0;i<8;i++)D[nd][i]=0;D[nd][plus[a]]=0x00800000u;D[nd][plus[b]]=0x00800000u;nd++;}
  for(int a=0;a<4;a++)for(int b=a+1;b<4;b++){for(int i=0;i<8;i++)D[nd][i]=0;D[nd][minus[a]]=0x00800000u;D[nd][minus[b]]=0x00800000u;nd++;}
  /* 직접 MSB-쌍(출력레벨 후보) */
  for(int a=0;a<4;a++)for(int b=a+1;b<4;b++){for(int i=0;i<8;i++)D[nd][i]=0;D[nd][plus[a]]=1u<<31;D[nd][plus[b]]=1u<<31;nd++;}
}
void run_at(uint64_t N,int A,int B,double*b2,double*b3,double*b4){
  *b2=*b3=*b4=0;
  for(int di=0;di<nd;di++){double d=bestdp(N,2,A,B,D[di]);if(d>*b2)*b2=d;}
  for(int di=0;di<nd;di++){double d=bestdp(N,3,A,B,D[di]);if(d>*b3)*b3=d;}
  for(int di=0;di<nd;di++){double d=bestdp(N,4,A,B,D[di]);if(d>*b4)*b4=d;}
}
int main(){
  cudaMalloc(&d_delta,8*4);cudaMalloc(&d_hist,NBUCKET*4);cudaMalloc(&d_max,4);
  const uint64_t N=1ULL<<30;  /* floor ~2^-25 */
  build_deltas();
  struct Mode{const char*name;int sig[8];};
  Mode modes[4]={
    {"all-8   k=1,2,3,5,7,11,13,17", {1,2,3,5,7,11,13,17}},
    {"even-4  {0,2,4,6}           ", {1,0,2,0,3,0,5,0}},
    {"sig{0,4} (ypsilenti식)      ", {1,0,0,0,3,0,0,0}},
    {"empty   (framing only)      ", {0,0,0,0,0,0,0,0}},
  };
  printf("(yttrium-LM) best-DP σ-커버리지 비교: N=2^30(floor~2^-25), δ=%d (단일비트+2bit+MSB영합쌍).\n",nd);
  printf("결정적 시험: 영합 같은부호 MSB-쌍이 부분 σ에서 생존/all-8서 붕괴하는가.\n\n");
  printf("== @ (α,β)=(8,9) σ-커버리지별 worst-δ best-DP ==\n");
  for(int m=0;m<4;m++){
    cudaMemcpyToSymbol(SIGK,modes[m].sig,sizeof(int)*8);
    double b2,b3,b4; run_at(N,8,9,&b2,&b3,&b4);
    printf("  %s : R2=2^-%-6.1f R3=2^-%-6.1f R4=2^-%-6.1f%s\n",modes[m].name,
           -log2(b2),-log2(b3),-log2(b4),(m==0)?"  <- 권고":"");
    fflush(stdout);
  }
  /* 권고(all-8) (α,β) sweep */
  cudaMemcpyToSymbol(SIGK,modes[0].sig,sizeof(int)*8);
  printf("\n== all-8 σ, (α,β) sweep ==\n");
  int cand[][2]={{8,9},{8,3},{9,10}};
  for(int c=0;c<3;c++){int A=cand[c][0],B=cand[c][1];double b2,b3,b4;run_at(N,A,B,&b2,&b3,&b4);
    printf("  (%2d,%2d)  R2=2^-%-6.1f R3=2^-%-6.1f R4=2^-%-6.1f%s\n",A,B,-log2(b2),-log2(b3),-log2(b4),
           (A==8&&B==9)?"   <- 설계":"");fflush(stdout);}
  cudaFree(d_delta);cudaFree(d_hist);cudaFree(d_max);
  return 0;
}
