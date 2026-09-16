#!/usr/bin/env python3
"""Independent RAM-oriented implementations of the complete PLUMBv2 predicates.
No Trident compiler output is read. Normative schema: reference/plumb-v2.md.
RAM [7000000,7100000) is internal scratch; witness uses ordinary secret fields.
"""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Asm:
 def __init__(self): self.lines=[];self.defs=[];self.mem={};self.serial=0
 def e(self,s): self.lines.extend(s.splitlines())
 def slot(self,n):
  if n not in self.mem:self.mem[n]=7000000+len(self.mem)
  return self.mem[n]
 def load(self,x): self.e(f'push {x}' if isinstance(x,int) else f'push {self.slot(x)} read_mem 1 pop 1')
 def save(self,n):self.e(f'push {self.slot(n)} write_mem 1 pop 1')
 def set(self,n,x): self.load(x);self.save(n)
 def fresh(self):self.serial+=1;return f'tmp{self.serial}'
 def d(self,n):return [f'{n}_{i}' for i in range(5)]
 def read(self,n,public=False):self.e('read_io 1' if public else 'divine 1');self.save(n);return n
 def digest(self,n,public=False):
  for x in self.d(n):self.read(x,public)
  return self.d(n)
 def eq(self,a,b):self.load(a);self.load(b);self.e('eq assert')
 def deq(self,a,b):
  for x,y in zip(a,b):self.eq(x,y)
 def u32(self,x):self.load(x);self.e('split swap 1 push 0 eq assert pop 1')
 def nonzero(self,x):self.load(x);self.e('push 0 eq push 0 eq assert')
 def math(self,a,b,sub=False):
  self.load(a);self.load(b)
  if sub:self.e('push -1 mul')
  self.e('add');n=self.fresh();self.save(n);return n
 def checked(self,a,b,sub=False):n=self.math(a,b,sub);self.u32(n);return n
 def h(self,words):
  assert len(words)==10
  for x in reversed(words):self.load(x)
  self.e('hash');n=self.d(self.fresh())
  for x in n:self.save(x)
  return n
 def pair(self,a,b):return self.h(a+b)
 def zero(self,d):
  for i,x in enumerate(d):
   self.load(x);self.e('push 0 eq')
   if i:self.e('mul')
 def subroutine(self,label,fn):
  saved=self.lines;self.lines=[];self.e(label+':');fn();self.e('return');self.defs.extend(self.lines);self.lines=saved
 def when(self,condition,fn):
  label='__conditional_'+self.fresh();self.subroutine(label,fn);condition();self.e('skiz call '+label)
 def auth(self,d,optional=False):
  def check():
   self.zero(d);self.e('push 0 eq assert');s=self.digest(self.fresh());self.deq(self.h(s+[2,1,0,0,0]),d)
  if optional:self.when(lambda:(self.zero(d),self.e('push 0 eq')),check)
  else:check()
 def hook(self,x):self.when(lambda:(self.load(x),self.e('push 0 eq push 0 eq')),lambda:(self.load(x),self.e('write_io 1')))
 def output(self,words):
  for x in words:self.load(x);self.e('write_io 1')
 def seal(self,tag,id,nonce):self.output(self.h([tag,id,nonce,0,0,0,0,0,0,0]))
 def config(self,expected):
  a=[self.digest(self.fresh()) for _ in range(5)];hooks=[self.read(self.fresh()) for _ in range(5)];self.deq(self.pair(self.pair(self.pair(a[0],a[1]),self.pair(a[2],a[3])),self.pair(a[4],self.h(hooks+[2,2,0,0,0]))),expected);return a,hooks
 def index(self,id):
  idx=self.read(self.fresh());self.u32(idx);self.nonzero(id);self.eq(id,idx);self.checked(1048575,idx,True);return idx
 def tree(self,old,new,root,idx):
  for target,src in [('tree_old',old),('tree_new',new),('tree_root',root)]:
   for x,y in zip(self.d(target),src):self.set(x,y)
  self.set('tree_idx',idx)
  for _ in range(20):self.e('call __tree_step')
  self.eq('tree_idx',0);self.deq(self.d('tree_old'),self.d('tree_root'));result=self.d(self.fresh())
  for x,y in zip(result,self.d('tree_new')):self.set(x,y)
  return result
 def tree_defs(self):
  def branch(odd):
   for node in ['tree_old','tree_new']:
    a,b=self.d(node),self.d('tree_sibling');out=self.pair(b,a) if odd else self.pair(a,b)
    for x,y in zip(self.d(node),out):self.set(x,y)
  self.subroutine('__tree_even',lambda:branch(False));self.subroutine('__tree_odd',lambda:branch(True))
  def step():
   self.load(2);self.load('tree_idx');self.e('div_mod');self.save('tree_side');self.save('tree_idx');self.digest('tree_sibling');self.load('tree_side');self.e('push 0 eq skiz call __tree_even');self.load('tree_side');self.e('push 1 eq skiz call __tree_odd')
  self.subroutine('__tree_step',step)
 def coin_read(self):
  v={k:self.read(self.fresh()) for k in ['id','balance','nonce']};v['auth']=self.digest(self.fresh());v.update({k:self.read(self.fresh()) for k in ['lock','controller','locked_by','lock_data']});return v
 def coin_hash(self,v):
  for k in ['balance','nonce','lock']:self.u32(v[k])
  return self.pair(self.h([v[k] for k in ['id','balance','nonce','lock','controller','locked_by','lock_data']]+[2,1,0]),v['auth'])
 def card_read(self):
  v={k:self.read(self.fresh()) for k in ['id','owner','nonce']};v['auth']=self.digest(self.fresh());v.update({k:self.read(self.fresh()) for k in ['lock','collection','metadata','royalty']});v['creator']=self.digest(self.fresh());v['flags']=self.read(self.fresh());return v
 def card_hash(self,v):
  for k in ['nonce','lock','royalty','flags']:self.u32(v[k])
  self.checked(10000,v['royalty'],True);self.checked(31,v['flags'],True)
  return self.pair(self.h([v[k] for k in ['id','owner','nonce','lock','collection','metadata','royalty','flags']]+[2,2]),self.pair(v['auth'],v['creator']))
 def flag(self,flags,bit):self.load(flags);self.load(bit);self.e('and push 0 eq push 0 eq assert')
 def public(self,n,checked=False):v=self.read(n,True);self.u32(v) if checked else None;return v
 def roots(self):return self.digest(self.fresh(),True),self.digest(self.fresh(),True)
 def finish(self,name,ops):
  body=self.lines;self.lines=[];self.e('// Generated from the independent PLUMBv2 RAM predicate in scripts/generate_plumb_v2_baselines.py.\n// Full operation dispatch, authenticated config and same-sibling state updates.');self.read('op',True);self.u32('op');self.checked(4,'op',True)
  for i in ops:self.load('op');self.e(f'push {i} eq skiz call __op_{i}')
  self.e('halt');self.lines.extend(body);self.tree_defs();self.lines.extend(self.defs);(ROOT/f'baselines/triton/os/neptune/standards/{name}.tasm').write_text('\n'.join(self.lines)+'\n')
