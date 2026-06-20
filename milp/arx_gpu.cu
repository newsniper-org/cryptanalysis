/* ARX(Amaryllises) 절대 best-DP GPU 측정 (ypsilenti 8×u32).
 * z3가 막힌 영역(R≥2 full-width)의 *경험적 상한*을 대량 샘플로.
 * 빌드: nvcc --std=c++14 -O3 -o arx_gpu arx_gpu.cu   (libstdc++16↔CUDA 비호환 회피: C 헤더만)
 *
 * 방법: 입력차분 δ마다 N개 무작위 상태 x에 대해 diff=P^R(x)^P^R(x⊕δ) 를 구해
 *       히스토그램(2^24 버킷, 32-bit fold)에 누적 → max버킷/N = 경험적 best-DP(δ).
 *       변형의 best-DP = max_δ. floor≈버킷baseline/N. *증명 아닌 상한.* */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <math.h>

#define NB_LOG 24
#define NBUCKET (1u<<NB_LOG)
#define RED 0x400007u
__device__ __constant__ int PPI[8]={7,4,1,6,3,0,5,2};

__device__ inline uint32_t rotl(uint32_t x,int k){k&=31;return k? (x<<k)|(x>>(32-k)):x;}
__device__ inline uint32_t rotr(uint32_t x,int k){return rotl(x,(32-(k&31))&31);}
__device__ inline uint32_t alpha(uint32_t y){uint32_t m=0u-(y>>31);return (y<<1)^(m&RED);}
__device__ inline uint32_t alphapow(uint32_t y,int p){for(int i=0;i<p;i++)y=alpha(y);return y;}

/* splitmix64 -> 8 words */
__device__ inline void gen_state(uint64_t seed, uint32_t*w){
  for(int i=0;i<4;i++){ seed+=0x9E3779B97F4A7C15ULL; uint64_t z=seed;
    z=(z^(z>>30))*0xBF58476D1CE4E5B9ULL; z=(z^(z>>27))*0x94D049BB133111EBULL; z^=z>>31;
    w[2*i]=(uint32_t)z; w[2*i+1]=(uint32_t)(z>>32);} }

__device__ inline void permute(uint32_t*w,int rounds,int comb,
    int nt,const int*terms,int ns,const int*sig){
  for(int r=0;r<rounds;r++){
    uint32_t S=w[0]; for(int i=1;i<8;i++)S^=w[i];
    uint32_t acc=0; for(int k=0;k<nt;k++)acc^=rotl(S,terms[2*k])&rotl(S,terms[2*k+1]);
    uint32_t t=S^acc;
    if(comb==0){ for(int i=0;i<8;i++)w[i]^=t; }
    else{ for(int i=0;i<8;i++) w[i]=rotr(rotl(w[i],8)+t,3); }
    for(int k=0;k<ns;k++){int ln=sig[2*k];w[ln]=alphapow(w[ln],sig[2*k+1]);}
    uint32_t nw[8]; for(int i=0;i<8;i++)nw[i]=w[PPI[i]]; for(int i=0;i<8;i++)w[i]=nw[i];
  }
}
__device__ inline uint32_t fold(const uint32_t*d){
  uint32_t f=0; for(int i=0;i<8;i++)f^=rotl(d[i],i*4); return f;
}

