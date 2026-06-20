/* (α,β) 튜닝: ARX 결합기 ROTR_β(ROTL_α(x) ⊞ t) 의 회전쌍을 GPU로 sweep.
 * 가산 MSB 약점/저weight trail을 가장 빨리 죽이는 (α,β) = R=2 best-DP 최소.
 * 공통설계 고정: 3-term F (7,17),(3,21),(9,29), σ{0,4}. δ: word0 단일비트 32개 + 쌍 4개.
 * 빌드: nvcc --std=c++14 -O3 -o arx_gpu_tune arx_gpu_tune.cu
 * 주: RC는 XOR라 차분 투명 → 이 탐색과 무관(별도 rotational 용도).
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
__device__ __constant__ int SIG[4]={0,1, 4,3};
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
    uint32_t S=w[0];for(int i=1;i<8;i++)S^=w[i];
    uint32_t acc=0;for(int k=0;k<3;k++)acc^=rotl(S,TERMS[2*k])&rotl(S,TERMS[2*k+1]);
    uint32_t t=S^acc;
    for(int i=0;i<8;i++)w[i]=rotr(rotl(w[i],A)+t,B);
    for(int k=0;k<2;k++){int ln=SIG[2*k];w[ln]=alfp(w[ln],SIG[2*k+1]);}
    uint32_t nw[8];for(int i=0;i<8;i++)nw[i]=w[PPI[i]];for(int i=0;i<8;i++)w[i]=nw[i];}
}
__device__ inline uint32_t fold(const uint32_t*d){uint32_t f=0;for(int i=0;i<8;i++)f^=rotl(d[i],i*4);return f;}
__global__ void run(uint64_t N,int R,int A,int B,const uint32_t*delta,uint32_t*hist){
  uint64_t tid=blockIdx.x*(uint64_t)blockDim.x+threadIdx.x,str=gridDim.x*(uint64_t)blockDim.x;
  for(uint64_t s=tid;s<N;s+=str){
    uint32_t x[8],y[8];gen(s,x);for(int i=0;i<8;i++)y[i]=x[i]^delta[i];
    perm(x,R,A,B);perm(y,R,A,B);
    uint32_t d[8];for(int i=0;i<8;i++)d[i]=x[i]^y[i];
    atomicAdd(&hist[fold(d)&(NBUCKET-1)],1u);}
}
static uint32_t *d_delta,*d_hist,*h_hist;
double bestdp(uint64_t N,int R,int A,int B,const uint32_t*delta){
  cudaMemcpy(d_delta,delta,8*4,cudaMemcpyHostToDevice);
  cudaMemset(d_hist,0,NBUCKET*4);
  run<<<2048,256>>>(N,R,A,B,d_delta,d_hist);cudaDeviceSynchronize();
  cudaMemcpy(h_hist,d_hist,NBUCKET*4,cudaMemcpyDeviceToHost);
  uint32_t mx=0;for(uint32_t i=0;i<NBUCKET;i++)if(h_hist[i]>mx)mx=h_hist[i];
  return (double)mx/(double)N;
}
typedef struct{int a,b;double r2,r3;}Res;
int cmp(const void*p,const void*q){const Res*x=(const Res*)p,*y=(const Res*)q;
  return (x->r2>y->r2)-(x->r2<y->r2);}  /* r2 오름차순 (작을수록 강함) */
int main(){
  cudaMalloc(&d_delta,8*4);cudaMalloc(&d_hist,NBUCKET*4);h_hist=(uint32_t*)malloc(NBUCKET*4);
  const uint64_t N=1ULL<<26;
  uint32_t D[36][8];int nd=0;
  for(int j=0;j<32;j++){for(int i=0;i<8;i++)D[nd][i]=0;D[nd][0]=1u<<j;nd++;}
  for(int j=0;j<32;j+=8){for(int i=0;i<8;i++)D[nd][i]=0;D[nd][0]=D[nd][1]=1u<<j;nd++;}
  int amts[]={1,2,3,4,5,6,7,8,9,10,11,12,13,15}; int na=14;
  Res res[256]; int nr=0;
  for(int ia=0;ia<na;ia++)for(int ib=0;ib<na;ib++){
    int A=amts[ia],B=amts[ib];
    double b2=0;for(int di=0;di<nd;di++){double dp=bestdp(N,2,A,B,D[di]);if(dp>b2)b2=dp;}
    res[nr].a=A;res[nr].b=B;res[nr].r2=b2;res[nr].r3=-1;nr++;
  }
  qsort(res,nr,sizeof(Res),cmp);
  printf("(α,β) sweep — R=2 best-DP 오름차순(작을수록 강함). N=2^26, floor~2^-20.\n");
  printf("상위 12 (강함):  + 하위 5 (약함, MSB약점 큰 쌍)\n");
  printf("%-8s %-12s %-12s\n","(α,β)","R2 best-DP","R3 best-DP");
  for(int i=0;i<12&&i<nr;i++){
    double b3=0;for(int di=0;di<nd;di++){double dp=bestdp(N,3,res[i].a,res[i].b,D[di]);if(dp>b3)b3=dp;}
    printf("(%2d,%2d)  2^-%-9.1f 2^-%-9.1f\n",res[i].a,res[i].b,-log2(res[i].r2),-log2(b3));
  }
  printf("...\n");
  for(int i=nr-5;i<nr;i++) printf("(%2d,%2d)  2^-%-9.1f (weak)\n",res[i].a,res[i].b,-log2(res[i].r2));
  /* 현행 (8,3) 위치 */
  for(int i=0;i<nr;i++) if(res[i].a==8&&res[i].b==3) printf("\n현행 (8,3): 순위 %d/%d, R2=2^-%.1f\n",i+1,nr,-log2(res[i].r2));
  return 0;
}