def coin():
 a=Asm()
 for op in range(5):
  a.e(f'__op_{op}:');old,new=a.roots()
  if op in [0,1,2]:supply=a.public('supply',True)
  else:old_supply=a.public('old_supply',True);new_supply=a.public('new_supply',True)
  if op in [0,4]:time=a.public('time',True)
  if op in [0,3,4]:amount=a.public('amount',True)
  if op==1:lock=a.public('lock',True)
  cfg=a.digest('public_config',True)
  if op==2:newcfg=a.digest('new_config',True);a.deq(old,new)
  authorities,hooks=a.config(cfg)
  if op==2:a.auth(authorities[0]);a.config(newcfg);a.hook(hooks[2]);a.output([1,supply]);a.e('return');continue
  if op==3:a.auth(authorities[3]);a.eq(new_supply,a.checked(old_supply,amount))
  v=a.coin_read();leaf=a.coin_hash(v);idx=a.index(v['id'])
  if op!=3:a.auth(v['auth']);a.auth(authorities[{0:1,1:2,4:4}[op]],True)
  if op in [0,4]:a.hook(v['controller']);a.hook(v['locked_by']);a.checked(time,v['lock'],True)
  n=v.copy();n['nonce']=a.checked(v['nonce'],1)
  if op==1:a.checked(lock,v['lock'],True);n['lock']=lock
  else:n['balance']=a.checked(v['balance'],amount,op!=3)
  if op==4:a.eq(new_supply,a.checked(old_supply,amount,True))
  if op==0:
   r=a.coin_read();rleaf=a.coin_hash(r);ridx=a.index(r['id']);a.load(idx);a.load(ridx);a.e('eq push 0 eq assert');nr=r.copy();nr['nonce']=a.checked(r['nonce'],1);nr['balance']=a.checked(r['balance'],amount);rnew=a.coin_hash(nr)
  nleaf=a.coin_hash(n);root=a.tree(leaf,nleaf,old,idx)
  if op==0:root=a.tree(rleaf,rnew,root,ridx)
  a.deq(root,new);a.hook(hooks[op]);a.seal(0,v['id'],v['nonce'])
  if op==0:a.seal(0,r['id'],r['nonce'])
  a.output([1,supply] if op in [0,1] else [2,old_supply,new_supply]);a.e('return')
 a.finish('coin',range(5))
