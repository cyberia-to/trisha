from pathlib import Path
import subprocess,json,hashlib,sys
C=Path(__file__).resolve().parents[2]/'trisha-native-ci'
O=Path(__file__).resolve().parent
HEADS=['e3ff0b71919a956119674d9cc6f58489bd888a81','6624b97eb0c2179816f908cb90af02c4edc7d6e8']
def git(*args): return subprocess.check_output(['git',*args],cwd=C)
def tree(ref):
    return {r.split(b'\t',1)[1].decode():r.split(b'\t',1)[0].decode() for r in git('ls-tree','-rz',ref).split(b'\0') if r}
def run(name,args):
    r=subprocess.run(args,cwd=C,capture_output=True)
    (O/(name+'.stdout')).write_bytes(r.stdout); (O/(name+'.stderr')).write_bytes(r.stderr)
    commands.append({'name':name,'argv':args,'cwd':str(C),'returncode':r.returncode})
    assert r.returncode==0, name
commands=[]
subprocess.run(['git','add','--','.gitattributes'],cwd=C,check=True)
a,b=map(tree,HEADS); ancestor=git('merge-base',*HEADS).decode().strip(); old=tree(ancestor)
index=tree(git('write-tree').decode().strip())
assert set(index)==set(a)|set(b)
assert all(index.get(n)==v for n,v in a.items() if n!='.gitattributes')
incoming=[n for n,v in b.items() if old.get(n)!=v and n!='.gitattributes']
assert all(index.get(n)==b[n] for n in incoming)
assert all(index.get(n)==v for n,v in b.items() if n.startswith('audit/'))
attrs=(C/'.gitattributes').read_bytes(); lines=attrs.decode().splitlines()
for h in HEADS: assert set(git('show',h+':.gitattributes').decode().splitlines())<=set(lines)
assert lines[-1]=='/audit/whole-self-build-ci/retention-hardening/gh-pagination-help.stdout -text -whitespace'
run('diff-check',['git','diff','--cached','--check'])
run('branch-diff-check',['git','diff','--check',ancestor])
run('actionlint',[str(C.parents[2]/'native-proof-ci/actionlint-1.7.12/actionlint')])
for name in ['test_final_native_gate','test_transport_native_rehearsal','test_whole_self_build','test_whole_v2']:
    run(name,[sys.executable,'-B','-W','error','scripts/'+name+'.py'])
protected={}
for n in sorted(a):
    if n.startswith('.github/final-package') or n in ['scripts/native-candidate.py','scripts/native-rehearsal-local.py','scripts/native-rehearsal-macos-floor.py','scripts/prepare-native-rehearsal.py','scripts/transport-native-rehearsal.py','scripts/final-source-impact.py','scripts/check-installed-host-ceiling.py','scripts/inherit-full-baselines.py']:
        assert index[n]==a[n]
        protected[n]={'blob':a[n].split()[-1],'sha256':hashlib.sha256((C/n).read_bytes()).hexdigest()}
result={'status':'passed','parents':HEADS,'merge_base':ancestor,'parent_entries':[len(a),len(b)],'merged_entries':len(index),'preserved_feature_entries':len(a)-1,'preserved_incoming_changed_entries':len(incoming),'every_incoming_audit_blob_preserved':True,'only_modified_existing_feature_path':'.gitattributes','attributes_sha256':hashlib.sha256(attrs).hexdigest(),'staged_tree':git('write-tree').decode().strip(),'protected':protected,'commands':commands,'push_scope':'All four final-package selectors and workflows unchanged from premerge HEAD; their push paths cannot activate. Incoming whole-proof workflows restrict pushes to test/0.4-whole-self-build-ci.'}
(O/'receipt.json').write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps({'status':'passed','tree':result['staged_tree'],'commands':len(commands),'preserved_feature_entries':len(a)-1,'preserved_incoming_changed_entries':len(incoming)}))
