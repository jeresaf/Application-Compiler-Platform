-- Target 0.1 invocation schema -> target 0.2 delivery/job schema.
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
