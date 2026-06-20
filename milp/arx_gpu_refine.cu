/* (a) 상위 (α,β) 정밀 재순위 — N↑ + fuller δ-set, R=2/3/4.
 * 공통설계 고정(3-term F, σ{0,4}). δ: 8개 워드 단일비트(여러 위치) + 2-bit(word0) + 비활성쌍.
 * 빌드: nvcc --std=c++14 -O3 -o arx_gpu_refine arx_gpu_refine.cu */
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
  for(int r=0;r<R;r++){uint32_t S=w[0];for(int i=1;i<8;i++)S^=w[i];
    uint32_t acc=0;for(int k=0;k<3;k++)acc^=rotl(S,TERMS[2*k])&rotl(S,TERMS[2*k+1]);
    uint32_t t=S^acc; for(int i=0;i<8;i++)w[i]=rotr(rotl(w[i],A)+t,B);
    for(int k=0;k<2;k++){int ln=SIG[2*k];w[ln]=alfp(w[ln],SIG[2*k+1]);}
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
int main(){
  cudaMalloc(&d_delta,8*4);cudaMalloc(&d_hist,NBUCKET*4);cudaMalloc(&d_max,4);
  const uint64_t N=1ULL<<30;  /* floor ~2^-25 */
  /* fuller δ-set */
  static uint32_t D[200][8]; int nd=0;
  int pos[8]={0,4,8,15,20,24,28,31};
  for(int wd=0;wd<8;wd++)for(int pi=0;pi<8;pi++){for(int i=0;i<8;i++)D[nd][i]=0;D[nd][wd]=1u<<pos[pi];nd++;} /*64*/
  for(int p1=0;p1<32;p1+=8)for(int p2=p1+8;p2<32;p2+=8){for(int i=0;i<8;i++)D[nd][i]=0;D[nd][0]=(1u<<p1)|(1u<<p2);nd++;} /*2-bit word0*/
  for(int j=0;j<32;j+=8){for(int i=0;i<8;i++)D[nd][i]=0;D[nd][0]=D[nd][1]=1u<<j;nd++;} /*inactive pair*/
  /* 후보 (α,β): sweep 상위 + 현행 */
  int cand[][2]={{9,10},{8,9},{10,11},{15,9},{7,4},{7,8},{7,2},{6,8},{8,15},{3,4},{8,3}};
  int ncand=11;
  typedef struct{int a,b;double r2,r3,r4;}Res; Res res[32];
  printf("(a) 정밀 재순위: N=2^30(floor~2^-25), δ=%d (8워드 단일비트+2bit+쌍). 3-term σ{0,4}.\n\n",nd);
  for(int c=0;c<ncand;c++){int A=cand[c][0],B=cand[c][1];
    double b2=0,b3=0,b4=0;
    for(int di=0;di<nd;di++){double d2=bestdp(N,2,A,B,D[di]);if(d2>b2)b2=d2;}
    for(int di=0;di<nd;di++){double d3=bestdp(N,3,A,B,D[di]);if(d3>b3)b3=d3;}
    for(int di=0;di<nd;di++){double d4=bestdp(N,4,A,B,D[di]);if(d4>b4)b4=d4;}
    res[c].a=A;res[c].b=B;res[c].r2=b2;res[c].r3=b3;res[c].r4=b4;
    printf("  (%2d,%2d)  R2=2^-%-6.1f R3=2^-%-6.1f R4=2^-%-6.1f%s\n",A,B,-log2(b2),-log2(b3),-log2(b4),
           (A==8&&B==3)?"   <- 현행":"");
    fflush(stdout);
  }
  return 0;
}