def card():
 a=Asm()
 for op in range(5):
  a.e(f'__op_{op}:');old,new=a.roots()
  if op in [0,1,2]:count=a.public('count',True)
  else:oldcount=a.public('oldcount',True);newcount=a.public('newcount',True)
  if op==3:cap=a.public('cap',True)
  id=a.public('id')
  if op in [0,4]:time=a.public('time',True)
  if op==1:lock=a.public('lock',True)
  if op in [2,3]:metadata=a.public('metadata')
  if op==3:collection=a.public('collection')
  cfg=a.digest('config',True)
  if op==3:metacfg=a.digest('metaconfig',True)
  authorities,hooks=a.config(cfg)
  if op==2:
   def update_cfg():
    a.deq(old,new);newcfg=a.digest('newconfig',True);a.auth(authorities[0]);a.config(newcfg)
   a.when(lambda:(a.load(id),a.e('push 0 eq')),update_cfg)
  def transition():
   if op==3:
    a.auth(authorities[3]);m=[a.read(a.fresh()) for _ in range(10)];a.eq(m[5],cap);a.eq(m[7],2);a.eq(m[8],0);a.eq(m[9],0);a.deq(a.h(m),metacfg);a.eq(newcount,a.checked(oldcount,1));a.when(lambda:(a.load(cap),a.e('push 0 eq push 0 eq')),lambda:a.checked(cap,newcount,True))
    v={'id':id,'owner':a.read(a.fresh()),'auth':a.digest(a.fresh()),'creator':a.digest(a.fresh()),'royalty':a.read(a.fresh()),'flags':a.read(a.fresh()),'nonce':0,'lock':0,'metadata':metadata,'collection':collection};a.deq(v['creator'],authorities[3]);a.flag(v['flags'],16);leaf=a.h([0,0,0,0,0,0,0,0,2,0]);nleaf=a.card_hash(v);idx=a.index(id)
   else:
    v=a.card_read();leaf=a.card_hash(v);idx=a.index(v['id']);a.eq(id,v['id']);a.auth(v['auth']);n=v.copy()
    if op!=4:n['nonce']=a.checked(v['nonce'],1)
    if op!=2:a.auth(authorities[{0:1,1:2,4:4}[op]],True)
    a.flag(v['flags'],{0:1,1:8,2:4,4:2}[op])
    if op in [0,4]:a.checked(time,v['lock'],True)
    if op==0:n['owner']=a.read(a.fresh());n['auth']=a.digest(a.fresh())
    if op==1:a.checked(lock,v['lock'],True);n['lock']=lock
    if op==2:n['metadata']=metadata
    if op==4:a.eq(newcount,a.checked(oldcount,1,True));nleaf=a.h([0,0,0,0,0,0,0,0,2,0])
    else:nleaf=a.card_hash(n)
   a.deq(a.tree(leaf,nleaf,old,idx),new)
   if op!=2:a.hook(hooks[op])
   if op!=3:a.seal(5,id,v['nonce'])
   if op==0:a.output([0,id,v['owner'],n['owner'],v['royalty']])
   if op==1:a.output([1,id,lock])
   if op==2:a.output([2,id,v['metadata'],metadata])
   if op==3:a.output([3,id]+v['creator']+[collection,metadata,6,oldcount,newcount])
   if op==4:a.output([4,id,v['owner'],6,oldcount,newcount])
  if op==2:a.when(lambda:(a.load(id),a.e('push 0 eq push 0 eq')),transition);a.hook(hooks[2])
  else:transition()
  a.e('return')
 a.finish('card',range(5))
