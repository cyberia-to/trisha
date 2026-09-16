"""Independent finite-field matrix application for the hand benchmark.

apply_single_gate() returns assembly defining __apply_single_gate, with eleven
source-order words: state_addr, n, target, g00.re/im, g01.re/im, g10.re/im,
g11.re/im. It returns nothing. State is U32-addressed, 1 <= n <= 12,
target < n. All bounds precede state mutation. Benchmark-private scratch
[2**40, 2**40 + 64) is clobbered; it cannot overlap the accepted state buffer.
No normalization, unitarity or physical quantum behavior is claimed.
"""
BASE = 1 << 40

def apply_single_gate():
    def r(i): return f'push {BASE+i} read_mem 1 pop 1'
    def w(i): return f'push {BASE+i} write_mem 1 pop 1'
    def c(n): return f'push {n}'
    def add(a,b): return f'{a} {b} add'
    def mul(a,b): return f'{a} {b} mul'
    def neg(a): return f'{a} push -1 mul'
    def put(i,v): return f'{v} {w(i)}'
    def u32(v): return f'{v} split swap 1 push 0 eq assert pop 1'
    # args 0..10, size 11, bit 12, counter 13, amplitude addresses 14,15,
    # old amplitudes 16..19; writes only after all four inputs were copied.
    code=['__apply_single_gate:', ' '.join(w(i) for i in reversed(range(11))),
          u32(r(0)), u32(r(1)), u32(r(2)),
          f'push 13 {r(1)} lt assert',f'{r(1)} {r(2)} lt assert',
          put(11,c(1)),put(13,c(0)), 'call __qram_size',
          u32(add(add(r(0),mul(r(11),c(2))),c(-1))),
          put(12,c(1)),put(13,c(0)), 'call __qram_bit',
          put(13,c(0)), 'call __qram_apply', 'return']
    for label,limit,value in [('size',1,11),('bit',2,12)]:
        code += [f'__qram_{label}:',f'{r(limit)} {r(13)} lt push 0 eq skiz return',
                 put(value,mul(r(value),c(2))),put(13,add(r(13),c(1))),'recurse']
    code += ['__qram_apply:', f'{r(11)} {r(13)} lt push 0 eq skiz return',
             f'{r(13)} {r(12)} and push 0 eq skiz call __qram_pair',
             put(13,add(r(13),c(1))),'recurse','__qram_pair:',
             put(14,add(r(0),mul(r(13),c(2)))),
             put(15,add(r(14),mul(r(12),c(2))))]
    for i in range(4):
        addr=add(r(14+i//2),c(i%2))
        code += [put(16+i,addr+' read_mem 1 pop 1')]
    for row in range(2):
        g=3+4*row
        real=add(add(mul(r(g),r(16)),neg(mul(r(g+1),r(17)))),add(mul(r(g+2),r(18)),neg(mul(r(g+3),r(19)))))
        imag=add(add(mul(r(g),r(17)),mul(r(g+1),r(16))),add(mul(r(g+2),r(19)),mul(r(g+3),r(18))))
        code += [f'{real} {r(14+row)} write_mem 1 pop 1', f'{imag} {add(r(14+row),c(1))} write_mem 1 pop 1']
    return '\n'.join(code+['return'])+'\n'
