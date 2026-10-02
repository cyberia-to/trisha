"""Check retained exact current producer-to-consumer receipts without executing code."""
import argparse,hashlib,json
from pathlib import Path
SOURCE='734df69dc7d43467fc9ae574c7cf7b25eb9b4ec9bc08e9ca3f96b9500131f42e'
PROVENANCE='3c6f2ced084812e73f97c069169f83807fc5d389e54b581dd52f10982cd5b227'
TARGETS={'aarch64-apple-darwin','x86_64-apple-darwin','aarch64-unknown-linux-gnu','x86_64-unknown-linux-gnu','aarch64-pc-windows-msvc','x86_64-pc-windows-msvc'}
def require(ok,message):
 if not ok:raise ValueError(message)
def sha(path):
 with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def load(path):return json.loads(path.read_text())
def pair(receipt,manifest,candidate):
 observed=load(receipt);corpus=load(manifest)
 require(corpus['source_provenance_sha256']==candidate['provenance_sha256']==PROVENANCE,'source provenance differs')
 require(observed['all_checks_passed'] is True and observed['corpus_sha256']==sha(manifest),'corpus receipt identity differs')
 binaries={r['name']:r['sha256'] for r in candidate['binaries']}
 require(observed['consumer_binaries']=={k:binaries[k] for k in ['trisha','joy']},'consumer binaries differ')
 expected=[dict(args=row['args'],exit_code=row['exit_code']) for row in corpus['cases']]
 require(len(expected)==47 and observed['cases']==expected,'exact case commands or outcomes differ')
 require(sum(row['exit_code']==0 for row in expected)==18 and sum(row['exit_code']==1 for row in expected)==29,'corpus case coverage differs')
 require(observed['producer_platform']==corpus['producer_platform'],'producer platform differs')
 return dict(receipt_sha256=sha(receipt),corpus_manifest_sha256=sha(manifest),cases=47,accepted=18,rejected=29,consumer_binaries=observed['consumer_binaries'])

