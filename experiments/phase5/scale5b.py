"""Separate parse/editor measurements and bounded full semantic validation."""
import copy,json,sys,time
from pathlib import Path
from run import AREA,ROOT,command,invoke,canonical_bytes
from generate import encode
from refactor import rename_label
sys.path.insert(0,str(ROOT/'tooling/tests'))
from test_canonical import base_model,node
from validate import validate

def main():
    results={};folder=AREA/'.cache/scale5b';folder.mkdir(exist_ok=True)
    for size in (1000,10000,100000):
        # 1k is complete ACP input; larger corpora are deliberately parse-only.
        if size==1000:model=base_model(*(node(f'PARAM-{i:06d}','Parameter',{'type':{'kind':'Integer'},'value':str(i)}) for i in range(size-1)))
        else:model={'applicationId':'APP-SCALE','modelVersion':'0.2.0','snapshotId':'SCALE','nodes':[{'id':f'ENT-{i:06d}','revision':1,'kind':'Entity','name':f'Entity {i}'} for i in range(size)]}
        text=encode(model);file=folder/f'{size}.acp';file.write_text(text)
        valid=None
        if size==1000:
            start=time.perf_counter();diagnostics=validate(model,'compile');valid=(time.perf_counter()-start)*1000;assert not diagnostics,diagnostics[:2]
        results[str(size)]={'sourceBytes':len(text.encode()),'semanticValidation':{'status':'PASS','elapsedMs':valid} if valid is not None else {'status':'NOT_SUPPORTED','reason':'Exceeds accepted 2000-node/1MiB compiler bounds; synthetic declarations are parse-only.'},'candidates':{}}
        for candidate in ('antlr','langium','xtext'):
            initial=invoke(command(candidate,file,2),ACP_PARSE_ONLY='1');entry={'initialParse':initial,'localEdit':None,'nativeIncremental':'NOT_RUN','incrementalSemanticValidation':'NOT_SUPPORTED: no incremental ACP validator is implemented; full bounded validation remains authoritative.'}
            if initial['status']=='PASS':
                changed=folder/f'{size}-edit.acp';changed.write_text(text.replace('"name":','"name": ',1));entry['localEdit']=invoke(command(candidate,changed),ACP_PARSE_ONLY='1')
                entry['localEditInterpretation']='Cold full reparse of one local edit; not native incremental parsing.'
            if candidate=='langium':
                entry['nativeIncremental']=invoke(['node','--max-old-space-size=768',str(AREA/'langium/scale5b.mjs'),str(file)])
            if candidate=='xtext':
                native=invoke(command(candidate,file),ACP_EDITOR='1')
                if native.get('output'):
                    native['output'].pop('model',None);native['output'].pop('spans',None)
                entry['nativeIncremental']=native
            if size==1000:
                # A two-module label-based refactoring workspace, with native AST
                # proof in test_phase5b and source edits measured independently.
                header={k:v for k,v in model.items() if k!='nodes'}
                a={**header,'nodes':model['nodes'][:1]};b=copy.deepcopy({**header,'nodes':model['nodes'][1:]})
                for n in b['nodes']:n['basis'][0]['id']='a::DEC-ROOT'
                docs=[{'path':'a.acp','text':'module "a";\n'+encode(a).replace('\nDecision ','\nexport Decision ')},{'path':'b.acp','text':'module "b";\nimport "a";\n'+encode(b)}]
                start=time.perf_counter();updated=rename_label(docs,'a','DEC-ROOT','DEC-ROOT','Decision display label');entry['labelRenameAndReferenceUpdateMs']=(time.perf_counter()-start)*1000
                entry['updatedQualifiedReferences']=updated[1]['text'].count('a::Decision display label');assert entry['updatedQualifiedReferences']==999
                entry['dependentCrossFileEdit']='Native Langium builder above; ANTLR/Xtext scale workspace invalidation NOT_RUN.'
                start=time.perf_counter();refresh=validate(model,'compile');entry['diagnosticRefreshFullSemanticMs']=(time.perf_counter()-start)*1000;assert not refresh
            else:
                docs=[{'path':'a.acp','text':'module "a";\napplication {};\nexport Entity "ENT-TARGET" @ 1 {"name":"Original label"};\n'},
                      {'path':'b.acp','text':'module "b";\nimport "a";\napplication {};\n'+''.join(f'Entity "ENT-{i:06d}" @ 1 {{"name":"Entity {i}","data":{{"peer":ref "a::Original label" @ 1}}}};\n' for i in range(size-1))}]
                start=time.perf_counter();updated=rename_label(docs,'a','ENT-TARGET','Original label','New label');entry['labelRenameAndReferenceUpdateMs']=(time.perf_counter()-start)*1000
                entry['updatedQualifiedReferences']=updated[1]['text'].count('a::New label');assert entry['updatedQualifiedReferences']==size-1
                entry['refactoringScope']='Source-edit cost on a synthetic qualified-reference workspace; no claim of full ACP semantic validation above accepted bounds.' 
            results[str(size)]['candidates'][candidate]=entry
            (AREA/'results/phase5b/scale.json').write_text(json.dumps(results,indent=2)+'\n')
            print(size,candidate,initial['status'],flush=True)
if __name__=='__main__':main()
