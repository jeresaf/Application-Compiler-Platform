"""External disposable test adapter. Never generated into production source."""
import json,hashlib
from engineering.documents.run import adapter_source as document_adapter
PREFIX='j_'+hashlib.sha256(b'JOB-INTEGRITY').hexdigest()[:24]

def adapter_source():
 source=document_adapter();marker='@GetMapping("/__test/facts")';assert source.count(marker)==1
 gate='''
 @Bean acp.api.IntegrityWorker.ExecutionGate integrityGate(JdbcTemplate jdbc){return q->{
  var controls=jdbc.queryForList("SELECT * FROM PREFIX_control WHERE queue=?",q.id());if(controls.isEmpty())return;var control=controls.getFirst();String mode=control.get("mode").toString();
  if(mode.equals("ALWAYS_FAIL"))throw new IllegalStateException("LAB_TRANSIENT");
  if(mode.equals("ONCE")&&jdbc.update("UPDATE PREFIX_control SET failures=failures-1 WHERE queue=? AND failures>0",q.id())==1)throw new IllegalStateException("LAB_TRANSIENT");
  if(mode.equals("TIMEOUT")){new java.util.concurrent.CountDownLatch(1).await(10,java.util.concurrent.TimeUnit.SECONDS);return;}
  if(mode.equals("HOLD_FIRST")&&jdbc.update("UPDATE PREFIX_control SET first_token=?,entered=true WHERE queue=? AND first_token IS NULL",q.token(),q.id())==1){
   long deadline=System.nanoTime()+java.util.concurrent.TimeUnit.SECONDS.toNanos(8);
   try(var connection=java.util.Objects.requireNonNull(jdbc.getDataSource()).getConnection();var statement=connection.createStatement()){
    statement.execute("LISTEN acp_integrity_release");var pg=connection.unwrap(org.postgresql.PGConnection.class);
    while(!Boolean.TRUE.equals(jdbc.queryForObject("SELECT released FROM PREFIX_control WHERE queue=?",Boolean.class,q.id()))){if(Thread.currentThread().isInterrupted())throw new InterruptedException();if(System.nanoTime()>deadline)throw new IllegalStateException("LAB_GATE_TIMEOUT");pg.getNotifications(100);}
   }
  }
 };}
'''.replace('PREFIX',PREFIX)
 source=source.replace(' @Bean acp.infrastructure.JobRuntime.PrincipalPort',gate+'\n @Bean acp.infrastructure.JobRuntime.PrincipalPort',1)
 methods='''
  @GetMapping("/__test/worker-owner") Map<String,Object> workerOwner(){return Map.of("owner",integrity.instanceOwner());}
  @GetMapping("/__test/job-state") Map<String,Object> jobState(){return Map.of(
   "queue",jdbc.queryForList("SELECT id::text,convert_from(tenant,'UTF8') AS tenant,convert_from(resource,'UTF8') AS resource,document::text,state,attempts,token,owner,lease_until,occurrence,error FROM PREFIX_queue ORDER BY occurrence,id"),
   "audits",jdbc.queryForList("SELECT id,convert_from(subject,'UTF8') AS subject,convert_from(tenant,'UTF8') AS tenant FROM acp_audit WHERE operation='JOB-INTEGRITY' ORDER BY id"),
   "results",jdbc.queryForList("SELECT queue::text,status,token,expected_sha,actual_sha,audit_id FROM PREFIX_result ORDER BY queue"),
   "attempts",jdbc.queryForList("SELECT queue::text,token,owner,state,error FROM PREFIX_attempt ORDER BY queue,token"),
   "schedule",jdbc.queryForList("SELECT job,convert_from(tenant,'UTF8') AS tenant,next_slot,last_slot,skipped,error FROM PREFIX_schedule ORDER BY tenant"),
   "controls",jdbc.queryForList("SELECT queue::text,mode,entered,first_token,released FROM PREFIX_control ORDER BY queue"));}
  @PostMapping("/__test/job-admin") Map<String,Object> jobAdmin(@RequestBody Map<String,Object> body){
   String action=body.get("action").toString();
   if(action.equals("INIT")){jdbc.execute("CREATE TABLE PREFIX_control(queue uuid PRIMARY KEY,mode text NOT NULL,failures integer NOT NULL DEFAULT 0,entered boolean NOT NULL DEFAULT false,first_token bigint,released boolean NOT NULL DEFAULT false)");return Map.of("initialized",true);}
   if(action.equals("MISSED")){jdbc.update("UPDATE PREFIX_schedule SET next_slot=last_slot-3");return Map.of("configured",true);}
   java.util.UUID id=java.util.UUID.fromString(body.get("queue").toString());
   if(action.equals("RELEASE")){jdbc.update("UPDATE PREFIX_control SET released=true WHERE queue=?",id);jdbc.execute("NOTIFY acp_integrity_release");}
   else if(action.equals("EXPIRE")){jdbc.update("UPDATE PREFIX_queue SET lease_until=clock_timestamp()-interval '1 second' WHERE id=?",id);}
   else if(action.equals("ROLLBACK_ON")){jdbc.execute("CREATE FUNCTION acp_job_test_failure() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN RAISE EXCEPTION 'CONTROLLED_JOB_ROLLBACK';END$$;CREATE TRIGGER acp_job_test_failure BEFORE INSERT ON PREFIX_result FOR EACH ROW WHEN(NEW.queue='"+id+"'::uuid) EXECUTE FUNCTION acp_job_test_failure()");}
   else if(action.equals("ROLLBACK_OFF")){jdbc.execute("DROP TRIGGER IF EXISTS acp_job_test_failure ON PREFIX_result;DROP FUNCTION IF EXISTS acp_job_test_failure()");}
   else if(action.equals("ENQUEUE_FAULT")){new org.springframework.transaction.support.TransactionTemplate(manager).execute(s->{
    String tenant=body.getOrDefault("tenant","tenant-one").toString(),resource=body.get("resource").toString(),document=body.get("document").toString(),expected=body.get("sha256").toString();long slot=java.time.Instant.now().getEpochSecond()/3600*3600-((Number)body.get("offset")).longValue()*3600;
    String payload;try{payload=new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(Map.of("resourceId",resource,"documentId",document,"expectedDigest",expected));if(Boolean.TRUE.equals(body.get("invalid")))payload="{\\"command\\":\\"forbidden\\"}";}catch(Exception e){throw new IllegalStateException(e);}
    jdbc.update("INSERT INTO PREFIX_control(queue,mode,failures) VALUES(?,?,?)",id,body.getOrDefault("mode","NONE"),body.getOrDefault("failures",0));
    jdbc.update("INSERT INTO PREFIX_queue(id,job,tenant,resource,document,occurrence,payload,state) VALUES(?,'JOB-INTEGRITY',convert_to(?,'UTF8'),convert_to(?,'UTF8'),?,?,?::jsonb,'PENDING')",id,tenant,resource,java.util.UUID.fromString(document),slot,payload);return null;});}
   else throw new IllegalArgumentException("LAB_ACTION");return Map.of("configured",true);
  }
'''.replace('PREFIX',PREFIX)
 source=source.replace(marker,methods+marker)
 source=source.replace('final JdbcTemplate jdbc;final Flyway flyway;', 'final acp.api.IntegrityWorker integrity;final JdbcTemplate jdbc;final Flyway flyway;')
 source=source.replace('Fixture(JdbcTemplate jdbc,Flyway flyway,', 'Fixture(acp.api.IntegrityWorker integrity,JdbcTemplate jdbc,Flyway flyway,').replace('this.jdbc=jdbc;this.flyway=flyway;', 'this.integrity=integrity;this.jdbc=jdbc;this.flyway=flyway;')
 return source
