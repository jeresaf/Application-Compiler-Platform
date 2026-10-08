"""Exact classified observability and terminal CLOSED_COMMIT target subset."""
import json
from decimal import Decimal
from model import CapabilityError,identifier,encoded

MIGRATION='''CREATE TABLE acp_lifecycle_anchor (
 lifecycle text NOT NULL,revision integer NOT NULL,tenant bytea NOT NULL,resource bytea NOT NULL,
 entity text NOT NULL,machine text NOT NULL,machine_revision integer NOT NULL,closing_state text NOT NULL,state_revision integer NOT NULL,
 anchor_xid text,anchor_ns numeric,root_version bigint NOT NULL,last_ns numeric,
 status text NOT NULL,attempt_xid text,completed_ns numeric,
 PRIMARY KEY(lifecycle,revision,tenant,resource));
CREATE TABLE acp_lifecycle_attempt (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,lifecycle text NOT NULL,revision integer NOT NULL,tenant bytea NOT NULL,resource bytea NOT NULL,
 observed_ns numeric NOT NULL,result text NOT NULL,action_xid text);
CREATE TABLE acp_lifecycle_release_audit (
 lifecycle text NOT NULL,revision integer NOT NULL,tenant bytea NOT NULL,resource bytea NOT NULL,
 hold text NOT NULL,hold_revision integer NOT NULL,permission text NOT NULL,permission_revision integer NOT NULL,subject bytea NOT NULL,
 action_xid text NOT NULL);
'''

def validate(nodes):
    by={n['id']:n for n in nodes}
    expected={'PUBLIC':('WRITE','NONE'),'INTERNAL':('WRITE','NONE'),'SENSITIVE':('READ_WRITE','MASK'),'SECRET':('READ_WRITE','OMIT')}
    for n in nodes:
        d=n['data'];kind=n['kind']
        if kind=='DataClassification':
            if d['level'] not in expected or (d['audit'],d['redaction'])!=expected[d['level']] or d['export']!='DENY' or d['redactionScope']!='NON_DOMAIN_OBSERVABILITY' or d['encryptAtRest'] is not True or d['encryptInTransit'] is not True:raise CapabilityError('CLASSIFICATION_SUBSET_REQUIRED')
        if kind=='DataLifecycle':
            a=d['anchor'];machine=by[a['machine']['id']]
            if a['kind']!='CLOSED_COMMIT' or a['instant']!='COMMITTED_ENTRY' or a['terminal'] is not True or len(a['states'])!=1 or machine['data']['resource']!=d['resource']:raise CapabilityError('LIFECYCLE_TERMINAL_COMMIT_REQUIRED')
            ids={r['id'] for r in a['states']}
            if any(not by[r['id']]['data']['terminal'] for r in a['states']) or any(t['kind']=='Transition' and t['data']['machine']==a['machine'] and t['data']['from']['id'] in ids for t in nodes):raise CapabilityError('LIFECYCLE_REOPEN_UNSUPPORTED')
            if not any(x['kind']=='Aggregate' and x['data']['root']==d['resource'] for x in nodes):raise CapabilityError('LIFECYCLE_AGGREGATE_ROOT_REQUIRED')
            e=by[d['resource']['id']]['data']
            if len(e['identity'])!=1 or not e.get('tenantField') or e['tenancy']!='SCOPED':raise CapabilityError('LIFECYCLE_ONE_ROOT_REQUIRED')
        if kind=='Retention':
            if d['trigger']!='CLOSED' or type(d['minimumSeconds']) is not int or not 0<=d['minimumSeconds']<=2147483647:raise CapabilityError('RETENTION_CLOSED_INTEGER_REQUIRED')
        if kind=='DeletionPolicy':
            if d['trigger']!='CLOSED' or d['mode']!='ANONYMIZE' or d['holdBehavior']!='BLOCK' or type(d['afterSeconds']) is not int or not 0<=d['afterSeconds']<=2147483647:raise CapabilityError('DELETION_ANONYMIZE_REQUIRED')
            for effect in d['anonymizationEffects']:
                f=by[effect['field']['id']]['data']
                if effect['action']=='REMOVE':
                    t=f['type'];t=t['item'] if t['kind']=='Nullable' else t
                    if not f['optional'] or t['kind']!='String':raise CapabilityError('DISPOSAL_OPTIONAL_STRING_REQUIRED')
                elif effect['action']=='REPLACE':
                    replacement=effect['replacement']
                    if replacement!={'type':{'kind':'Money','currency':'UGX','precision':18,'scale':2,'rounding':'REJECT'},'value':'1'} or f['type']!=replacement['type']:raise CapabilityError('DISPOSAL_EXACT_MONEY_CONSTANT_REQUIRED')
                else:raise CapabilityError('DISPOSAL_EFFECT_UNSUPPORTED')
        if kind=='LegalHold':
            if d['releaseMode']!='CURRENT_LIFECYCLE_ACTION' or d['condition']!={'tag':'literal','type':{'kind':'Boolean'},'value':True}:raise CapabilityError('HOLD_LITERAL_TRUE_CURRENT_ACTION_REQUIRED')

