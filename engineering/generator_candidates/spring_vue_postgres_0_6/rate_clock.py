"""Successor-only atomic rate admission. The sealed parent template is read-only."""

PATH = 'backend/src/main/java/acp/infrastructure/InvocationCore.java'

TOKEN = r'''    private byte[] rateKey(String policy,int revision,String tenant,String actor) {
        return digest(canonical(mapper.valueToTree(List.of(policy,revision,tenant,actor))));
    }
    private long rateLock(byte[] key) {
        return java.nio.ByteBuffer.wrap(digest("ACP\0RATE_ADMISSION\0"+HexFormat.of().formatHex(key))).getLong();
    }
    private void lockRates(List<byte[]> keys) {
        // Only overlapping policy/revision/tenant/actor partitions contend.
        // Sorted transaction-scoped locks work across processes and release on
        // commit/rollback. Hash collisions can only add contention, never merge state.
        keys.stream().mapToLong(this::rateLock).distinct().sorted().forEach(key ->
            jdbc.execute("SELECT pg_advisory_xact_lock("+key+")"));
    }
    public boolean token(String policy,int revision,String tenant,String actor,int requests,int seconds,int burst,BigInteger now) {
        if(now.signum()<0)throw new Outcome("SEMANTIC_TIME");
        byte[] key=rateKey(policy,revision,tenant,actor);
        return isolated.execute(status -> {lockRates(List.of(key));return debit(key,requests,seconds,burst,now);});
    }
    private boolean debit(byte[] key,int requests,int seconds,int burst,BigInteger now) {
        JobContext job=JOB.get();
        if(job!=null && jdbc.queryForObject("SELECT count(*) FROM acp_job_charge WHERE occurrence=? AND rate_identity=?",Long.class,job.occurrence(),key)>0)return true;
        BigInteger denominator=BigInteger.valueOf(seconds).multiply(BILLION), capacity=BigInteger.valueOf(burst).multiply(denominator);
        jdbc.update("INSERT INTO acp_rate(identity,tokens,last_ns) VALUES(?,?,?) ON CONFLICT DO NOTHING",key,new java.math.BigDecimal(capacity),new java.math.BigDecimal(now));
        var row=jdbc.queryForMap("SELECT * FROM acp_rate WHERE identity=? FOR UPDATE",key);
        BigInteger last=integer(row.get("last_ns")); if(now.compareTo(last)<0)throw new Outcome("CLOCK_REVERSED");
        BigInteger tokens=integer(row.get("tokens")).add(now.subtract(last).multiply(BigInteger.valueOf(requests))).min(capacity);
        boolean allowed=tokens.compareTo(denominator)>=0;
        if(allowed)tokens=tokens.subtract(denominator);
        jdbc.update("UPDATE acp_rate SET tokens=?,last_ns=? WHERE identity=?",new java.math.BigDecimal(tokens),new java.math.BigDecimal(now),key);
        if(allowed && job!=null)jdbc.update("INSERT INTO acp_job_charge(occurrence,rate_identity) VALUES(?,?)",job.occurrence(),key);
        return allowed;
    }
    private record Admission(BigInteger instant,Outcome error) {}
    /** Must be called only after generated session/authorization/tenant checks. */
    public void charge(String operation,Jwt jwt) { admission(operation,jwt); }
    private BigInteger admission(String operation,Jwt jwt) {
        List<JsonNode> rates=new ArrayList<>();List<byte[]> keys=new ArrayList<>();
        for(var rate:model.nodes("RatePolicy")) {
            var d=rate.path("data");var permission=model.node(d.path("permission").path("id").asText());
            if(!operation.equals(permission.path("data").path("action").path("id").asText()))continue;
            rates.add(rate);
            keys.add(rateKey(rate.path("id").asText(),rate.path("revision").asInt(),jwt.getClaimAsString("tenant"),
                "ACTOR".equals(d.path("partition").asText())?jwt.getSubject():""));
        }
        Admission result=isolated.execute(status -> {
            lockRates(keys);
            // The logical invocation instant is acquired AFTER partition ordering,
            // once, and returned unchanged to the idempotency reservation.
            BigInteger instant=time.now();if(instant.signum()<0)throw new Outcome("SEMANTIC_TIME");
            for(int i=0;i<rates.size();i++) {
                var d=rates.get(i).path("data");
                try {
                    if(!debit(keys.get(i),d.path("requests").asInt(),d.path("windowSeconds").asInt(),d.path("burst").asInt(),instant))
                        return new Admission(instant,new Outcome("RATE_DENIED"));
                } catch(Outcome error) {return new Admission(instant,error);}
            }
            return new Admission(instant,null);
        });
        // Commit authorized charges (including a denied bucket's clock update)
        // before exposing outcomes, as before. Business rollback never refunds them.
        if(result.error()!=null)throw result.error();
        return result.instant();
    }
'''


def apply(templates):
    original=templates[PATH]
    start=original.index('    public boolean token(')
    end=original.index('    private BigInteger commitTime(',start)
    old='BigInteger instant=time.now();charge(operation,jwt,instant);claim=reserve(call,jwt,instant);'
    if original.count(old)!=1:
        raise ValueError('SUCCESSOR_RATE_ANCESTRY')
    templates=dict(templates)
    templates[PATH]=(original[:start]+TOKEN+original[end:]).replace(old,
        'BigInteger instant=admission(operation,jwt);claim=reserve(call,jwt,instant);',1)
    return templates