if __name__=='__main__':coin();card()

# Shared typed utility ABI; arguments and result words are declaration order,
# first coordinate deepest. This library is also exercised by Coin/Card hosts.
def shared():
 a=Asm()
 def save_args(words):
  for x in reversed(words):a.save(x)
 def result(words):
  for x in words:a.load(x)
 def config_hash():
  d=[a.d('cfg'+str(i)) for i in range(5)];hooks=['hook'+str(i) for i in range(5)];return a.pair(a.pair(a.pair(d[0],d[1]),a.pair(d[2],d[3])),a.pair(d[4],a.h(hooks+[2,2,0,0,0])))
 config_words=[x for i in range(5) for x in a.d('cfg'+str(i))]+['hook'+str(i) for i in range(5)]
 a.subroutine('__hash_config',lambda:(save_args(config_words),result(config_hash())))
 a.subroutine('__verify_config',lambda:(save_args(config_words+a.d('expected')),a.deq(config_hash(),a.d('expected'))))
 a.subroutine('__verify_auth',lambda:(save_args(a.d('authority')),a.auth(a.d('authority'))))
 a.subroutine('__is_zero',lambda:(save_args(a.d('authority')),a.zero(a.d('authority'))))
 a.subroutine('__pair',lambda:(save_args(a.d('left')+a.d('right')),result(a.pair(a.d('left'),a.d('right')))))
 a.subroutine('__empty_leaf',lambda:result(a.h([0,0,0,0,0,0,0,0,2,0])))
 a.subroutine('__tree_depth',lambda:a.load(20))
 a.subroutine('__assert_non_negative',lambda:(a.save('value'),a.u32('value')))
 a.subroutine('__next_nonce',lambda:(a.save('value'),a.u32('value'),a.load(a.checked('value',1))))
 a.subroutine('__signal_hook',lambda:(a.save('value'),a.hook('value')))
 a.subroutine('__check_index',lambda:(save_args(['id','idx']),a.u32('idx'),a.nonzero('id'),a.eq('id','idx'),a.checked(1048575,'idx',True)))
 def update():
  save_args(a.d('old')+a.d('new')+a.d('root')+['idx']);a.u32('idx');a.checked(1048575,'idx',True);result(a.tree(a.d('old'),a.d('new'),a.d('root'),'idx'))
 a.subroutine('__update_leaf',update);a.tree_defs();(ROOT/'baselines/triton/os/neptune/standards/plumb.tasm').write_text('// PLUMBv2 complete typed shared utility ABI, independently implemented in RAM.\n'+'\n'.join(a.defs)+'\n')
if __name__=='__main__':shared()