__global__ void run(uint64_t N,uint64_t base,int rounds,int comb,int nt,const int*terms,
                    int ns,const int*sig,const uint32_t*delta,uint32_t*hist){
  uint64_t tid=blockIdx.x*(uint64_t)blockDim.x+threadIdx.x;
  uint64_t stride=gridDim.x*(uint64_t)blockDim.x;
  for(uint64_t s=tid;s<N;s+=stride){
    uint32_t x[8],y[8]; gen_state(base+s,x); for(int i=0;i<8;i++)y[i]=x[i]^delta[i];
    permute(x,rounds,comb,nt,terms,ns,sig); permute(y,rounds,comb,nt,terms,ns,sig);
    uint32_t d[8]; for(int i=0;i<8;i++)d[i]=x[i]^y[i];
    uint32_t b=fold(d)&(NBUCKET-1);
    atomicAdd(&hist[b],1u);
  }
}
/* host helpers ----------------------------------------------------------- */
static int *d_terms,*d_sig; static uint32_t *d_delta,*d_hist;
double best_dp(uint64_t N,int rounds,int comb,int nt,const int*terms,int ns,const int*sig,const uint32_t*delta){
  cudaMemcpy(d_terms,terms,2*nt*sizeof(int),cudaMemcpyHostToDevice);
  cudaMemcpy(d_sig,sig,2*ns*sizeof(int),cudaMemcpyHostToDevice);
  cudaMemcpy(d_delta,delta,8*sizeof(uint32_t),cudaMemcpyHostToDevice);
  cudaMemset(d_hist,0,NBUCKET*sizeof(uint32_t));
  run<<<2048,256>>>(N,0,rounds,comb,nt,d_terms,ns,d_sig,d_delta,d_hist);
  cudaDeviceSynchronize();
  static uint32_t *h=0; if(!h)h=(uint32_t*)malloc(NBUCKET*sizeof(uint32_t));
  cudaMemcpy(h,d_hist,NBUCKET*sizeof(uint32_t),cudaMemcpyDeviceToHost);
  uint32_t mx=0; for(uint32_t i=0;i<NBUCKET;i++) if(h[i]>mx)mx=h[i];
  return (double)mx/(double)N;
}
int main(){
  cudaMalloc(&d_terms,8*sizeof(int)); cudaMalloc(&d_sig,8*sizeof(int));
  cudaMalloc(&d_delta,8*sizeof(uint32_t)); cudaMalloc(&d_hist,NBUCKET*sizeof(uint32_t));
  const uint64_t N=1ULL<<28;   /* 268M 표본/δ → floor ~ 2^-22 */
  /* 변형: combiner(0=xor,1=arx), F terms, sigma (lane,pow) */
  int F3[6]={7,17, 3,21, 9,29};
  int F4[8]={7,17, 3,21, 9,29, 1,7};
  int F2o[4]={7,17, 3,13};
  int S2[4]={0,1, 4,3}; int S4[8]={0,1, 2,5, 4,3, 6,7};
  struct Cfg{const char*name;int comb,nt;int*terms;int ns;int*sig;};
  Cfg cfgs[]={
    {"[base] sGLM XOR 2term(orig) s{0,4}",0,2,F2o,2,S2},
    {"ARX 3term s{0,4}",1,3,F3,2,S2},
    {"ARX 4term s{0,4}",1,4,F4,2,S2},
    {"ARX 3term s{0,2,4,6}",1,3,F3,4,S4},
    {"ARX 4term s{0,2,4,6}",1,4,F4,4,S4},
  };
  int ncfg=5; int rounds_list[3]={2,3,4};
  /* delta set: single-bit word0 (8), MSB-aligned word0 (bit31), inactive pair w0=w1 (4) */
  uint32_t deltas[16][8]; int nd=0;
  for(int j=0;j<32;j+=4){ for(int i=0;i<8;i++)deltas[nd][i]=0; deltas[nd][0]=1u<<j; nd++; }
  for(int j=0;j<32;j+=8){ for(int i=0;i<8;i++)deltas[nd][i]=0; deltas[nd][0]=1u<<j; deltas[nd][1]=1u<<j; nd++; }
  printf("GPU 경험적 best-DP (N=2^28, floor~2^-22; -log2 표기, 클수록 강함). *증명 아닌 상한*\n\n");
  printf("%-38s","config");
  for(int ri=0;ri<3;ri++)printf("  R=%-9d",rounds_list[ri]); printf("\n");
  for(int c=0;c<ncfg;c++){
    printf("%-38s",cfgs[c].name);
    for(int ri=0;ri<3;ri++){
      double best=0;
      for(int di=0;di<nd;di++){
        double dp=best_dp(N,rounds_list[ri],cfgs[c].comb,cfgs[c].nt,cfgs[c].terms,cfgs[c].ns,cfgs[c].sig,deltas[di]);
        if(dp>best)best=dp;
      }
      double w=-log2(best);
      printf("  2^-%-7.1f",w);
      fflush(stdout);
    }
    printf("\n");
  }
  return 0;
}
