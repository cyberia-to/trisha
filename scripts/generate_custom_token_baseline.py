#!/usr/bin/env python3
"""Independent full canonical BFieldCodec custom-token-v2 RAM validator."""
from generate_plumb_v2_baselines import Asm,ROOT
class Token(Asm):
 def lt(self,a,b):self.load(b);self.load(a);self.e('lt')
 def bounded(self,x,maximum):self.u32(x);self.checked(maximum,x,True)
 def readat(self,offset,end,numeric=False):
  self.u32(offset);self.lt(offset,end);self.e('assert');self.load('base');self.load(offset);self.e('add read_mem 1 pop 1');v=self.fresh();self.save(v)
  if numeric:self.u32(v)
  return v
 def put(self,offset,value):self.load(value);self.load('base');self.load(offset);self.e('add write_mem 1 pop 1')
 def loop(self,label,cond,body):
  def sub():body();cond();self.e('skiz recurse')
  self.subroutine(label,sub);cond();self.e('skiz call '+label)
 def advance(self,n,delta=1):self.set(n,self.math(n,delta))
a=Token();a.e('// Complete custom-token-v2: canonical salted UTXOs, own-program selector, full issuer Digest.\n// Generated independently; no compiler output is read.')
for i in range(5):a.e(f'dup {11+i}');a.save(a.d('own')[i])
a.digest('kernel',True);a.digest('input_hash',True);a.digest('output_hash',True);a.set('seen',0)
for i in a.d('authority'):a.set(i,0)
# Canonical loader + parser are shared between input and output.
for side,base in [('input',8000000),('output',8010000)]:
 a.set('base',base)
 for x,y in zip(a.d('expected'),a.d(side+'_hash')):a.set(x,y)
 a.e('call __load_list call __sum_list');a.set(side+'_total','total')
a.nonzero('seen')
def authorize():
 a.zero(a.d('authority'));a.e('push 0 eq assert');secret=a.digest('issuer_secret');a.deq(a.h(secret+[2,3,0,0,0]),a.d('authority'))
a.when(lambda:(a.load('input_total'),a.load('output_total'),a.e('eq push 0 eq')),authorize)
a.e('halt')
def loader():
 a.read('length');a.bounded('length',4096);a.checked('length',5,True);a.set('i',0)
 def loadword():a.e('divine 1');value=a.fresh();a.save(value);a.put('i',value);a.advance('i')
 a.loop('__read_words',lambda:a.lt('i','length'),loadword)
 a.put('length',1);a.set('i',a.math('length',1));a.load(10);a.load('length');a.e('div_mod pop 1 push 1 add push 10 mul');a.save('padded')
 a.loop('__pad_words',lambda:a.lt('i','padded'),lambda:(a.put('i',0),a.advance('i')))
 a.e('sponge_init');a.set('i',0)
 def absorb():
  a.e('push 0 push 0 push 0 push 0');a.load('base');a.load('i');a.e('add sponge_absorb_mem pop 5');a.advance('i',10)
 a.loop('__absorb_words',lambda:a.lt('i','padded'),absorb);a.e('sponge_squeeze')
 for x in reversed(a.d('expected')):a.load(x);a.e('eq assert')
 a.e('pop 5')
a.subroutine('__load_list',loader)
def sumlist():
 a.eq(a.math(a.readat(3,'length',True),4),'length');a.set('utxos',a.readat(4,'length',True));a.bounded('utxos',64);a.set('u',0);a.set('cursor',5);a.set('total',0)
 def utxo():
  ul=a.readat('cursor','length',True);a.set('begin',a.math('cursor',1));a.set('end',a.math('begin',ul));a.u32('end');a.lt('end',a.math('length',1));a.e('assert');cl=a.readat('begin','end',True);a.set('coins_begin',a.math('begin',1));a.set('coins_end',a.math('coins_begin',cl));a.eq(a.math('coins_end',5),'end');a.set('coins',a.readat('coins_begin','coins_end',True));a.bounded('coins',64);a.set('coin_cursor',a.math('coins_begin',1));a.set('c',0)
  def coin():
   cl=a.readat('coin_cursor','coins_end',True);a.set('coin_begin',a.math('coin_cursor',1));a.set('coin_end',a.math('coin_begin',cl));a.u32('coin_end');a.lt('coin_end',a.math('coins_end',1));a.e('assert');sl=a.readat('coin_begin','coin_end',True);a.set('state_count',a.readat(a.math('coin_begin',1),'coin_end',True));a.eq(sl,a.math('state_count',1));a.set('type_start',a.math(a.math('coin_begin',1),sl));a.eq(a.math('type_start',5),'coin_end')
   matches=[]
   for i in range(5):
    word=a.readat(a.math('type_start',i),'coin_end');a.load(word);a.load(a.d('own')[i]);a.e('eq');n=a.fresh();a.save(n);matches.append(n)
   def condition():
    for i,x in enumerate(matches):a.load(x);a.e('mul') if i else None
   def selected():
    a.eq('state_count',7);a.eq(a.readat(a.math('coin_begin',2),'coin_end'),2);amount=a.readat(a.math('coin_begin',3),'coin_end',True);a.set('total',a.checked('total',amount));current=[a.readat(a.math('coin_begin',4+i),'coin_end') for i in range(5)]
    a.when(lambda:a.load('seen'),lambda:a.deq(current,a.d('authority')))
    def remember():
     for x,y in zip(a.d('authority'),current):a.set(x,y)
    a.when(lambda:(a.load('seen'),a.e('push 0 eq')),remember);a.set('seen',1)
   a.when(condition,selected);a.set('coin_cursor','coin_end');a.advance('c')
  a.loop('__coins',lambda:a.lt('c','coins'),coin);a.eq('coin_cursor','coins_end');a.set('cursor','end');a.advance('u')
 a.loop('__utxos',lambda:a.lt('u','utxos'),utxo);a.eq('cursor','length')
a.subroutine('__sum_list',sumlist);a.lines.extend(a.defs)
(ROOT/'baselines/triton/os/neptune/types/custom_token.tasm').write_text('\n'.join(a.lines)+'\n')
