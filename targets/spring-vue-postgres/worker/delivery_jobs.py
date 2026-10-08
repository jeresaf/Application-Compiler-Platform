"""Target 0.2 durable delivery/scheduler schema and bounded admission."""
from model import CapabilityError

def validate(nodes):
    by={n['id']:n for n in nodes}
    for n in nodes:
        d=n['data'];k=n['kind']
        if k=='DeliveryPolicy':
            if (d['guarantee'],d['ordering'],d['windowAnchor'],d['occurrenceOrder'],d['windowSeconds'])!=('AT_LEAST_ONCE','PER_AGGREGATE','EVENT_COMMIT','COMMIT_STEP_EMISSION_SEQUENCE',3600):raise CapabilityError('DELIVERY_SUBSET_REQUIRED')
            if by[d['deduplication']['id']]['data']['windowSeconds']<d['windowSeconds']:raise CapabilityError('DELIVERY_DEDUP_WINDOW')
        if k=='Schedule' and d!={'mode':'LOCAL_DAILY','localTime':'09:00:00','timezone':'Africa/Nairobi','tzdbVersion':'2026d','gap':'SKIP','overlap':'EARLIER'}:raise CapabilityError('SCHEDULE_SUBSET_REQUIRED')
        if k=='Job':
            commands=[by[by[step['id']]['data']['operation']['id']] for step in by[d['useCase']['id']]['data']['steps']]
            if any(c['kind']!='Command' or c['data']['idempotency']!=d['idempotency'] for c in commands):raise CapabilityError('JOB_COMMAND_IDEMPOTENCY_MATCH_REQUIRED')
            if d['missedOccurrences']!='SKIP' or d['catchUp'] is not None or d['timeoutSeconds']!=30 or any(b['value']['tag']!='literal' for b in d['inputBindings']):raise CapabilityError('JOB_SUBSET_REQUIRED')

MIGRATION='''-- Target 0.1 invocation schema -> target 0.2 delivery/job schema.
-- V1 is preserved byte-for-byte. Historical occurrences lack commit proof and
-- remain LEGACY_UNPROVEN, never assigned an invented anchor or silently sent.
ALTER TABLE acp_outbox DROP CONSTRAINT acp_outbox_tenant_event_resource_aggregate_version_key;
ALTER TABLE acp_outbox ADD COLUMN operation text, ADD COLUMN operation_revision integer,
 ADD COLUMN event_revision integer, ADD COLUMN aggregate_id text, ADD COLUMN aggregate_revision integer,
 ADD COLUMN commit_sequence bigint, ADD COLUMN step_ordinal integer, ADD COLUMN emission_ordinal integer,
 ADD COLUMN commit_xid text, ADD COLUMN commit_ns numeric,
 ADD COLUMN delivery_status text NOT NULL DEFAULT 'LEGACY_UNPROVEN',
 ADD COLUMN attempts integer NOT NULL DEFAULT 0, ADD COLUMN claim_owner text;
ALTER TABLE acp_outbox ADD CONSTRAINT delivery_status_check CHECK(delivery_status IN ('LEGACY_UNPROVEN','PENDING','CLAIMED','ACKNOWLEDGED','UNSATISFIED'));
CREATE UNIQUE INDEX acp_occurrence_position ON acp_outbox(tenant,aggregate_id,resource,commit_sequence,step_ordinal,emission_ordinal) WHERE commit_sequence IS NOT NULL;
CREATE TABLE acp_delivery_attempt(occurrence text NOT NULL REFERENCES acp_outbox(id),attempt integer NOT NULL,started_ns numeric NOT NULL,finished_ns numeric,result text NOT NULL,acknowledged boolean NOT NULL DEFAULT false,PRIMARY KEY(occurrence,attempt));
CREATE TABLE acp_delivery_barrier(tenant bytea NOT NULL,aggregate_id text NOT NULL,resource bytea NOT NULL,PRIMARY KEY(tenant,aggregate_id,resource));
CREATE TABLE acp_scheduler(job text NOT NULL,revision integer NOT NULL,scope bytea NOT NULL,activation_ns numeric NOT NULL,last_ns numeric NOT NULL,last_date date NOT NULL,PRIMARY KEY(job,revision,scope));
ALTER TABLE acp_idempotency ADD COLUMN job_occurrence text;
CREATE TABLE acp_job_invocation_attempt(id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,occurrence text NOT NULL,attempt integer NOT NULL,started_ns numeric NOT NULL,completed_ns numeric,outcome text NOT NULL,failure_id text,failure_revision integer);
CREATE TABLE acp_job_charge(occurrence text NOT NULL,rate_identity bytea NOT NULL,PRIMARY KEY(occurrence,rate_identity));
CREATE TABLE acp_job_skip_range(job text NOT NULL,revision integer NOT NULL,scope bytea NOT NULL,from_ns numeric,to_ns numeric NOT NULL);
CREATE TABLE acp_job_occurrence(identity text PRIMARY KEY,job text NOT NULL,revision integer NOT NULL,schedule text NOT NULL,schedule_revision integer NOT NULL,scope bytea NOT NULL,scheduled_ns numeric NOT NULL,status text NOT NULL CHECK(status IN ('SCHEDULED','STARTED','COMPLETED','FAILED','SKIPPED','INDETERMINATE')),owner text,attempt integer NOT NULL DEFAULT 0,result bytea,UNIQUE(job,revision,schedule,schedule_revision,scope,scheduled_ns));
'''

