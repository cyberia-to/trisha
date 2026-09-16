#!/usr/bin/env python3
"""Hand RAM algorithms for signature encoding, scalar range and exact low-S.
No elliptic-curve verification is claimed by this curve-agnostic helper module.
"""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'baselines/triton'
A=4100000; B=A+8; ORDER=A+16; S=A+24; R=A+32; ADDR=A+40

def ld(a): return f'push {a} read_mem 1 pop 1'
def st(a): return f'push {a} write_mem 1 pop 1'
def load(a): return f'push {a} call __load_u256'
def store(a): return f'push {a} call __store_u256'
a=['// Independent RAM reference: exact U256 encoding, range validation and low-S.','__store_u256:',st(ADDR)]
for i in reversed(range(8)): a += [f'{ld(ADDR)} push {i} add write_mem 1 pop 1']
a += ['return','__load_u256:',st(ADDR)]
for i in range(8): a += [f'{ld(ADDR)} push {i} add read_mem 1 pop 1']
a += ['return','__is_zero:']
# Sum of eight U32 limbs cannot wrap the Goldilocks modulus.
a += ['add']*7+['push 0 eq return','__lt256:',store(B),store(A),'call __cmp7 return']
for i in reversed(range(8)):
 a += [f'__cmp{i}:']
 if i: a += [f'{ld(A+i)} {ld(B+i)} eq skiz call __cmp{i-1}',f'{ld(A+i)} {ld(B+i)} eq skiz return']
 a += [f'{ld(B+i)} {ld(A+i)} lt return']
for public,op in [('read','read_io'),('divine','divine')]:
 a += [f'std_crypto_ecdsa__{public}_u256:']
 for _ in range(8): a += [f'{op} 1 split swap 1 push 0 eq assert']
 a += ['return',f'std_crypto_ecdsa__{public}_signature:',f'call std_crypto_ecdsa__{public}_u256 call std_crypto_ecdsa__{public}_u256 return']
a += ['std_crypto_ecdsa__valid_range:',store(ORDER),store(S),store(R),load(R),'call __is_zero push 0 eq',load(S),'call __is_zero push 0 eq mul',load(R),load(ORDER),'call __lt256 mul',load(S),load(ORDER),'call __lt256 mul return','std_crypto_ecdsa__is_low_s:',store(ORDER),store(S),'pop 5 pop 3']
for i in range(8):
 a += [f'push 2 {ld(ORDER+i)} div_mod pop 1']
 if i<7: a += [f'{ld(ORDER+i+1)} push 1 and push 2147483648 mul add']
 a += [st(ORDER+i)]
a += [load(S),'call __is_zero push 0 eq',load(ORDER),load(S),'call __lt256 push 0 eq mul return','std_crypto_ecdsa__write_u256:',store(R)]
for i in range(8): a += [f'{ld(R+i)} write_io 1']
a += ['return','std_crypto_ecdsa__write_signature:',store(S),'call std_crypto_ecdsa__write_u256',load(S),'call std_crypto_ecdsa__write_u256 return']
(ROOT/'std/crypto/ecdsa.tasm').write_text('\n'.join(a)+'\n')

def limbs(n): return [(n>>(32*i))&0xffffffff for i in range(8)]
order=0xfffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141
samples=[('half',1,order//2,order),('high',1,order//2+1,order),('zero',1,0,order),('order',1,order,order),('invalid-r',order,1,order),('cross-limb',1,(1<<128)//2,(1<<128)+1),('even-order',1,5,10)]
source='''program ecdsa_scalar_policy
use std.crypto.ecdsa
fn flag(b: Bool) -> Field { if b { 1 } else { 0 } }
fn main() {
    let sig = ecdsa.read_signature()
    let ord = ecdsa.read_signature()
    let order = ord.r
    pub_write(flag(ecdsa.valid_range(sig,order)))
    pub_write(flag(ecdsa.is_low_s(sig,order)))
    ecdsa.write_signature(sig)
}
'''
# The second signature record provides order in r and an explicit zero padding s.
# Entire original signature is written back to verify limb ordering and no truncation.
for name,r,s,n in samples:
 d=ROOT/'fixtures'/f'ecdsa-{name}';d.mkdir(exist_ok=True);(d/'main.tri').write_text(source)
 # Store input r/s explicitly: first store top s atS, then r atR.
 prefix='call std_crypto_ecdsa__read_signature '+store(S)+' '+store(R)+' call std_crypto_ecdsa__read_signature pop 5 pop 3 '+store(ORDER)
 prefix+=' '+load(R)+' '+load(S)+' '+load(ORDER)+' call std_crypto_ecdsa__valid_range write_io 1'
 prefix+=' '+load(R)+' '+load(S)+' '+load(ORDER)+' call std_crypto_ecdsa__is_low_s write_io 1'
 prefix+=' '+load(R)+' '+load(S)+' call std_crypto_ecdsa__write_signature halt'
 (d/'vector.bench.toml').write_text(f'source = "main.tri"\nhand = "../../std/crypto/ecdsa.tasm"\ninput = {limbs(r)+limbs(s)+limbs(n)+[0]*8}\noutput = {[int(0<r<n and 0<s<n),int(0<s<=n//2)]+limbs(r)+limbs(s)}\nreference = "Python exact integer range and low-S boundary plus complete signature limb roundtrip; curve-agnostic scalar policy, not ECDSA curve verification."\nhand_prefix = "{prefix}"\n')
# An oversized limb must fail range checking; truncation is not normalization.
d=ROOT/'fixtures'/'ecdsa-oversized-limb';d.mkdir(exist_ok=True);(d/'main.tri').write_text(source)
invalid=[1<<32]+[0]*7+limbs(1)+limbs(order)+[0]*8
(d/'vector.bench.toml').write_text(f'source = "main.tri"\nhand = "../../std/crypto/ecdsa.tasm"\ninput = {invalid}\noutput = []\nexpect_failure = true\nreference = "A 2^32 input limb must be rejected by both signature decoders, never truncated to U32."\nhand_prefix = "{prefix}"\n')
