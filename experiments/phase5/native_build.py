"""Compile native worker adapters against already-built approved grammars."""
import subprocess
from run import AREA

def build():
    cp=(AREA/'xtext/target/classpath.txt').read_text().strip()
    classpath=f'{AREA}/antlr/generated:{AREA}/tools/antlr-4.13.2-complete.jar:{AREA}/xtext/out:{cp}'
    out=AREA/'core-runtime/out';out.mkdir(exist_ok=True)
    subprocess.run(['javac','-cp',classpath,'-d',str(out),str(AREA/'core-runtime/Canonical.java'),str(AREA/'native/NativeWorker.java')],check=True)
if __name__=='__main__':build()
