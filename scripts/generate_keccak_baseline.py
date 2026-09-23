#!/usr/bin/env python3
"""Complete Keccak-f[1600] vectors, independent 64-bit integer implementation.
Specification: https://keccak.team/keccak_specs_summary.html (24 rounds, tables1/2).
These are permutation vectors, not claims about Ethereum padding/MPT validation.
"""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'baselines/triton'
MASK=(1<<64)-1
RC=[0x1,0x8082,0x800000000000808a,0x8000000080008000,0x808b,0x80000001,0x8000000080008081,0x8000000000008009,0x8a,0x88,0x80008009,0x8000000a,0x8000808b,0x800000000000008b,0x8000000000008089,0x8000000000008003,0x8000000000008002,0x8000000000000080,0x800a,0x800000008000000a,0x8000000080008081,0x8000000000008080,0x80000001,0x8000000080008008]
ROT=[[0,1,62,28,27],[36,44,6,55,20],[3,10,43,25,39],[41,45,15,21,8],[18,2,61,56,14]]
def rol(x,n): return ((x<<n)|(x>>(64-n)))&MASK if n else x

def permute(a):
    a=list(a)
    for rc in RC:
        c=[a[x]^a[x+5]^a[x+10]^a[x+15]^a[x+20] for x in range(5)]
        d=[c[(x-1)%5]^rol(c[(x+1)%5],1) for x in range(5)]
        a=[v^d[i%5] for i,v in enumerate(a)];b=[0]*25
        for y in range(5):
            for x in range(5): b[y+5*((2*x+3*y)%5)]=rol(a[x+5*y],ROT[y][x])
        a=[b[x+5*y]^((~b[(x+1)%5+5*y])&b[(x+2)%5+5*y]) for y in range(5) for x in range(5)]
        a[0]^=rc
    return a
assert permute([0]*25)[0]==0xF1258F7940E1DDE7

def limbs(a): return [v for x in a for v in [x&0xffffffff,x>>32]]
source='program keccak_permutation\nuse std.crypto.keccak256\nuse vm.core.convert\nfn read_lane() -> keccak256.Lane { let lo = convert.as_u32(pub_read())\nlet hi = convert.as_u32(pub_read())\nkeccak256.Lane { lo: lo, hi: hi } }\nfn main() {\nlet state = keccak256.KeccakState { '+', '.join(f's{x}{y}: read_lane()' for y in range(5) for x in range(5))+' }\nlet out = keccak256.keccak_f1600(state)\n'+''.join(f'pub_write(convert.as_field(out.s{x}{y}.{part}))\n' for y in range(5) for x in range(5) for part in ['lo','hi'])+'}\n'
prefix=' '.join(f'read_io 1 push {i} write_mem 1 pop 1' for i in range(50))+' call std_crypto_keccak256__keccak_f1600 '+' '.join(f'push {i} read_mem 1 pop 1 write_io 1' for i in range(50))+' halt'
for name,values in [('zero',[0]*25),('lanes',[(i+1)*0x0102030405060708&MASK for i in range(25)])]:
 d=ROOT/'fixtures'/f'keccak-{name}';d.mkdir(exist_ok=True);(d/'struct.tri').write_text(source)
 (d/'main.tri').write_text('program keccak_ram_permutation\nuse std.crypto.keccak256\nuse vm.io.mem\nuse vm.core.convert\nfn main() {\nfor i in 0..50 bounded 50 { mem.write(2000 + convert.as_field(i),pub_read()) }\nkeccak256.keccak_f1600_in_ram(2000,3000)\nfor i in 0..50 bounded 50 { pub_write(mem.read(2000 + convert.as_field(i))) }\n}\n')
 (d/'vector.bench.toml').write_text(f'source = "main.tri"\nhand = "../../std/crypto/keccak256.tasm"\ninput = {limbs(values)}\noutput = {limbs(permute(values))}\nmax_cycles = 1000000\nreference = "Independent 64-bit integer Keccak-f[1600] per https://keccak.team/keccak_specs_summary.html, caller-owned RAM API, all24 rounds/all25 lanes (50U32 outputs); not a padding or Ethereum-trie test."\nhand_prefix = "{prefix}"\n')

