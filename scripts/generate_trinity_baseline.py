#!/usr/bin/env python3
"""Independent RAM implementation of the Trinity arithmetic demonstration.
This preserves its 29-argument ABI and current witness checks. It is NOT TFHE,
secure private inference, or a binding quantum commitment. See fixture README.
Scratch [6000000,6011000); dependencies reserve their own documented scratch.
"""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
blocks=[]
next_slot=6010000
def alloc():
 global next_slot
 x=next_slot;next_slot+=1;return x
def R(addr):return f'push {addr} read_mem 1 pop 1'
def W(addr):return f'push {addr} write_mem 1 pop 1'
def mem(addr):return addr+' read_mem 1 pop 1'
def put(addr,val):return val+' '+addr+' write_mem 1 pop 1'
def add(a,b):return a+' '+b+' add'
def mul(a,b):return a+' '+b+' mul'
def neg(a):return a+' push -1 mul'
def C(n):return f'push {n}'
def A(n):return R(6000000+n)
def store(slot,val):return val+' '+W(slot)
def loop(name,count,body):
 slot=alloc(); i=R(slot)
 blocks.append(name+':\n'+count+' '+i+' lt push 0 eq skiz return\n'+body(i)+'\n'+store(slot,add(i,C(1)))+' recurse')
 return store(slot,C(0))+' call '+name
# Global intermediate registers independent of library scratch.
CLASS=6000030; SUM=6000031; Q=6001000
# LWE arithmetic: each ciphertext coefficient is its weighted input sum.
def linear_row(row):
 stride=add(A(7),C(1))
 def destination(coeff):return add(A(3),add(mul(row,stride),coeff))
 zero=loop('__tri_coefficients',stride,lambda coeff:put(destination(coeff),C(0)))
 def input_col(col):
  def coefficient(coeff):
   weight=mem(add(A(2),add(mul(row,A(8)),col)))
   ct=mem(add(A(0),add(mul(col,stride),coeff)))
   return put(destination(coeff),add(mem(destination(coeff)),mul(weight,ct)))
  return loop('__tri_accumulate',stride,coefficient)
 return zero+'\n'+loop('__tri_inputs',A(8),input_col)
linear=loop('__tri_neurons',A(9),linear_row)
# Generic decryption helper takes ct,secret,delta,n source order; same arithmetic
# checks as current std.fhe.lwe (high-word noise comparison, not an LWE proof).
CT=alloc();SK=alloc();DELTA=alloc();DIM=alloc();DOT=alloc();M=alloc();NOISE=alloc();HALF=alloc()
dec_loop=loop('__tri_decrypt_dot',R(DIM),lambda i:store(DOT,add(R(DOT),mul(mem(add(R(CT),i)),mem(add(R(SK),i))))))
blocks.append('__tri_decrypt:\n'+W(DIM)+' '+W(DELTA)+' '+W(SK)+' '+W(CT)+'\n'+store(DOT,C(0))+' '+dec_loop+'\n divine 1 '+W(M)+'\n'+store(NOISE,add(add(mem(add(R(CT),R(DIM))),neg(R(DOT))),neg(mul(R(M),R(DELTA)))))+'\n'+store(HALF,mul(R(DELTA),'push 2 invert'))+'\n'+R(HALF)+' split pop 1 '+R(NOISE)+' split pop 1 lt\n'+R(HALF)+' split pop 1 '+neg(R(NOISE))+' split pop 1 lt add push 0 eq push 0 eq assert\n'+R(M)+' return')
decrypt=loop('__tri_decrypt_outputs',A(9),lambda i:put(add(A(5),i),add(A(3),mul(i,add(A(7),C(1))))+' '+A(1)+' '+A(6)+' '+A(7)+' call __tri_decrypt'))
# Dense matrix, bias and table activation.
def dense_row(row):
 dest=add(A(12),row)
 def column(col):
  weight=mem(add(A(10),add(mul(row,A(9)),col)))
  return put(dest,add(mem(dest),mul(weight,mem(add(A(5),col)))))
 return put(dest,mem(add(A(11),row)))+'\n'+loop('__tri_dense_cols',A(9),column)+'\n'+put(dest,mem(add(A(13),mem(dest))))
