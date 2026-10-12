"""Prepare existing approved fixture provisioning on fresh sealed 0.4 projects only."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tooling'))
from invocation_reference_tests import source
from phase6_reference_tests import seed_sql,symbol

def prepare(projects):
 for domain in ('payment','case-management'):
  original=source(domain)
  seed=original[:original.index('    @Test void exactApprovedInvocation')]
  seed=seed.replace('class InvocationCoreTest','class InventorySeedTest').replace('acp_phase6_execution_test','acp_retained_inventory').replace('flyway.clean(); flyway.migrate();','flyway.migrate();')
  start=original.index('    void insert(String id)');end=original.index('    @Test void unicodeOrder',start)
  seed+=original[start:end]
  statements=seed_sql(domain)
  extras=[statements[1].replace("'tenant-one'","'tenant-two'").replace("'fixture:operator'","'fixture:operator-two'"),statements[2].replace("'tenant-one'","'tenant-two'").replace("'fixture:operator'","'fixture:operator-two'").replace("'fixture-resource'","'retained-tenant-two'")]
  if domain=='payment':extras.append(statements[3].replace("'tenant-one'","'tenant-two'").replace("'fixture:operator'","'fixture:operator-two'").replace("'fixture-resource'","'retained-tenant-two'"))
  seed+='    @Test void retainedSyntheticReferencePopulation() throws Exception {\n'
  seed+='        insert("retained-same-tenant");\n'
  seed+='        tx.execute(s -> {'+''.join('jdbc.execute('+json.dumps(sql)+');' for sql in extras)+'return null;});\n'
  seed+='        assertThrows(RuntimeException.class,()->inv.'+symbol('UC-TASK','v')+'(0,invocation("forbidden"),"cross-tenant",identity("tenant-two","fixture:operator-two")));\n'
  seed+='        inv.'+symbol('UC-TASK','v')+'(0,invocation("inventory completed 🦋"),"inventory-reference-call",identity("tenant-one","fixture:operator"));\n'
  seed+='        assertEquals(3,jdbc.queryForObject("SELECT count(*) FROM '+symbol('ENT-PAYMENT' if domain=='payment' else 'CASE','e')+'",Integer.class));\n    }\n}\n'
  path=projects/domain/'backend/src/test/java/acp/generated/InventorySeedTest.java'
  path.parent.mkdir(parents=True,exist_ok=True)
  path.write_text(seed)
if __name__=='__main__':prepare(Path(sys.argv[1]).resolve())
