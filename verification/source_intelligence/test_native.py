"""Real native semantic-resolution fixtures, independent of Canonical intent."""
import json,os,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from engineering.source_intelligence import native
from engineering.source_intelligence.model import digest

JAVA='''package sample;
interface Named { String name(); }
class Parent { int inherited=7; }
public class Example extends Parent implements Named {
 public String field="value";
 public Example() {}
 public String name(){return field;}
 static String choose(String x){return x;}
 static int choose(int x){return x;}
 void run(){String text=choose("ok"); int number=choose(2); new Example(); name();}
}
'''
TS_A='''export interface Named { name():string; }
export class Parent { inherited=7; }
export function choose(x:string):string;
export function choose(x:number):number;
export function choose(x:string|number){return x;}
'''
TS_B='''import {choose as pick,Parent,Named} from './a';
export class Child extends Parent implements Named {
 field:string='value'; constructor(){super();} name(){return this.field;}
 run(){return pick('ok');}
}
export const created=new Child();
'''

class NativeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temporary=tempfile.TemporaryDirectory(prefix='acp-phase7-native-');cls.root=Path(cls.temporary.name)
  cls.modules=Path(os.environ['ACP_SOURCE_NODE_MODULES']).absolute()
  cls.jroot=cls.root/'java';cls.jroot.mkdir();(cls.jroot/'Example.java').write_text(JAVA)
  cls.troot=cls.root/'ts';cls.troot.mkdir();(cls.troot/'a.ts').write_text(TS_A);(cls.troot/'b.ts').write_text(TS_B)
  def run_java(label):
   scratch=cls.root/label;scratch.mkdir();return native.java(cls.jroot,['Example.java'],[],scratch)
  def run_ts(label):
   scratch=cls.root/label;scratch.mkdir();return native.typescript(cls.troot,['a.ts','b.ts'],cls.modules,scratch)
  cls.run_java=staticmethod(run_java);cls.run_ts=staticmethod(run_ts)
  cls.java=run_java('j1');cls.ts=run_ts('t1')
 @classmethod
 def tearDownClass(cls):cls.temporary.cleanup()
 def test_java_native_overload_calls_are_distinct_and_exact(self):
  self.assertFalse(self.java['diagnostics']);calls=[r for r in self.java['references'] if r['kind']=='CALL' and 'choose' in str(r['native'])]
  self.assertEqual(len(calls),2);self.assertEqual({r['confidence'] for r in calls},{'KNOWN'});self.assertEqual(len({r['to'] for r in calls}),2)
  self.assertTrue(any('java.lang.String' in r['native'] for r in calls));self.assertTrue(any('choose(int)' in r['native'] for r in calls))
 def test_java_interfaces_fields_parameters_constructors_and_type_edges(self):
  self.assertTrue({'INTERFACE','CLASS','FIELD','METHOD','CONSTRUCTOR','PARAMETER'}<={r['kind'] for r in self.java['definitions']})
  self.assertTrue({'IMPLEMENTS','EXTENDS'}<={r['kind'] for r in self.java['relations']});self.assertTrue(any(r['kind']=='CONSTRUCT' and r['confidence']=='KNOWN' for r in self.java['references']))
 def test_typescript_alias_cross_file_resolution_uses_native_declarations(self):
  self.assertFalse(self.ts['diagnostics']);calls=[r for r in self.ts['references'] if r['kind']=='CALL' and 'choose' in str(r['native'])]
  self.assertEqual(len(calls),1);self.assertEqual(calls[0]['confidence'],'KNOWN');self.assertTrue(calls[0]['to'].startswith('a.ts:'))
  chosen=next(d for d in self.ts['definitions'] if d['key']==calls[0]['to']);self.assertIn('string',chosen['type']);self.assertNotIn('number',chosen['type'])
 def test_typescript_definitions_and_native_type_relationships(self):
  self.assertTrue({'IMPORT_ALIAS','INTERFACE','CLASS','FUNCTION','PROPERTY','PARAMETER','CONSTRUCTOR'}<={r['kind'] for r in self.ts['definitions']})
  self.assertEqual({r['kind'] for r in self.ts['relations']} & {'EXTENDS','IMPLEMENTS'},{'EXTENDS','IMPLEMENTS'})
 def test_java_analysis_is_deterministic(self):self.assertEqual(self.java,self.run_java('j2'))
 def test_typescript_analysis_is_deterministic(self):self.assertEqual(self.ts,self.run_ts('t2'))
 def test_ambiguous_java_overload_never_becomes_a_known_call(self):
  old=(self.jroot/'Example.java').read_text()
  try:
   (self.jroot/'Example.java').write_text(old.replace('static int choose(int x){return x;}','static Integer choose(Integer x){return x;}').replace('choose(2)','choose(null)'))
   result=self.run_java('ambiguous');self.assertTrue(result['diagnostics']);self.assertTrue(any(r['kind']=='CALL' and r['confidence']=='UNRESOLVED' for r in result['references']))
  finally:(self.jroot/'Example.java').write_text(old)
 def test_unknown_typescript_symbol_is_not_guessed_from_a_name(self):
  old=(self.troot/'b.ts').read_text()
  try:
   (self.troot/'b.ts').write_text(old.replace("pick('ok')","missing('ok')"));result=self.run_ts('missing')
   self.assertTrue(result['diagnostics']);self.assertTrue(any(r['kind']=='CALL' and r['confidence']=='UNRESOLVED' and r['to'] is None for r in result['references']))
  finally:(self.troot/'b.ts').write_text(old)
 def test_unsupported_or_broken_java_syntax_is_diagnostic(self):
  old=(self.jroot/'Example.java').read_text()
  try:
   (self.jroot/'Example.java').write_text('public class Example { void broken( ??? }');result=self.run_java('broken');self.assertTrue(result['diagnostics'])
  finally:(self.jroot/'Example.java').write_text(old)

if __name__=='__main__':unittest.main()
