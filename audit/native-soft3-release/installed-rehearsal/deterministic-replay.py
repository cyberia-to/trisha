from pathlib import Path
import importlib.util,json,time
p=Path.cwd();s=importlib.util.spec_from_file_location('retention',p/'retain.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
a=p/'installed-evidence.tar.gz'; b=p/'determinism-replay.tar.gz';m.archive(b,m.selections())
size=0
with a.open('rb') as x,b.open('rb') as y:
 while block:=x.read(1048576):
  if y.read(len(block))!=block: raise ValueError('different compressed bytes')
  size+=len(block)
 if y.read(1):raise ValueError('different compressed lengths')
receipt={'status':'passed','command':'python3 -B -W error (retained inline driver in deterministic-replay.py)','archive':m.identity(a),'direct_compressed_byte_comparison':True,'compared_bytes':size,'driver':m.identity(p/'retain.py'),'original_selection_reused':True}
b.unlink();m.write_json(p/'deterministic-replay.json',receipt)
print(json.dumps(receipt,sort_keys=True))
