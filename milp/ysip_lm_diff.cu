/* YSip best-DP 경험적 감쇠 (GPU) — yttrium_lm_diff.cu 양식 이식 (4×u64 SipRound-rar).
 *
 * 라운드(YSip): rar(x,y)=ROTR_B(ROTL_A(x)⊞y);
 *   v0=rar(v0,v1); v1=rotl(v1,13); v1^=v0; v0=rotl(v0,32);
 *   v2=rar(v2,v3); v3=rotl(v3,16); v3^=v2;
 *   v0=rar(v0,v3); v3=rotl(v3,21); v3^=v0;
 *   v2=rar(v2,v1); v1=rotl(v1,17); v1^=v2; v2=rotl(v2,32);
 * SipHash 모드: combine=⊞ (calibration).
 *
 * 방법: 입력차분 δ 고정 → x,x⊕δ R라운드 → 출력차분을 24bit fold 히스토그램 →
 *   max bucket / N = best 관측 (truncated) DP. δ 후보 sweep. floor~2^-23.2 (N=2^30, 24bit-fold max-bucket noise).
 * 정직: 경험적 상한(공격자 trail 발견 = min-weight의 상계), 절대 trail 경계 아님.
 *   SMT(ysip_diff.py)는 R1,R2 정확 하한. 둘이 상보적.
 *
 * 빌드: nvcc -O3 -o ysip_lm_diff ysip_lm_diff.cu   (arch 자동; 실패시 -arch=sm_XX)
 * 실행: ./ysip_lm_diff
 */
#include <stdio.h>
#include <stdint.h>
#include <math.h>
#define NB_LOG 24
#define NBUCKET (1u<<NB_LOG)

__device__ inline uint64_t rotl(uint64_t x,int k){k&=63;return k?(x<<k)|(x>>(64-k)):x;}
__device__ inline uint64_t rotr(uint64_t x,int k){return rotl(x,(64-(k&63))&63);}

__device__ inline void gen(uint64_t seed,uint64_t*v){
  for(int i=0;i<4;i++){seed+=0x9E3779B97F4A7C15ULL;uint64_t z=seed;
    z=(z^(z>>30))*0xBF58476D1CE4E5B9ULL;z=(z^(z>>27))*0x94D049BB133111EBULL;z^=z>>31;v[i]=z;}}

/* mode: 0=ysip(rar), 1=siphash(plain add). A,B = rar 회전. */
__device__ inline void perm(uint64_t*v,int R,int mode,int A,int B){
  for(int r=0;r<R;r++){
    uint64_t v0=v[0],v1=v[1],v2=v[2],v3=v[3];
    #define COMB(x,y) (mode? ((x)+(y)) : rotr(rotl((x),A)+(y),B))
    v0=COMB(v0,v1); v1=rotl(v1,13); v1^=v0; v0=rotl(v0,32);
    v2=COMB(v2,v3); v3=rotl(v3,16); v3^=v2;
    v0=COMB(v0,v3); v3=rotl(v3,21); v3^=v0;
    v2=COMB(v2,v1); v1=rotl(v1,17); v1^=v2; v2=rotl(v2,32);
    #undef COMB
    v[0]=v0;v[1]=v1;v[2]=v2;v[3]=v3;
  }
}
__device__ inline uint32_t fold(const uint64_t*d){
  uint64_t f=d[0]^rotl(d[1],16)^rotl(d[2],32)^rotl(d[3],48);
  return (uint32_t)(f^(f>>32))&(NBUCKET-1);}

__global__ void run(uint64_t N,int R,int mode,int A,int B,const uint64_t*delta,uint32_t*hist){
  uint64_t tid=blockIdx.x*(uint64_t)blockDim.x+threadIdx.x,str=gridDim.x*(uint64_t)blockDim.x;
  for(uint64_t s=tid;s<N;s+=str){uint64_t x[4],y[4];gen(s,x);for(int i=0;i<4;i++)y[i]=x[i]^delta[i];
    perm(x,R,mode,A,B);perm(y,R,mode,A,B);uint64_t d[4];for(int i=0;i<4;i++)d[i]=x[i]^y[i];
    atomicAdd(&hist[fold(d)],1u);}}
__global__ void rmax(const uint32_t*hist,uint32_t*out){
  uint32_t tid=blockIdx.x*blockDim.x+threadIdx.x,str=gridDim.x*blockDim.x,m=0;
  for(uint32_t i=tid;i<NBUCKET;i+=str) if(hist[i]>m)m=hist[i];
  atomicMax(out,m);}

