/* yttrium-large (u64, 16-lane) best-DP 라운드별 감쇠 — u64 보안레벨 정당화.
 * 라운드 = large.rs와 bit-동일: ROTL8 → 영합 Σεᵢ(ε=[+,−]×8) → F → ROTR9(⊞t) → all-16 σ(α^k) → π.
 *   GF(2^64) red 0x1B, k=[1..15,17], π=[7,12,1,6,11,0,5,10,15,4,9,14,3,8,13,2].
 * 목적: slope로 best-DP(R_b)≤2⁻¹²⁸(256-bit digest birthday) 도달 R_b 외삽.
 * 빌드: nvcc --std=c++14 -O3 -o yttrium_large_decay yttrium_large_decay.cu */
#include <stdio.h>
#include <stdint.h>
#include <math.h>
#define NB_LOG 24
#define NBUCKET (1u<<NB_LOG)
#define RED64 0x1BULL
__device__ __constant__ int PPI[16]={7,12,1,6,11,0,5,10,15,4,9,14,3,8,13,2};
__device__ __constant__ int TERMS[6]={7,17, 3,21, 9,29};
__device__ __constant__ int SIGK[16]={1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,17};
/* ε=[+,−]×8 : 짝수 레인 +, 홀수 − */
__device__ inline uint64_t rotl(uint64_t x,int k){k&=63;return k?(x<<k)|(x>>(64-k)):x;}
__device__ inline uint64_t rotr(uint64_t x,int k){return rotl(x,(64-(k&63))&63);}
__device__ inline uint64_t alf(uint64_t y){uint64_t m=0ULL-(y>>63);return (y<<1)^(m&RED64);}
__device__ inline uint64_t alfp(uint64_t y,int p){for(int i=0;i<p;i++)y=alf(y);return y;}
__device__ inline void gen(uint64_t seed,uint64_t*w){
  for(int i=0;i<16;i++){seed+=0x9E3779B97F4A7C15ULL;uint64_t z=seed;
    z=(z^(z>>30))*0xBF58476D1CE4E5B9ULL;z=(z^(z>>27))*0x94D049BB133111EBULL;z^=z>>31;w[i]=z;}}
__device__ inline void perm(uint64_t*w,int R){
  for(int r=0;r<R;r++){
    uint64_t xp[16]; for(int i=0;i<16;i++) xp[i]=rotl(w[i],8);
    uint64_t S=0; for(int i=0;i<16;i++) S += (i&1)? (0ULL-xp[i]) : xp[i];
    uint64_t acc=0; for(int k=0;k<3;k++) acc^=rotl(S,TERMS[2*k])&rotl(S,TERMS[2*k+1]);
    uint64_t t=S^acc;
    for(int i=0;i<16;i++) w[i]=rotr(xp[i]+t,9);
    for(int i=0;i<16;i++) w[i]=alfp(w[i],SIGK[i]);
    uint64_t nw[16];for(int i=0;i<16;i++)nw[i]=w[PPI[i]];for(int i=0;i<16;i++)w[i]=nw[i];}}
__device__ inline uint32_t fold(const uint64_t*d){uint64_t f=0;for(int i=0;i<16;i++)f^=rotl(d[i],i*4);
  return (uint32_t)((f^(f>>32))&(NBUCKET-1));}
__global__ void run(uint64_t N,int R,const uint64_t*delta,uint32_t*hist){
  uint64_t tid=blockIdx.x*(uint64_t)blockDim.x+threadIdx.x,str=gridDim.x*(uint64_t)blockDim.x;
  for(uint64_t s=tid;s<N;s+=str){uint64_t x[16],y[16];gen(s,x);for(int i=0;i<16;i++)y[i]=x[i]^delta[i];
    perm(x,R);perm(y,R);uint64_t d[16];for(int i=0;i<16;i++)d[i]=x[i]^y[i];
    atomicAdd(&hist[fold(d)],1u);}}
__global__ void rmax(const uint32_t*hist,uint32_t*out){
  uint32_t tid=blockIdx.x*blockDim.x+threadIdx.x,str=gridDim.x*blockDim.x,m=0;
  for(uint32_t i=tid;i<NBUCKET;i+=str) if(hist[i]>m)m=hist[i];
  atomicMax(out,m);}
static uint64_t *d_delta; static uint32_t *d_hist,*d_max;
double bestdp(uint64_t N,int R,const uint64_t*delta){
  cudaMemcpy(d_delta,delta,16*8,cudaMemcpyHostToDevice);cudaMemset(d_hist,0,NBUCKET*4);
  run<<<4096,256>>>(N,R,d_delta,d_hist);
  cudaMemset(d_max,0,4); rmax<<<256,256>>>(d_hist,d_max); cudaDeviceSynchronize();
  uint32_t mx=0; cudaMemcpy(&mx,d_max,4,cudaMemcpyDeviceToHost); return (double)mx/(double)N;}
static uint64_t D[256][16]; static int nd=0;
void build(){
  int pos[8]={0,8,20,31,40,52,60,63};
  for(int wd=0;wd<16;wd++)for(int pi=0;pi<8;pi++){for(int i=0;i<16;i++)D[nd][i]=0;D[nd][wd]=1ULL<<pos[pi];nd++;}
  /* 영합 같은부호 MSB-쌍: 짝수레인(+)쌍, 홀수레인(−)쌍. ROTR_8(MSB63)=bit55 입력차분 */
  for(int a=0;a<16;a+=2)for(int b=a+2;b<16;b+=2){for(int i=0;i<16;i++)D[nd][i]=0;D[nd][a]=1ULL<<55;D[nd][b]=1ULL<<55;nd++; if(nd>=240)return;}
  for(int a=1;a<16;a+=2)for(int b=a+2;b<16;b+=2){for(int i=0;i<16;i++)D[nd][i]=0;D[nd][a]=1ULL<<55;D[nd][b]=1ULL<<55;nd++; if(nd>=240)return;}
}
int main(){
  cudaMalloc(&d_delta,16*8);cudaMalloc(&d_hist,NBUCKET*4);cudaMalloc(&d_max,4);
  const uint64_t N=1ULL<<30; build();
  printf("yttrium-large (u64,16-lane) best-DP 감쇠 R=1..5: N=2^30(floor~2^-25), δ=%d.\n",nd);
  double w[6];
  for(int R=1;R<=5;R++){double best=0;for(int di=0;di<nd;di++){double d=bestdp(N,R,D[di]);if(d>best)best=d;}w[R]=-log2(best);
    printf("  R%d=2^-%-5.1f\n",R,w[R]);fflush(stdout);}
  double s=w[3]-w[2];
  printf("\nslope(R2->R3)=%.1f, 앵커 w(R3)=%.1f. acc-비용=1/best-DP.\n",s,w[3]);
  printf("256-bit digest birthday=2^128 → best-DP(R_b)<=2^-128 필요:\n");
  for(int rb=8;rb<=20;rb++){double ww=w[3]+s*(rb-3);
    printf("  R_b=%2d -> best-DP≈2^-%-3.0f acc≈2^%-3.0f %s%s\n",rb,ww,ww,
      (ww>=64)?"[>=2^-64]":"",(ww>=128)?" [>=2^-128 ✓256bit]":"");}
  printf("(floor 너머 외삽; 절대경계 아님. u32 변형(R_b<=10)은 ~128-bit급, full 256-bit엔 위 R_b.)\n");
  return 0;}
