/* yttrium best-DP 라운드별 감쇠 R=1..7 (오케스트레이터 GPU 실행용).
 *
 * 목적(SPEC §10-C, milp/yttrium-round-count.md):
 *   라운드별 worst-δ best-DP w(R)=-log2(DP) 와 per-round slope Δw 를 측정해
 *   R_b(acc-충돌 ≤2^-64)·R_b+R_c 합성(digest 충돌/2nd-preimage)의 라운드수를
 *   외삽 정당화한다. yttrium_lm_diff.cu(R=2/3/4·σ커버리지 비교)를 R=1..7 로 확장.
 *
 * 라운드 함수(SPEC §6 = yttrium_lm_diff.cu 와 bit-동일; RC ι 는 차분투명이라 생략):
 *   xp_i = ROTL_A(w_i);  S = Σ_i ε_i·xp_i (mod 2^32), ε=[+,-,+,-,+,-,+,-]
 *   t = F(S) = S ⊕ (S⋘7∧S⋘17) ⊕ (S⋘3∧S⋘21) ⊕ (S⋘9∧S⋘29)
 *   w_i = ROTR_B(xp_i ⊞ t);  w_i ← α^{k_i}·w_i (GF(2^32) red 0x400007);  π=[7,4,1,6,3,0,5,2]
 *   설계 σ = all-8 k=[1,2,3,5,7,11,13,17] (distinct powers; 반복-power 는 가짜 prob-1 고정점
 *            artifact 를 만드므로 금지 — verify_n8_slope/decay 류 함정 회피).
 *
 * 측정값은 N=2^30 에서 floor~2^-25(worst-δ 최대화 시 겉보기 2^-23). R>=3 의 깊은 weight 는
 * floor 에 막혀 직접관측 불가 → slope 외삽의 앵커(R1,R2, 가능하면 R3)만 신뢰.
 *
 * 빌드: nvcc --std=c++14 -O3 -o yttrium_round_decay yttrium_round_decay.cu
 * 실행: ./yttrium_round_decay
 * 정직: best-DP 는 δ-부분집합 경험적 상한(증명 아님), 절대 trail 경계 아님.
 *       2^-64/2^-128 은 직접측정 불가 → slope 선형외삽(보수). nvcc 는 에이전트가 실행 안 함.
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
__device__ __constant__ int EPS[8]={1,-1,1,-1,1,-1,1,-1};
__device__ __constant__ int SIGK[8];                     /* host-set σ powers; 0=identity */
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
    uint32_t xp[8]; for(int i=0;i<8;i++) xp[i]=rotl(w[i],A);
    uint32_t S=0; for(int i=0;i<8;i++) S += (EPS[i]>0)? xp[i] : (0u-xp[i]);
    uint32_t acc=0; for(int k=0;k<3;k++) acc^=rotl(S,TERMS[2*k])&rotl(S,TERMS[2*k+1]);
    uint32_t t=S^acc;
    for(int i=0;i<8;i++) w[i]=rotr(xp[i]+t,B);
    for(int i=0;i<8;i++) w[i]=alfp(w[i],SIGK[i]);
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
static uint32_t D[512][8]; static int nd=0;
void build_deltas(){
  int pos[8]={0,4,8,15,20,24,28,31};
  for(int wd=0;wd<8;wd++)for(int pi=0;pi<8;pi++){for(int i=0;i<8;i++)D[nd][i]=0;D[nd][wd]=1u<<pos[pi];nd++;} /*64 single-bit*/
  for(int p1=0;p1<32;p1+=8)for(int p2=p1+8;p2<32;p2+=8){for(int i=0;i<8;i++)D[nd][i]=0;D[nd][0]=(1u<<p1)|(1u<<p2);nd++;} /*2-bit word0*/
  int plus[4]={0,2,4,6},minus[4]={1,3,5,7};
  /* 영합 같은부호 MSB-쌍: ROTR_8(MSB)=bit23 입력차분 (worst-δ class) */
  for(int a=0;a<4;a++)for(int b=a+1;b<4;b++){for(int i=0;i<8;i++)D[nd][i]=0;D[nd][plus[a]]=0x00800000u;D[nd][plus[b]]=0x00800000u;nd++;}
  for(int a=0;a<4;a++)for(int b=a+1;b<4;b++){for(int i=0;i<8;i++)D[nd][i]=0;D[nd][minus[a]]=0x00800000u;D[nd][minus[b]]=0x00800000u;nd++;}
  /* 직접 MSB-쌍(출력레벨 후보) */
  for(int a=0;a<4;a++)for(int b=a+1;b<4;b++){for(int i=0;i<8;i++)D[nd][i]=0;D[nd][plus[a]]=1u<<31;D[nd][plus[b]]=1u<<31;nd++;}
  for(int a=0;a<4;a++)for(int b=a+1;b<4;b++){for(int i=0;i<8;i++)D[nd][i]=0;D[nd][minus[a]]=1u<<31;D[nd][minus[b]]=1u<<31;nd++;}
}
void run_R(uint64_t N,int A,int B,double*wR){     /* wR[1..7] = -log2(worst best-DP) */
  for(int R=1;R<=7;R++){
    double best=0;
    for(int di=0;di<nd;di++){double d=bestdp(N,R,A,B,D[di]);if(d>best)best=d;}
    wR[R]=-log2(best);
  }
}
int main(){
  cudaMalloc(&d_delta,8*4);cudaMalloc(&d_hist,NBUCKET*4);cudaMalloc(&d_max,4);
  const uint64_t N=1ULL<<30;  /* floor ~2^-25 (worst-δ 최대화시 겉보기 ~2^-23) */
  build_deltas();
  struct Mode{const char*name;int sig[8];};
  Mode modes[3]={
    {"all-8   k=1,2,3,5,7,11,13,17 (설계)", {1,2,3,5,7,11,13,17}},
    {"even-4  {0,2,4,6}                  ", {1,0,2,0,3,0,5,0}},
    {"sig{0,4} (ypsilenti식)             ", {1,0,0,0,3,0,0,0}},
  };
  printf("(yttrium) best-DP 라운드별 감쇠 R=1..7: N=2^30 (floor~2^-25), δ=%d (single+2bit+MSB영합쌍).\n",nd);
  printf("앵커: R1,R2(,R3) 만 floor 밖 신뢰. slope Δw 로 2^-64/2^-128 외삽(선형, 보수).\n\n");
  for(int m=0;m<3;m++){
    cudaMemcpyToSymbol(SIGK,modes[m].sig,sizeof(int)*8);
    double wR[8]; run_R(N,8,9,wR);
    printf("== σ = %s ==\n  ",modes[m].name);
    for(int R=1;R<=7;R++) printf("R%d=2^-%-5.1f ",R,wR[R]);
    printf("\n  per-round Δw: ");
    for(int R=2;R<=7;R++) printf("%+.1f ",wR[R]-wR[R-1]);
    printf("\n");
    if(m==0){
      /* 설계 σ: slope 외삽 요약.
       * acc-충돌(path a) 비용 = aligned-pair = 1/best-DP(R_b)  ← *제곱 아님*
       *   (적대검증 F1: 두 슬롯 출력차 ∇ 일치는 birthday/list-match → c∈[p^2,p], 비용 c^(-1/2)∈[p^-1/2,p^-1];
       *    보수적으로 1/best-DP. rb_wagner_cost.py 의 (1/p)^2 는 과대평가 = 폐기, rb_acc_cost_v2.py 가 정정판.)
       * 요건: worst-DP(R_b) <= 2^-64 (collision). slope 외삽으로 도달 R_b 추정.
       * 앵커는 R2->R3 slope 권장(R1 은 worst MSB-쌍이 F-비활성이라 prob-1≈2^-0 outlier). */
      double s23=wR[3]-wR[2];          /* R2->R3 slope (F 활성 영역) */
      printf("  [외삽, 선형 slope=R2->R3=%.1f, 앵커 w(R3)=%.1f; acc-비용=1/best-DP]\n",s23,wR[3]);
      for(int rb=4;rb<=12;rb++){double w=wR[3]+s23*(rb-3);
        printf("    R_b=%2d -> worst-DP≈2^-%.0f  acc-충돌≈2^%.0f %s\n",rb,w,w,
               (w>=64)?"(>=2^-64 acc-safe)":"");}
      printf("  주의: floor(~2^-23~25) 때문에 R>=3 은 측정 아닌 외삽. plateau(→F-floor 6)/가속 둘 다 가능.\n");
      printf("  digest 충돌/2nd-preimage(path b): 합성 R_b+R_c 의 worst-DP <= 2^-64(collision)/2^-128(preimage).\n");
    }
    printf("\n");fflush(stdout);
  }
  cudaFree(d_delta);cudaFree(d_hist);cudaFree(d_max);
  return 0;
}