dense=loop('__tri_dense_rows',A(9),dense_row)
sum_outputs=store(SUM,C(0))+' '+loop('__tri_sum',A(9),lambda i:store(SUM,add(R(SUM),mem(add(A(12),i)))))
# LUT sponge consumes exactly r,k for each of14*8 canonical field words.
sponge_init='\n'.join(store(Q+i,v) for i,v in enumerate([A(16),A(17),R(SUM),R(CLASS),C(4),C(0),C(0),C(0)]))
REM=alloc();QUOT=alloc();X=alloc();SS=alloc()
def sponge_round(round):
 body=[]
 for i in range(8):
  body += [store(X,add(R(Q+i),mem(add(A(20),add(mul(round,C(8)),C(i)))))),'divine 1 '+W(REM)+' divine 1 '+W(QUOT),R(X)+' '+add(mul(R(QUOT),A(19)),R(REM))+' eq assert',R(REM)+' split swap 1 push 0 eq assert pop 1',A(19)+' '+R(REM)+' lt assert',store(Q+i,mem(add(A(13),R(REM))))]
 body += [store(SS,' '.join([R(Q)]+[R(Q+i)+' add' for i in range(1,8)]))]
 body += [store(Q+i,add(R(Q+i),R(SS))) for i in range(8)]
 return '\n'.join(body)
sponge=sponge_init+'\n'+loop('__tri_sponge_rounds',C(14),sponge_round)+'\n'+R(Q)+' '+A(21)+' eq assert'
# PBS demo witness transport: underconstrained rotation/key switch is explicit.
TIDX=alloc();SRC=alloc();SIGN=alloc();POLY=alloc()
pbs=loop('__tri_test_poly',A(24),lambda i:'divine 1 '+W(TIDX)+' '+A(24)+' '+add(mul(i,A(19)),neg(mul(R(TIDX),A(24))))+' lt assert\n'+put(add(A(26),i),mem(add(A(13),R(TIDX)))))
pbs+='\n'+loop('__tri_acc_init',A(24),lambda i:put(add(A(25),i),C(0))+'\n'+put(add(A(25),add(A(24),i)),mul(mem(add(A(26),i)),A(6))))+'\n divine 1 pop 1\n'
copy=loop('__tri_monomial_copy',A(24),lambda i:put(add(A(27),i),mem(add(R(POLY),i))))
write=loop('__tri_monomial_write',A(24),lambda i:'divine 1 '+W(SRC)+' divine 1 '+W(SIGN)+'\n'+put(add(R(POLY),i),mul(mem(add(A(27),R(SRC))),R(SIGN))))
blocks.append('__tri_monomial:\n'+copy+'\n'+write+' return')
pbs+=store(POLY,A(25))+' call __tri_monomial\n'+store(POLY,add(A(25),A(24)))+' call __tri_monomial\n'
pbs+=put(A(26),mem(A(25)))+'\n'+loop('__tri_extract',A(24),lambda j:put(add(A(26),j),neg(mem(add(A(25),add(A(24),neg(j)))))))+'\n'+put(A(26),mem(A(25)))+'\n'+put(add(A(26),A(24)),mem(add(A(25),A(24))))
pbs+='\n'+loop('__tri_switch',add(A(7),C(1)),lambda i:put(add(A(23),i),'divine 1'))+'\n'+A(23)+' '+A(1)+' '+A(6)+' '+A(7)+' call __tri_decrypt '+A(28)+' eq assert'
# Independent4x4 field-matrix simulation. H on |00> equals the source's
# tensor product H|0> tensor |0>; no quantum hardware/security is implied.
quantum='\n'.join(store(Q+i,C(int(i==0))) for i in range(8))
quantum+='\n'+'\n'.join(store(Q+10+i,add(R(Q+i),R(Q+i+4)))+'\n'+store(Q+14+i,add(R(Q+i),neg(R(Q+i+4)))) for i in range(4))
quantum+='\n'+'\n'.join(store(Q+i,R(Q+10+i)) for i in range(8))
swap_last='\n'.join([store(Q+20,R(Q+4)),store(Q+21,R(Q+5)),store(Q+4,R(Q+6)),store(Q+5,R(Q+7)),store(Q+6,R(Q+20)),store(Q+7,R(Q+21))])
blocks.append('__tri_cz:\n'+store(Q+6,neg(R(Q+6)))+'\n'+store(Q+7,neg(R(Q+7)))+' return')
quantum+='\n'+swap_last+'\n'+R(CLASS)+' push 0 eq push 0 eq skiz call __tri_cz\n'+swap_last
# Difference of squared norms after final unnormalized H on first qubit.
terms=[]
for i in range(4):
 v=add(R(Q+i),R(Q+i+4));terms.append(mul(v,v))
for i in range(4):
 v=add(R(Q+i),neg(R(Q+i+4)));terms.append(neg(mul(v,v)))
