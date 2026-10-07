"""Clean previous/current frontend builds, identical corpus and generated-code diff.

Prepare isolated previous dependencies per COMMANDS.md. Production pins never
change; rolling back means deleting the ignored experiment directory.
"""
import hashlib,json,subprocess,time,shutil,sys,urllib.request
from pathlib import Path
from run import AREA,ROOT,command,invoke

OLD=AREA/'.cache/evolution'
def run(args,cwd=ROOT):
    start=time.perf_counter();p=subprocess.run(list(map(str,args)),cwd=cwd,capture_output=True,text=True,timeout=600)
    return {'exitCode':p.returncode,'elapsedMs':(time.perf_counter()-start)*1000,'stdout':p.stdout[-5000:],'stderr':p.stderr[-5000:]}
def hashes(folder,extension):
    return {str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*'+extension)}
def prepare():
    for candidate,files in [('langium',['tsconfig.json','langium-config.json','Acp.langium','probe.mjs','services.mjs']),('xtext',['Acp.xtext','Generator.java','Generate.mwe2','XtextProbe.java','.antlr-generator-3.2.0-patch.jar'])]:
        folder=OLD/candidate;folder.mkdir(parents=True,exist_ok=True)
        for file in files:shutil.copyfile(AREA/candidate/file,folder/file)
    shutil.copyfile(AREA/'evolution-locks/langium-package.json',OLD/'langium/package.json')
    shutil.copyfile(AREA/'evolution-locks/langium-package-lock.json',OLD/'langium/package-lock.json')
    shutil.copyfile(AREA/'evolution-locks/xtext-pom.xml',OLD/'xtext/pom.xml')
    entry=json.loads((AREA/'evolution-locks/versions.json').read_text())['antlrPrevious']
    folder=OLD/'antlr';folder.mkdir(exist_ok=True);jar=folder/'antlr-4.13.1-complete.jar'
    if not jar.exists():
        with urllib.request.urlopen(entry['url'],timeout=90) as response:jar.write_bytes(response.read())
    if hashlib.sha256(jar.read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('ANTLR previous digest mismatch')

def main():
    cp=(AREA/'xtext/target/classpath.txt').read_text().strip();evidence={}
    for candidate,old,new in [('antlr','4.13.1','4.13.2'),('langium','4.3.0','4.4.0'),('xtext','2.43.0','2.44.0')]:
        folder=OLD/candidate;steps=[]
        if candidate=='langium':
            schema=folder/'node_modules/langium-cli/langium-config-schema.json'
            value=json.loads(schema.read_text());value['$id']='https://langium.org/schema/langium-config.json';schema.write_text(json.dumps(value))
        if candidate=='antlr':
            jar=folder/'antlr-4.13.1-complete.jar';generated=folder/'generated';generated.mkdir(exist_ok=True)
            steps.append(run(['java','-jar',jar,'-o',generated,AREA/'antlr/Acp.g4']))
            steps.append(run(['javac','-cp',f'{jar}:{cp}','-d',generated,*generated.glob('*.java'),AREA/'antlr/Probe.java']))
            oldcommand=['java','-XX:-UsePerfData','-Xmx768m','-cp',f'{generated}:{jar}:{cp}','Probe']
            before=hashes(generated,'.java');after=hashes(AREA/'antlr/generated','.java')
        elif candidate=='langium':
            steps.extend([run(['npm','run','generate'],folder),run(['npm','run','build'],folder)])
            oldcommand=['node','--max-old-space-size=768',str(folder/'probe.mjs')]
            before=hashes(folder/'generated','.ts');after=hashes(AREA/'langium/generated','.ts')
        else:
            oldcp=(folder/'target/classpath.txt').read_text().strip();out=folder/'out';out.mkdir(exist_ok=True)
            for name in ('org.acp.experiment','org.acp.experiment.ide'):(folder/'generated'/name).mkdir(parents=True,exist_ok=True)
            steps.append(run(['javac','-cp',oldcp,'-d',out,folder/'Generator.java']))
            steps.append(run(['java','-Xmx1024m','-cp',f'{out}:{oldcp}','Generator',folder/'Generate.mwe2'],folder))
            steps.append(run(['javac','-cp',oldcp,'-d',out,*list((folder/'generated').rglob('*.java')),folder/'XtextProbe.java']))
            oldcommand=['java','-XX:-UsePerfData','-Xmx768m','-cp',f'{out}:{folder}/generated/org.acp.experiment/src-gen:{oldcp}','XtextProbe']
            before=hashes(folder/'generated','.java');after=hashes(AREA/'xtext/generated','.java')
        corpus={}
        if all(s['exitCode']==0 for s in steps):
            for domain in ('payment','case-management'):
                file=AREA/f'corpora/{domain}.acp';a=invoke([*oldcommand,str(file),'1']);b=invoke(command(candidate,file))
                corpus[domain]={'oldStatus':a['status'],'newStatus':b['status'],'equalModels':a.get('output',{}).get('model')==b.get('output',{}).get('model'),'oldErrors':a.get('output',{}).get('errors'),'newErrors':b.get('output',{}).get('errors')}
        keys=set(before)|set(after);changed=sorted(k for k in keys if before.get(k)!=after.get(k))
        evidence[candidate]={'from':old,'to':new,'cleanBuild':steps,'corpus':corpus,'generatedFilesBefore':len(before),'generatedFilesAfter':len(after),'changedGeneratedFiles':changed,'generatedHashesBefore':before,'generatedHashesAfter':after,'migration':('Previous Langium 4.3.0 packaged config schema required adding $id=https://langium.org/schema/langium-config.json to run with jsonschema 1.5. Current 4.4.0 already supplies this. Initial failure preserved in evolution-first-attempt.json. One metadata edit; no grammar/adapter changes.' if candidate=='langium' else 'Same grammar and adapter sources, no migration edits. Probe display strings remain current; resolved artifact/lock identifies actual previous runtime.'),'rollback':'Production locks/pins are untouched; remove ignored .cache/evolution and regenerate with pinned commands.','status':'PASS' if corpus and all(v['equalModels'] and not v['oldErrors'] and not v['newErrors'] for v in corpus.values()) else 'FAIL'}
        (AREA/'results/phase5b').mkdir(exist_ok=True)
        (AREA/'results/phase5b/evolution.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print({k:v['status'] for k,v in evidence.items()})
    assert all(v['status']=='PASS' for v in evidence.values()), 'Controlled upgrade corpus regression'
if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    else:main()
