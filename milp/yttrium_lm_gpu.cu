/* yttrium Lai-Massey 가역 라운드 best-DP 하니스 (gen/fold/hist/rmax, arx_gpu_refine.cu 양식).
 * 이 라운드 반영:
 *   reduction: x'_i = ROTL_A(state_i);  S = Σ_i ε_i·x'_i (mod 2^32), ε=영합(+1/-1, Σ=0)
 *   t = F(S)            (3-term AND-based F, 회전 {7,17,3,21,9,29})
 *   combiner: y_i = ROTR_B(x'_i ⊞ t)                 (additive broadcast, 전 레인)
 *   σ: y0=α^1·y0, y4=α^3·y4  (GF(2^32) red 0x400007, post-combiner)
 *   π: new[i]=y[PPI[i]]
 * OLD σ-GLM과 달리 reduction이 영합(부호합)이라 라운드가 가역(오케스트레이터: invert 하니스 별도).
 * 빌드: nvcc --std=c++14 -O3 -o yttrium_lm_gpu yttrium_lm_gpu.cu && ./yttrium_lm_gpu
 * 측정 한계(정직): best-DP는 δ-부분집합 탐색의 경험적 상한(증명 아님). R=2/3/4. */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <math.h>
#define NB_LOG 24
#define NBUCKET (1u<<NB_LOG)
#define RED 0x400007u
__device__ __constant__ int PPI[8]={7,4,1,6,3,0,5,2};
__device__ __constant__ int TERMS[6]={7,17, 3,21, 9,29};
/* σ 권장: 전-lane GF α^{k_i}, distinct powers 1..8 (작은 n 전수에서 σ{0,4}는 미적용 lane의
 * MSB-쌍 불변을 일부 남길 수 있음 → 전-lane 권장). σ{0,4}만 쓰려면 SIG/NSIG를 {0,1,4,3}/2로. */
__device__ __constant__ int SIG[16]={0,1, 1,2, 2,3, 3,4, 4,5, 5,6, 6,7, 7,8};
__device__ __constant__ int NSIG=8;                          /* (lane, alpha power) 쌍 수 */
__device__ __constant__ int EPS[8]={1,-1,1,-1,1,-1,1,-1};   /* 영합 부호패턴, Σ=0 */
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
    /* reduction: x'_i = ROTL_A(w_i); 영합 S = Σ ε_i x'_i (mod 2^32) */
    uint32_t xp[8]; for(int i=0;i<8;i++)xp[i]=rotl(w[i],A);
    uint32_t S=0; for(int i=0;i<8;i++) S += (uint32_t)(EPS[i]) * xp[i];   /* 2의 보수: -1*x = ~x+1 */
    /* t = F(S) */
    uint32_t acc=0; for(int k=0;k<3;k++)acc^=rotl(S,TERMS[2*k])&rotl(S,TERMS[2*k+1]);
    uint32_t t=S^acc;
    /* combiner (additive broadcast, 전 레인): y_i = ROTR_B(x'_i + t) */
    for(int i=0;i<8;i++)w[i]=rotr(xp[i]+t,B);
    /* σ (post-combiner): 전-lane GF α^{k_i} (XOR-orthomorphism = Farfalle mask-roll) */
    for(int k=0;k<NSIG;k++){int ln=SIG[2*k];w[ln]=alfp(w[ln],SIG[2*k+1]);}
    /* π */
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
  /* fuller δ-set (arx_gpu_refine.cu와 동일 구성) */
  static uint32_t D[200][8]; int nd=0;
  int pos[8]={0,4,8,15,20,24,28,31};
  for(int wd=0;wd<8;wd++)for(int pi=0;pi<8;pi++){for(int i=0;i<8;i++)D[nd][i]=0;D[nd][wd]=1u<<pos[pi];nd++;} /*64*/
  for(int p1=0;p1<32;p1+=8)for(int p2=p1+8;p2<32;p2+=8){for(int i=0;i<8;i++)D[nd][i]=0;D[nd][0]=(1u<<p1)|(1u<<p2);nd++;} /*2-bit word0*/
  for(int j=0;j<32;j+=8){for(int i=0;i<8;i++)D[nd][i]=0;D[nd][0]=D[nd][1]=1u<<j;nd++;} /*inactive pair*/
  /* prob-1 inactive 후보 = ROTL_A(Δ)=2^31 인 Δ, 즉 Δ=ROTR_A(2^31). A=8 → 0x00800000.
   * (작은 n 전수로 '유일 prob-1 inactive 차분류 = 이 MSB-쌍'임을 증명; σ가 R≤2서 죽임 예측.) */
  uint32_t msbA = (0x80000000u>>(8&31))|(0x80000000u<<((32-8)&31)); /* ROTR_8(2^31)=0x00800000 */
  /* 모든 MSB-쌍 (lane i,j): 부호합 0 → 1라운드 inactive, σ가 R≤2서 소멸하는지 실측 */
  for(int i=0;i<8;i++)for(int j=i+1;j<8;j++){for(int k=0;k<8;k++)D[nd][k]=0;D[nd][i]=msbA;D[nd][j]=msbA;nd++;}
  /* 단일 MSB-after-rot (참고; 부호합≠0이라 inactive 아님) */
  for(int wd=0;wd<8;wd++){for(int i=0;i<8;i++)D[nd][i]=0;D[nd][wd]=msbA;nd++;}
  /* 후보 (α,β): 설계값 + 인접 (arx_gpu_refine.cu 상위) */
  int cand[][2]={{8,9},{9,10},{8,3},{7,4}};
  int ncand=4;
  printf("(LM 가역) best-DP: N=2^30(floor~2^-25), δ=%d (단일비트+2bit+MSB쌍+단일MSB). 영합 ε, 전-lane σ.\n\n",nd);
  for(int c=0;c<ncand;c++){int A=cand[c][0],B=cand[c][1];
    double b2=0,b3=0,b4=0;
    for(int di=0;di<nd;di++){double d2=bestdp(N,2,A,B,D[di]);if(d2>b2)b2=d2;}
    for(int di=0;di<nd;di++){double d3=bestdp(N,3,A,B,D[di]);if(d3>b3)b3=d3;}
    for(int di=0;di<nd;di++){double d4=bestdp(N,4,A,B,D[di]);if(d4>b4)b4=d4;}
    printf("  (%2d,%2d)  R2=2^-%-6.1f R3=2^-%-6.1f R4=2^-%-6.1f%s\n",A,B,-log2(b2),-log2(b3),-log2(b4),
           (A==8&&B==9)?"   <- 설계값":"");
    fflush(stdout);
  }
  return 0;
}