def generated_jobs(generator):
    from typed_contracts import name,member,quoted
    methods=[]
    for job in sorted(generator.nodes.values(),key=lambda n:n['id']):
        if job['kind']!='Job':continue
        d=job['data'];uc=generator.nodes[d['useCase']['id']];steps=uc['data']['steps'];command=generator.nodes[generator.nodes[steps[0]['id']]['data']['operation']['id']]
        entity=generator.nodes[command['data']['resource']['id']];ed=entity['data']
        # Input bindings compile through the same typed expression generator.
        inp=generator.construct(uc['data']['input']['id'],d['inputBindings'])
        bindings={b['field']['id']:b['value'] for b in d['inputBindings']}
        resource_expr=generator.nodes[steps[0]['id']]['data']['resource']
        if resource_expr.get('tag')!='input':raise CapabilityError('JOB_RESOURCE_BINDING_REQUIRED')
        resource=bindings[resource_expr['field']['id']]
        if resource['tag']!='literal':raise CapabilityError('JOB_LITERAL_RESOURCE_REQUIRED')
        from model import identifier
        sql='SELECT acp_version FROM '+identifier(entity['id'],'e')+' WHERE '+identifier(ed['identity'][0]['id'],'f')+'=? AND '+identifier(ed['tenantField']['id'],'f')+'=?'
        methods.append('case '+quoted(job['id'])+' -> {var input='+inp+';long version=jdbc.queryForObject('+quoted(sql)+',Long.class,ExecutionStore.bytes('+quoted(resource['value'])+'),ExecutionStore.bytes(jwt.getClaimAsString("tenant")));yield invocations.'+member(uc['id'])+'(version,input,occurrence,jwt,'+quoted(d['retry']['id'])+');}')
    return '''package acp.generated;
import static acp.generated.Contracts.*;
import acp.infrastructure.*;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.oauth2.jwt.Jwt;
/** Exact canonical Job input bindings; caller supplies trusted configured principal. */
public final class GeneratedJobs implements JobRuntime.Invocation {
 private final JdbcTemplate jdbc;private final Invocations invocations;
 public GeneratedJobs(JdbcTemplate jdbc,Invocations invocations){this.jdbc=jdbc;this.invocations=invocations;}
 public Object execute(String job,String occurrence,Jwt jwt){return switch(job){
'''+ '\n'.join(methods)+'''
 default -> throw new IllegalArgumentException("UNKNOWN_JOB");};}
}
'''