quantum+='\n'+' '.join([terms[0]]+[x+' add' for x in terms[1:]])+' split pop 1 push 2147483647 swap 1 lt return'
main='__trinity:\n'+' '.join(W(6000000+i) for i in reversed(range(29)))+'\n'+linear+'\n'+decrypt+'\n'+dense+'\n'+A(12)+' '+A(9)+' call __argmax '+W(CLASS)+'\n'+R(CLASS)+' '+A(14)+' eq assert\n'+sum_outputs+'\n'+sponge+'\n'+A(16)+' '+A(17)+' '+R(SUM)+' '+R(CLASS)+' '+A(15)+' call __poseidon2_hash4_to_digest '+A(18)+' eq assert\n'+pbs+'\n'+quantum
(ROOT/'baselines/triton/std/trinity/inference.tasm').write_text('// Independent arithmetic-demo implementation; no encryption/privacy security claim.\n// Full29source-order arguments; scratch [6000000,6011000).\n'+main+'\n\n'+'\n\n'.join(blocks)+'\n')
# Independent integer oracle + fixed reference vectors (not source execution).
P=2**64-2**32+1
def custom_hash(values,constants):
 state=values+[4,0,0,0];constants=iter(constants)
 for round in range(30):
  if round<4 or round>=26:
   state=[pow((v+next(constants))%P,7,P) for v in state]
   total=sum(state)%P;state=[(v+total)%P for v in state]
  else:
   state[0]=pow((state[0]+next(constants))%P,7,P)
   total=sum(state)%P;state=[((1+2**i)*v+total)%P for i,v in enumerate(state)]
 return state[0]
def lut_hash(values,table,constants):
 state=values+[4,0,0,0];witness=[]
 for round in range(14):
  nonlinear=[]
  for lane in range(8):
   x=(state[lane]+constants[8*round+lane])%P
   q,r=divmod(x,len(table));witness.extend([r,q]);nonlinear.append(table[r])
  total=sum(nonlinear)%P;state=[(v+total)%P for v in nonlinear]
 return state[0],witness
for name,plain in [('ascending',[1,2]),('descending',[2,1])]:
 delta=2**34;table=list(range(4));rc=list(range(1,87));src=list(range(1,113))
 klass=max(range(2),key=lambda i:plain[i]);values=[5,7,sum(plain),klass]
 digest=custom_hash(values,rc);lut_digest,lut_witness=lut_hash(values,table,src)
 cells={100:3,101:plain[0]*delta+3,102:5,103:plain[1]*delta+5,200:1,210:1,211:0,212:0,213:1,600:1,601:0,602:0,603:1,700:0,701:0}
 cells.update({900+i:v for i,v in enumerate(table)})
 cells.update({1000+i:v for i,v in enumerate(rc)});cells.update({1200+i:v for i,v in enumerate(src)})
 args=[100,200,210,300,400,500,delta,1,2,2,600,700,800,900,klass,1000,5,7,digest,4,1200,lut_digest,300,1400,4,1500,1600,1700,plain[0]]
 secret=plain+lut_witness+list(range(4))+[1]+[3,P-1,0,1,1,1,2,1]*2+[7,plain[0]*delta+7,plain[0]]
 outputs=[int(klass==0),plain[0],plain[1],plain[0],plain[1],7,plain[0]*delta+7]
 init='\n'.join(f'mem.write({address},{value})' for address,value in sorted(cells.items()))
 writes='\n'.join(f'pub_write(mem.read({addr}))' for addr in [500,501,800,801,1400,1401])
 source='program trinity_demo\nuse std.trinity.inference\nuse vm.io.mem\nfn main() {\n'+init+'\nlet result: Bool = inference.trinity('+','.join(map(str,args))+')\nif result {pub_write(1)} else {pub_write(0)}\n'+writes+'\n}\n'
 prefix=' '.join(f'push {v} push {addr} write_mem 1 pop 1' for addr,v in sorted(cells.items()))+' '+' '.join(f'push {v}' for v in args)+' call __trinity write_io 1 '+' '.join(f'push {addr} read_mem 1 pop 1 write_io 1' for addr in [500,501,800,801,1400,1401])+' halt'
 d=ROOT/'baselines/triton/fixtures'/f'trinity-{name}';d.mkdir(exist_ok=True);(d/'main.tri').write_text(source)
 encode=lambda xs:'['+', '.join('"'+str(x)+'"' for x in xs)+']'
 fixture='source = "main.tri"\nhand = "../../std/trinity/inference.tasm"\nhand_libraries = ["../../std/nn/tensor.tasm", "../../std/crypto/poseidon2.tasm"]\ninput = []\nsecret = '+encode(secret)+'\noutput = '+encode(outputs)+'\nreference = "Independent integer matrix arithmetic, full custom30-round hash,14-round LUT witness oracle and explicit PBS witness transport; all29arguments. Arithmetic demonstration only: not secure TFHE/private inference or quantum commitment."\nhand_prefix = """\n'+prefix+'\n"""\n'
 (d/'vector.bench.toml').write_text(fixture)
 # Mutate the decryption witness: both programs must reject noise mismatch.
 bad=list(secret);bad[0]+=3
 (d/'wrong-witness.bench.toml').write_text(fixture.replace('secret = '+encode(secret),'secret = '+encode(bad)).replace('output = '+encode(outputs),'output = []\nexpect_failure = true'))