RULES={name+'-'+suffix:(0 if suffix=='valid' else 1,'result') for name in ('add14','identity_tree','loop4097','compiler-success','compiler-diagnostic') for suffix in ('valid','wrong-input','wrong-program','truncated','corrupt')}
RULES.update({'compiler-success-extract':(0,'program'),'compiler-diagnostic-extract':(1,'program')})
def structured_pair(receipt,manifest,candidate):
 observed=load(receipt);corpus=load(manifest);joy=next(row['sha256'] for row in candidate['binaries'] if row['name']=='joy')
 require(corpus['source_provenance_sha256']==observed['source_provenance_sha256']==candidate['provenance_sha256']==PROVENANCE,'structured source provenance differs')
 require(observed['status']=='passed' and observed['all_checks_passed'] is True and observed['corpus_sha256']==sha(manifest),'structured corpus receipt identity differs')
 require(observed['consumer_joy']['sha256']==joy and observed['producer_joy_sha256']==corpus['producer_joy_sha256'],'structured producer/consumer Joy differs')
 require(len(corpus['cases'])==27 and {row['id']:(row['expected_exit'],row['emit']) for row in corpus['cases']}==RULES,'exact structured case map differs')
 require(observed['cases']==[dict(id=row['id'],exit_code=row['expected_exit']) for row in corpus['cases']],'exact structured case outcomes differ')
 require(observed['producer_platform']==corpus['producer_platform'],'structured producer platform differs')
 commands={name:exit_code for name,(exit_code,emit) in RULES.items()};commands['compiler-success-extract-run']=0
 require(len(observed['commands'])==28 and {row['name']:row['exit_code'] for row in observed['commands']}==commands,'structured command inventory differs')
 for row in observed['commands']:
  require(row['exit_code']==row['expected_exit'],'structured command result differs')
  for stream in ('stdout','stderr'):
   expected=row[stream];path=receipt.with_suffix('')/expected['path'];require(path.is_file() and path.stat().st_size==expected['bytes'] and sha(path)==expected['sha256'],'structured raw command stream differs')
 return dict(receipt_sha256=sha(receipt),corpus_manifest_sha256=sha(manifest),cases=27,accepted=6,rejected=21,consumer_binaries={'joy':joy})

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('selection',type=Path);parser.add_argument('output',type=Path);args=parser.parse_args()
 selected=load(args.selection);spec=load(Path(selected['selector']));producers={k:Path(v) for k,v in selected['producer_results'].items()};consumers={k:Path(v) for k,v in selected['consumer_results'].items()}
 require(set(producers)==set(consumers)==set(spec['binaries'])==TARGETS,'all six producers and consumers required')
 require(spec['phase']=='verify' and spec['source_sha256']==SOURCE,'current verification selector required')
 require(len(spec['corpora'])==6 and {r['target'] for r in spec['corpora']}==TARGETS,'all six producer corpora required')
 require(spec['validation_profile']=='current-package-v1','current package profile required')
 require(len(spec['structured_corpora'])==6 and {r['target'] for r in spec['structured_corpora']}==TARGETS,'all six structured corpora required')
 metadata={};manifests={};structured_manifests={}
 for target,root in producers.items():
  candidate=load(root/'candidate.json');meta=load(root/'archive.json');metadata[target]=candidate;manifest=root/'proof-corpus/corpus.json';manifests[target]=manifest
  require(candidate['provenance_sha256']==PROVENANCE and meta['target']==target and meta['source']['source_sha256']==SOURCE,'producer source identity differs')
  require(candidate['toolchain'].startswith('rustc 1.89.0 ') and 'host: '+target+'\n' in candidate['toolchain'],'producer actual native Rust differs')
  require(sha(root/meta['archive'])==meta['sha256']==spec['binaries'][target]['sha256'],'selected binary package differs')
  corpus=next(r for r in spec['corpora'] if r['target']==target)
  require(sha(root/('proof-corpus-'+target+'.tar.gz'))==corpus['sha256'],'selected corpus package differs')
  require(load(manifest)['producer_binaries']==candidate['binaries'],'corpus producer binary inventory differs')
  structured=root/'structured-corpus/corpus.json';structured_manifests[target]=structured
  entry=next(row for row in spec['structured_corpora'] if row['target']==target)
  require(sha(root/('structured-corpus-'+target+'.tar.gz'))==entry['sha256'],'selected structured corpus package differs')
  require(load(structured)['producer_joy_sha256']==next(row['sha256'] for row in candidate['binaries'] if row['name']=='joy'),'structured producer identity differs')
 results=[]
 for consumer,root in consumers.items():
  require(not (root/'failure.txt').exists(),'consumer retained a failure')
  kit=load(root/'verified-selfhost-smoke/receipt.json');reference=load(producers[consumer]/'unpacked-selfhost-smoke/receipt.json')
  require(kit['status']=='passed' and kit['joy']['sha256']==reference['joy']['sha256'] and kit['kit_manifest']==reference['kit_manifest'],'consumer kit identity differs')
  for index,entry in enumerate(spec['corpora']):
   result=pair(root/f'verification-{index}.json',manifests[entry['target']],metadata[consumer]);results.append(dict(kind='legacy',producer=entry['target'],consumer=consumer,**result))
  for index,entry in enumerate(spec['structured_corpora']):
   result=structured_pair(root/f'structured-verification-{index}.json',structured_manifests[entry['target']],metadata[consumer]);results.append(dict(kind='structured',producer=entry['target'],consumer=consumer,**result))
 report=dict(scope='Retained current native legacy and structured corpus receipt matrices only; original container authentication and complete producer gates remain separately bound',status='passed',source_sha256=SOURCE,source_provenance_sha256=PROVENANCE,selector_sha256=sha(Path(selected['selector'])),selection_sha256=sha(args.selection),checker_sha256=sha(Path(__file__)),native_pairs=len(producers)*len(consumers),corpus_pairs=len(results),case_checks=sum(r['cases'] for r in results),pairs=results)
 with args.output.open('x') as stream:stream.write(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:report[k] for k in ['status','native_pairs','corpus_pairs','case_checks']}))
if __name__=='__main__':main()
