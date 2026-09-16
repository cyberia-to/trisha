#!/usr/bin/env python3
"""Independent arithmetic vectors for the historical custom permutation.
This is deliberately not a standard Poseidon2/security test.
"""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'baselines/triton'
P=2**64-2**32+1

def permute(state,constants):
    state=list(state);rc=iter(constants)
    for r in range(30):
        if r<4 or r>=26:
            state=[pow((x+next(rc))%P,7,P) for x in state]
            total=sum(state)%P;state=[(x+total)%P for x in state]
        else:
            state[0]=pow((state[0]+next(rc))%P,7,P)
            total=sum(state)%P;state=[((1+2**i)*x+total)%P for i,x in enumerate(state)]
    return state
source='''program custom_permutation
use std.crypto.poseidon2
use vm.core.convert
use vm.io.mem
use vm.io.io
fn main() {
'''+''.join(f'let s{i} = pub_read()\n' for i in range(8))+'''for i in 0..86 bounded 86 { mem.write(1000 + convert.as_field(i),io.divine()) }
let result = poseidon2.permute_from_ram(poseidon2.State { '''+', '.join(f's{i}: s{i}' for i in range(8))+''' },1000)
'''+''.join(f'pub_write(result.s{i})\n' for i in range(8))+'}\n'
reverse='swap 7 swap 1 swap 6 swap 1 swap 2 swap 5 swap 2 swap 3 swap 4 swap 3'
for name,values,rc in [('lanes',list(range(1,9)),list(range(1,87))),('zero',[0]*8,[i*i+7 for i in range(86)])]:
    d=ROOT/'fixtures'/f'custom-poseidon2-{name}';d.mkdir(exist_ok=True);(d/'main.tri').write_text(source)
    out='['+', '.join(f'"{x}"' for x in permute(values,rc))+']'
    (d/'vector.bench.toml').write_text(f'source = "main.tri"\nhand = "../../std/crypto/poseidon2.tasm"\ninput = {values}\nsecret = {rc}\noutput = {out}\nreference = "Independent Python modular exponentiation and explicit custom I+J/diagonal+J matrices over all eight lanes and 86 nonzero caller constants. This historical custom permutation is not standard Poseidon2 and has no cryptographic security claim."\nhand_prefix = "'+ 'read_io 1 '*8+reverse+' call __permute write_io 5 write_io 3 halt"\n')

# Verify the RAM-constant adapter used by the composed Trinity demo.
d=ROOT/'fixtures'/'custom-poseidon2-ram';d.mkdir(exist_ok=True)
(d/'main.tri').write_text('program custom_ram\nuse std.crypto.poseidon2\nuse vm.io.mem\nuse vm.core.convert\nuse vm.io.io\nfn main() { let a=pub_read() let b=pub_read() let c=pub_read() let d=pub_read()\nfor i in 0..86 bounded 86 { mem.write(1000 + convert.as_field(i),io.divine()) }\npub_write(poseidon2.hash4_to_digest(a,b,c,d,1000)) }\n')
rc=list(range(1,87));values=[11,22,33,44]
expected=permute(values+[4,0,0,0],rc)[0]
prefix=' '.join(f'divine 1 push {1000+i} write_mem 1 pop 1' for i in range(86))+' read_io 1 read_io 1 read_io 1 read_io 1 push 1000 call __poseidon2_hash4_to_digest write_io 1 halt'
(d/'vector.bench.toml').write_text(f'source = "main.tri"\nhand = "../../std/crypto/poseidon2.tasm"\ninput = {values}\nsecret = {rc}\noutput = ["{expected}"]\nreference = "Complete custom30-round RAM-constant hash4 adapter against independent modular oracle, for Trinity composition; no standard hash security claim."\nhand_prefix = "{prefix}"\n')
