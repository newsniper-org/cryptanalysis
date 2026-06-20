/* yttrium 가역(덧셈형 Horst) 조건 전수 검증:
 *   Φ(Σ) = Σ ⊞ 8·F(Σ)  가 Z/2^32 의 치환인가? (전수 2^32 = 완전 증명)
 *   F(s)=s^(s<<<7 & s<<<17)^(s<<<3 & s<<<21)^(s<<<9 & s<<<29).
 * 치환 ⟺ surjective ⟺ 모든 값이 정확히 1번 hit. 512MB 비트맵으로 검사.
 * 빌드: nvcc --std=c++14 -O3 -o yttrium_invert_check yttrium_invert_check.cu */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
__device__ inline uint32_t rotl(uint32_t x,int k){k&=31;return k?(x<<k)|(x>>(32-k)):x;}
__device__ inline uint32_t F(uint32_t s){
  return s ^ (rotl(s,7)&rotl(s,17)) ^ (rotl(s,3)&rotl(s,21)) ^ (rotl(s,9)&rotl(s,29));
}
/* Φ 후보들 (가산 계수 c·F, c=8 기본; 진단용 다른 c도) */
__device__ inline uint32_t Phi(uint32_t S,uint32_t mul){ return S + mul*F(S); }

__global__ void setbits(uint32_t mul,uint32_t*bm){
  uint64_t tid=blockIdx.x*(uint64_t)blockDim.x+threadIdx.x, str=gridDim.x*(uint64_t)blockDim.x;
  for(uint64_t S=tid;S<(1ULL<<32);S+=str){
    uint32_t v=Phi((uint32_t)S,mul);
    atomicOr(&bm[v>>5], 1u<<(v&31));
  }
}
__global__ void popc(const uint32_t*bm,unsigned long long*cnt){
  uint64_t tid=blockIdx.x*(uint64_t)blockDim.x+threadIdx.x, str=gridDim.x*(uint64_t)blockDim.x;
  unsigned long long local=0;
  for(uint64_t i=tid;i<(1ULL<<27);i+=str) local+=__popc(bm[i]);
  atomicAdd(cnt,local);
}
int main(){
  uint32_t *bm; unsigned long long *d_cnt,h_cnt;
  size_t BMW=(1ULL<<27); /* 2^32 bits = 2^27 words = 512MB */
  if(cudaMalloc(&bm,BMW*4)!=cudaSuccess){printf("OOM bitmap\n");return 2;}
  cudaMalloc(&d_cnt,8);
  uint32_t muls[]={8u, 2u, 1u, 16u, 24u}; /* 8=설계값; 진단용 비교 */
  const char* note[]={"<- 설계값 (8t)","","","",""};
  printf("Φ(Σ)=Σ + c·F(Σ) 전수 치환성 (distinct count == 2^32 이면 bijection)\n\n");
  for(int m=0;m<5;m++){
    cudaMemset(bm,0,BMW*4);
    setbits<<<65535,256>>>(muls[m],bm); cudaDeviceSynchronize();
    cudaMemset(d_cnt,0,8); popc<<<1024,256>>>(bm,d_cnt); cudaDeviceSynchronize();
    cudaMemcpy(&h_cnt,d_cnt,8,cudaMemcpyDeviceToHost);
    double frac=(double)h_cnt/4294967296.0;
    printf("  c=%2u : distinct=%llu / 2^32  (%.4f%% 도달) %s %s\n",
      muls[m],h_cnt, frac*100.0, (h_cnt==4294967296ULL)?"=> BIJECTION ✓":"=> NOT bijective ✗", note[m]);
  }
  return 0;
}