static uint64_t *d_delta,*d_max_dummy; static uint32_t *d_hist,*d_max;
double bestdp(uint64_t N,int R,int mode,int A,int B,const uint64_t*delta){
  cudaMemcpy(d_delta,delta,4*8,cudaMemcpyHostToDevice);cudaMemset(d_hist,0,(size_t)NBUCKET*4);
  run<<<4096,256>>>(N,R,mode,A,B,d_delta,d_hist);
  cudaMemset(d_max,0,4); rmax<<<256,256>>>(d_hist,d_max); cudaDeviceSynchronize();
  uint32_t mx=0; cudaMemcpy(&mx,d_max,4,cudaMemcpyDeviceToHost);
  return (double)mx/(double)N;}

static uint64_t D[600][4]; static int nd=0;
void add_delta(int w,uint64_t val){for(int i=0;i<4;i++)D[nd][i]=0;D[nd][w]=val;nd++;}
void build_deltas(){
  int pos[10]={0,1,8,15,23,31,40,48,55,63};
  for(int w=0;w<4;w++)for(int p=0;p<10;p++)add_delta(w,1ULL<<pos[p]);   /* 40 single-bit */
  for(int w=0;w<4;w++)add_delta(w,1ULL<<63);                            /* MSB-only (add free-trail seed) */
  /* 2-bit, word0, MSB-pair cross-word */
  for(int p=0;p<64;p+=16){for(int i=0;i<4;i++)D[nd][i]=0;D[nd][0]=(1ULL<<p)|(1ULL<<((p+8)&63));nd++;}
  for(int a=0;a<4;a++)for(int b=a+1;b<4;b++){for(int i=0;i<4;i++)D[nd][i]=0;D[nd][a]=1ULL<<63;D[nd][b]=1ULL<<63;nd++;}
}
void run_at(uint64_t N,int mode,int A,int B,double*b2,double*b3,double*b4){
  *b2=*b3=*b4=0;
  for(int di=0;di<nd;di++){double d=bestdp(N,2,mode,A,B,D[di]);if(d>*b2)*b2=d;}
  for(int di=0;di<nd;di++){double d=bestdp(N,3,mode,A,B,D[di]);if(d>*b3)*b3=d;}
  for(int di=0;di<nd;di++){double d=bestdp(N,4,mode,A,B,D[di]);if(d>*b4)*b4=d;}
}
int main(){
  cudaMalloc(&d_delta,4*8);cudaMalloc(&d_hist,(size_t)NBUCKET*4);cudaMalloc(&d_max,4);
  const uint64_t N=1ULL<<30;
  build_deltas();
  printf("YSip best-DP 경험적 감쇠: N=2^30 (floor~2^-23.2), δ=%d (단일비트+MSB+2bit+MSB쌍). fold=24bit.\n",nd);
  printf("정직: 경험적 상한(δ-부분집합 탐색). SMT R1,R2 정확하한과 상보.\n\n");
  double b2,b3,b4;
  printf("== calibration: SipHash vs YSip (8,9) worst-δ best-DP ==\n");
  run_at(N,1,0,0,&b2,&b3,&b4);
  printf("  SipHash     R2=2^-%-5.1f R3=2^-%-5.1f R4=2^-%-5.1f\n",-log2(b2),-log2(b3),-log2(b4));fflush(stdout);
  run_at(N,0,8,9,&b2,&b3,&b4);
  printf("  YSip(8,9)   R2=2^-%-5.1f R3=2^-%-5.1f R4=2^-%-5.1f  <- 설계\n",-log2(b2),-log2(b3),-log2(b4));fflush(stdout);
  printf("\n== YSip (A,B) sweep (상수튜닝: 높은 -log2 DP = 강함) ==\n");
  int cand[][2]={{8,9},{8,3},{7,16},{12,29},{16,21},{8,21},{24,16},{32,16}};
  for(int c=0;c<8;c++){int A=cand[c][0],B=cand[c][1];run_at(N,0,A,B,&b2,&b3,&b4);
    printf("  (%2d,%2d) R2=2^-%-5.1f R3=2^-%-5.1f R4=2^-%-5.1f%s\n",A,B,-log2(b2),-log2(b3),-log2(b4),
           (A==8&&B==9)?"  <- 현 설계":"");fflush(stdout);}
  cudaFree(d_delta);cudaFree(d_hist);cudaFree(d_max);
  return 0;
}
