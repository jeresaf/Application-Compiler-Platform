package acp.infrastructure;

/** Only generated, exact binding sites manufacture trusted semantic occurrences. */
public final class SemanticFailure extends RuntimeException {
    public record Envelope(String failureId, int failureRevision, String code, String category,
                           boolean retryable, String operationId, int operationRevision, String correlationId) {}
    private final Envelope envelope;
    private final String stage;
    private SemanticFailure(Envelope envelope,String stage) { super("SEMANTIC_FAILURE"); this.envelope=envelope; this.stage=stage; }
    public static SemanticFailure bound(String id,int revision,String code,String category,boolean retryable,String operation,int operationRevision,String stage) {
        return new SemanticFailure(new Envelope(id,revision,code,category,retryable,operation,operationRevision,java.util.UUID.randomUUID().toString()),stage);
    }
    public Envelope envelope() { return envelope; }
    public String stage() { return stage; }
}