# Independent RAM assembly: U32 limb operations, explicit scratch, no compiler
# output. The Python oracle above instead works on whole 64-bit integers.
def ld(a): return f'push {a} read_mem 1 pop 1'
def st(a): return f'push {a} write_mem 1 pop 1'
def copy(src,dst): return [f'{ld(src+i)} {st(dst+i)}' for i in range(50)]
asm=['// Keccak-f[1600], independent U32 RAM implementation. State RAM0..49.', '// Scratch RAM1000..1251 and round constants1300..1301; no witness constants.', 'std_crypto_keccak256__theta:']
for x in range(5):
 for h in range(2): asm += [' '.join(ld(2*(x+5*y)+h) for y in range(5))+' xor xor xor xor '+st(1000+2*x+h)]
# Rotate each C[x+1] by one, using exact low/high32 split; products fit <2^33.
for x in range(5):
 j=(x+1)%5
 for h in range(2): asm += [f'{ld(1000+2*j+h)} push 2 mul split {st(1200+2*h)} {st(1201+2*h)}']
 asm += [f'{ld(1200)} {ld(1203)} xor {ld(1000+2*((x-1)%5))} xor {st(1010+2*x)}',f'{ld(1202)} {ld(1201)} xor {ld(1001+2*((x-1)%5))} xor {st(1011+2*x)}']
for i in range(25):
 for h in range(2): asm += [f'{ld(2*i+h)} {ld(1010+2*(i%5)+h)} xor {st(2*i+h)}']
asm += ['return','std_crypto_keccak256__rho:']
for y in range(5):
 for x in range(5):
  i=x+5*y;n=ROT[y][x];lo=2*i;hi=lo+1
  if n>=32: lo,hi=hi,lo;n-=32
  if n:
   for h,addr in enumerate([lo,hi]): asm += [f'{ld(addr)} push {1<<n} mul split {st(1200+2*h)} {st(1201+2*h)}']
   asm += [f'{ld(1200)} {ld(1203)} xor {st(1100+2*i)}',f'{ld(1202)} {ld(1201)} xor {st(1101+2*i)}']
  else: asm += [f'{ld(lo)} {st(1100+2*i)}',f'{ld(hi)} {st(1101+2*i)}']
asm += copy(1100,0)+['return','std_crypto_keccak256__pi:']
for y in range(5):
 for x in range(5):
  target=y+5*((2*x+3*y)%5)
  for h in range(2): asm += [f'{ld(2*(x+5*y)+h)} {st(1100+2*target+h)}']
asm += copy(1100,0)+['return','std_crypto_keccak256__chi:']+copy(0,1100)
for y in range(5):
 for x in range(5):
  for h in range(2): asm += [f'{ld(1100+2*((x+1)%5+5*y)+h)} push 4294967295 xor {ld(1100+2*((x+2)%5+5*y)+h)} and {ld(1100+2*(x+5*y)+h)} xor {st(2*(x+5*y)+h)}']
asm += ['return','std_crypto_keccak256__iota:',f'{ld(1)} xor {st(1)}',f'{ld(0)} xor {st(0)}','return','std_crypto_keccak256__keccak_round:',st(1301),st(1300),'call std_crypto_keccak256__theta call std_crypto_keccak256__rho call std_crypto_keccak256__pi call std_crypto_keccak256__chi',ld(1300),ld(1301),'call std_crypto_keccak256__iota return','std_crypto_keccak256__keccak_f1600:']
for rc in RC: asm += [f'push {rc&0xffffffff} push {rc>>32} call std_crypto_keccak256__keccak_round']
asm += ['return']
(ROOT/'std/crypto/keccak256.tasm').write_text('\n'.join(asm)+'\n')
