/* yttrium 튜닝 배치: σ-power 집합 최소화 · (α,β) · ε 패턴. MSB-쌍 worst-δ best-DP R2/R3.
 * 라운드 = yttrium_lm_diff.cu 와 bit-동일(영합 LM + ARX + σ all-8 + π). σ-power·(α,β)·ε 가변.
 * 목적: 현 σ k=[1,2,3,5,7,11,13,17](Σ=59 α-step)를 더 싼 distinct-power로 줄여도
 *       MSB-쌍이 R2서 붕괴(≈2^-15)하는가. (α,β)·ε 미세조정 확인.
 * 빌드: nvcc --std=c++14 -O3 -o yttrium_tune yttrium_tune.cu */
#include <stdio.h>
#include <stdint.h>
#include <math.h>
#define NB_LOG 24
#define NBUCKET (1u<<NB_LOG)
#define RED 0x400007u
__device__ __constant__ int PPI[8]={7,4,1,6,3,0,5,2};
__device__ __constant__ int TERMS[6]={7,17, 3,21, 9,29};
__device__ __constant__ int SIGK[8];
__device__ __constant__ int EPSc[8];
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
    uint32_t S=0; for(int i=0;i<8;i++) S += (EPSc[i]>0)? xp[i] : (0u-xp[i]);
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
  uint32_t mx=0; cudaMemcpy(&mx,d_max,4,cudaMemcpyDeviceToHost); return (double)mx/(double)N;}
/* 판별력 있는 MSB-쌍 δ-set만 (빠르게) */
static uint32_t D[64][8]; static int nd=0;
void build(){int plus[4]={0,2,4,6},minus[4]={1,3,5,7};
  for(int a=0;a<4;a++)for(int b=a+1;b<4;b++){for(int i=0;i<8;i++)D[nd][i]=0;D[nd][plus[a]]=0x00800000u;D[nd][plus[b]]=0x00800000u;nd++;}
  for(int a=0;a<4;a++)for(int b=a+1;b<4;b++){for(int i=0;i<8;i++)D[nd][i]=0;D[nd][minus[a]]=0x00800000u;D[nd][minus[b]]=0x00800000u;nd++;}
  for(int a=0;a<4;a++)for(int b=a+1;b<4;b++){for(int i=0;i<8;i++)D[nd][i]=0;D[nd][plus[a]]=1u<<31;D[nd][plus[b]]=1u<<31;nd++;}}
void setc(const int*sig,const int*eps){cudaMemcpyToSymbol(SIGK,sig,32);cudaMemcpyToSymbol(EPSc,eps,32);}
double worst(uint64_t N,int R,int A,int B){double b=0;for(int i=0;i<nd;i++){double d=bestdp(N,R,A,B,D[i]);if(d>b)b=d;}return b;}
int main(){
  cudaMalloc(&d_delta,8*4);cudaMalloc(&d_hist,NBUCKET*4);cudaMalloc(&d_max,4);
  const uint64_t N=1ULL<<30; build();
  int ALT[8]={1,-1,1,-1,1,-1,1,-1}, BLK[8]={1,1,1,1,-1,-1,-1,-1};
  int CUR[8]={1,2,3,5,7,11,13,17};   /* Σ=59 (현행) */
  int SEQ[8]={1,2,3,4,5,6,7,8};      /* Σ=36 (minimal distinct-positive) */
  int LOW[8]={1,2,3,4,5,6,7,9};      /* Σ=37 (9 회피 검증용 변형) */
  printf("yttrium 튜닝: MSB-쌍 worst-δ best-DP (N=2^30, δ=%d). R2/R3.\n\n",nd);
  printf("== σ-power 집합 (ε=alt, (α,β)=(8,9)) ==\n");
  struct{const char*n;int*s;int cost;}sm[]={{"cur [1,2,3,5,7,11,13,17]",CUR,59},{"seq [1..8]",SEQ,36},{"low [1,2,3,4,5,6,7,9]",LOW,37}};
  for(int m=0;m<3;m++){setc(sm[m].s,ALT);double r2=worst(N,2,8,9),r3=worst(N,3,8,9);
    printf("  %-26s Σα-step=%2d : R2=2^-%-5.1f R3=2^-%-5.1f\n",sm[m].n,sm[m].cost,-log2(r2),-log2(r3));fflush(stdout);}
  printf("\n== (α,β) (σ=cur, ε=alt) ==\n");
  int ab[][2]={{8,9},{9,10},{8,3}};
  for(int m=0;m<3;m++){setc(CUR,ALT);double r2=worst(N,2,ab[m][0],ab[m][1]),r3=worst(N,3,ab[m][0],ab[m][1]);
    printf("  (%d,%2d) : R2=2^-%-5.1f R3=2^-%-5.1f\n",ab[m][0],ab[m][1],-log2(r2),-log2(r3));fflush(stdout);}
  printf("\n== ε 패턴 (σ=cur, (α,β)=(8,9)) ==\n");
  struct{const char*n;int*e;}em[]={{"alt [+,-,+,-,+,-,+,-]",ALT},{"blk [+,+,+,+,-,-,-,-]",BLK}};
  for(int m=0;m<2;m++){setc(CUR,em[m].e);double r2=worst(N,2,8,9),r3=worst(N,3,8,9);
    printf("  %-24s : R2=2^-%-5.1f R3=2^-%-5.1f\n",em[m].n,-log2(r2),-log2(r3));fflush(stdout);}
  cudaFree(d_delta);cudaFree(d_hist);cudaFree(d_max);return 0;}
