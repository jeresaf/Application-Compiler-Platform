"""Read-only native Source Intelligence; no intent edits or semantic authorization."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from engineering.source_intelligence.analysis import prepare,analyze
from engineering.source_intelligence.model import require,sha,encode,impact,compare,validate

def load(path,pin):
    raw=Path(path).read_bytes();require(sha(raw)==pin,'MODEL_FILE_DIGEST');return validate(json.loads(raw))

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare');p.add_argument('--workspace',type=Path,required=True);p.add_argument('--domain',choices=['payment','case-management'],required=True)
    a=sub.add_parser('analyze');a.add_argument('--root',type=Path,required=True);a.add_argument('--binding',type=Path,required=True);a.add_argument('--binding-sha256',required=True);a.add_argument('--maven-repo',type=Path,required=True);a.add_argument('--node-modules',type=Path,required=True);a.add_argument('--scratch',type=Path);a.add_argument('--output',type=Path,required=True)
    i=sub.add_parser('impact');i.add_argument('--root',type=Path,required=True);i.add_argument('--model',type=Path,required=True);i.add_argument('--model-sha256',required=True);group=i.add_mutually_exclusive_group(required=True);group.add_argument('--symbol');group.add_argument('--semantic')
    d=sub.add_parser('compare');d.add_argument('--before',type=Path,required=True);d.add_argument('--before-sha256',required=True);d.add_argument('--after',type=Path,required=True);d.add_argument('--after-sha256',required=True)
    args=parser.parse_args()
    if args.command=='prepare':result=prepare(args.workspace,args.domain)
    elif args.command=='analyze':
        require(not args.output.resolve().is_relative_to(args.root.resolve()),'READ_ONLY_ANALYSIS_OUTPUT');require(not args.output.exists(),'OUTPUT_COLLISION')
        result=analyze(args.root,args.binding,args.binding_sha256,maven_repo=args.maven_repo,node_modules=args.node_modules,scratch=args.scratch)
        with args.output.open('xb') as stream:stream.write(encode(result))
        result={'model':str(args.output),'fileSHA256':sha(args.output.read_bytes()),'digest':result['digest'],'completeness':result['completeness'],'drift':result['drift']}
    elif args.command=='impact':result=impact(load(args.model,args.model_sha256),args.root,symbol=args.symbol,semantic=args.semantic)
    else:result=compare(load(args.before,args.before_sha256),load(args.after,args.after_sha256))
    print(json.dumps(result,sort_keys=True,indent=2))

if __name__=='__main__':main()