def migration(nodes):
    by={n['id']:n for n in nodes};sql=MIGRATION
    for life in sorted((n for n in nodes if n['kind']=='DataLifecycle'),key=lambda n:n['id']):
        d=life['data'];e=by[d['resource']['id']]['data'];a=d['anchor'];state=a['states'][0]
        # IDs are validated semantic IDs, quote SQL literal values explicitly.
        q=lambda s:"'"+s.replace("'","''")+"'"
        sql+=f"INSERT INTO acp_lifecycle_anchor(lifecycle,revision,tenant,resource,entity,machine,machine_revision,closing_state,state_revision,root_version,status) SELECT {q(life['id'])},{life['revision']},{identifier(e['tenantField']['id'],'f')},{identifier(e['identity'][0]['id'],'f')},{q(d['resource']['id'])},{q(a['machine']['id'])},{a['machine']['revision']},{q(state['id'])},{state['revision']},acp_version,'LEGACY_UNPROVEN' FROM {identifier(d['resource']['id'],'e')} WHERE acp_state={q(state['id'])};\n"
    return sql

def requirements(nodes):
    items=[]
    for n in sorted(nodes,key=lambda n:n['id']):
        kinds=[]
        if n['kind']=='DataClassification':kinds=['ENCRYPTION_AT_REST','TLS_IN_TRANSIT','KEY_MANAGEMENT','BACKUP_ENCRYPTION','OBSERVABILITY_EXPORTER_NON_DISCLOSURE']
        if n['kind'] in ('DataLifecycle','DeletionPolicy','Retention'):kinds=['BACKUP_LIFECYCLE','WAL_REPLICA_RETENTION','PRIVACY_DESTRUCTION_VERIFICATION','CLASSIFIED_HISTORICAL_EVENT_IDEMPOTENCY_STORAGE']
        for requirement in kinds:items.append({'origin':{'id':n['id'],'revision':n['revision']},'requirement':requirement,'status':'OUTSTANDING'})
    return {'contractVersion':'1.0.0','scope':'Deployment obligations, never evidence of satisfaction; active-state anonymization does not erase backups/WAL/replicas or immutable semantic history','requirements':items}

def actions(generator):
    g=generator;by=g.nodes
    from typed_contracts import name,member,quoted
    cases=[];locks=[]
    for life in sorted((n for n in by.values() if n['kind']=='DataLifecycle'),key=lambda n:n['id']):
        d=life['data'];entity=d['resource']['id'];e=by[entity]['data'];policy=by[d['deletion']['id']]['data'];table=identifier(entity,'e');identity=identifier(e['identity'][0]['id'],'f');tenant=identifier(e['tenantField']['id'],'f')
        lock=f'var row=store.lock({quoted(table)},{quoted(identity)},{quoted(tenant)},resource,jwt,{g.row_reader(entity)});'
        locks.append(f'case {quoted(life["id"])} -> {{ {lock} yield new LifecycleRuntime.Snapshot({g.semantic(entity,"row.value()")},row.version(),row.state()); }}')
        lines=[lock,'var staged=row.value();']
        effects={effect['field']['id']:effect for effect in policy['anonymizationEffects']}
        args=[]
        for f in g.c.fields(entity):
            effect=effects.get(f['id']);value='staged.'+member(f['id'])+'()'
            if effect:
                if effect['action']=='REMOVE':value='Slot.absent()'
                else:value=g.expression({'tag':'literal',**effect['replacement']})
            args.append(value)
        lines.append('staged=new '+name(entity)+'('+','.join(args)+');')
        for inv in sorted((n for n in by.values() if n['kind']=='Invariant' and n['data']['resource']==d['resource'] and 'WRITE' in n['data']['enforcement']),key=lambda n:n['id']):lines.append('if(!Boolean.TRUE.equals('+g.expression(inv['data']['predicate'],pre='staged')+'))throw new IllegalArgumentException("POST_DISPOSAL_INVARIANT");')
        setters=[];values=[]
        for fid,effect in sorted(effects.items()):
            f=by[fid]['data'];setters.append(identifier(fid,'f')+'=?');values.append('null' if effect['action']=='REMOVE' else g.db_value(f['type'],g.field('staged',fid)))
            if f['optional'] and f['type']['kind']=='Nullable':setters.append(identifier(fid,'present')+'=?');values.append('false')
        sql=f'UPDATE {table} SET '+','.join(setters)+f',acp_version=acp_version+1 WHERE {identity}=? AND {tenant}=? AND acp_version=?'
        lines.append('store.update('+quoted(sql)+','+','.join(values+['ExecutionStore.bytes(resource)','ExecutionStore.bytes(jwt.getClaimAsString("tenant"))','row.version()'])+');')
        lines.append('store.audit('+quoted(life['id'])+',resource,jwt);')
        lines.append(g.classified_audit(life['id'],entity,'WRITE','resource',effects))
        cases.append('case '+quoted(life['id'])+' -> {'+'\n'.join(lines)+'}')
    return '''package acp.generated;
import static acp.generated.Contracts.*;
import acp.infrastructure.*;
import org.springframework.security.oauth2.jwt.Jwt;
/** Compiled exact disposal effects and complete staged WRITE invariant checks. */
public final class LifecycleActions implements LifecycleRuntime.Actions {
 private final ExecutionStore store;
 public LifecycleActions(ExecutionStore store){this.store=store;}
 public LifecycleRuntime.Snapshot lock(String lifecycle,String resource,Jwt jwt){return switch(lifecycle){'''+ '\n'.join(locks)+''' default -> throw new IllegalArgumentException("LIFECYCLE_REQUIRED");};}
 public void apply(String lifecycle,String resource,Jwt jwt){switch(lifecycle){'''+ '\n'.join(cases)+''' default -> throw new IllegalArgumentException("LIFECYCLE_REQUIRED");}}
}
'''
