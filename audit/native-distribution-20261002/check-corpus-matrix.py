"""Check retained exact frozen producer-to-consumer receipts without executing code."""
import argparse,hashlib,json
from pathlib import Path
SOURCE='e4bac7ff7260a5f395febc196b3e4792653e0ff81d7887d688e16ea0959aa361'
PROVENANCE='9fddb8002ebb49ad724dfeb20972066c1de0b75b22f806b5360609bb12eaaec5'
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
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('selection',type=Path);parser.add_argument('output',type=Path);args=parser.parse_args()
 selected=load(args.selection);spec=load(Path(selected['selector']));producers={k:Path(v) for k,v in selected['producer_results'].items()};consumers={k:Path(v) for k,v in selected['consumer_results'].items()}
 require(set(producers)==set(consumers)==set(spec['binaries'])==TARGETS,'all six producers and consumers required')
 require(spec['phase']=='verify' and spec['source_sha256']==SOURCE,'frozen verification selector required')
 require(len(spec['corpora'])==6 and {r['target'] for r in spec['corpora']}==TARGETS,'all six producer corpora required')
 metadata={};manifests={}
 for target,root in producers.items():
  candidate=load(root/'candidate.json');meta=load(root/'archive.json');metadata[target]=candidate;manifest=root/'proof-corpus/corpus.json';manifests[target]=manifest
  require(candidate['provenance_sha256']==PROVENANCE and meta['target']==target and meta['source']['source_sha256']==SOURCE,'producer source identity differs')
  require(candidate['toolchain'].startswith('rustc 1.89.0 ') and 'host: '+target+'\n' in candidate['toolchain'],'producer actual native Rust differs')
  require(sha(root/meta['archive'])==meta['sha256']==spec['binaries'][target]['sha256'],'selected binary package differs')
  corpus=next(r for r in spec['corpora'] if r['target']==target)
  require(sha(root/('proof-corpus-'+target+'.tar.gz'))==corpus['sha256'],'selected corpus package differs')
  require(load(manifest)['producer_binaries']==candidate['binaries'],'corpus producer binary inventory differs')
 results=[]
 for consumer,root in consumers.items():
  require(not (root/'failure.txt').exists(),'consumer retained a failure')
  kit=load(root/'verified-selfhost-smoke/receipt.json');reference=load(producers[consumer]/'unpacked-selfhost-smoke/receipt.json')
  require(kit['status']=='passed' and kit['joy']['sha256']==reference['joy']['sha256'] and kit['kit_manifest']==reference['kit_manifest'],'consumer kit identity differs')
  for index,entry in enumerate(spec['corpora']):
   result=pair(root/f'verification-{index}.json',manifests[entry['target']],metadata[consumer]);results.append(dict(producer=entry['target'],consumer=consumer,**result))
 report=dict(scope='Retained frozen native corpus receipt matrix only; original container authentication and complete producer gates remain separately bound',status='passed',source_sha256=SOURCE,source_provenance_sha256=PROVENANCE,selector_sha256=sha(Path(selected['selector'])),selection_sha256=sha(args.selection),checker_sha256=sha(Path(__file__)),native_pairs=len(results),case_checks=sum(r['cases'] for r in results),pairs=results)
 with args.output.open('x') as stream:stream.write(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:report[k] for k in ['status','native_pairs','case_checks']}))
if __name__=='__main__':main()
