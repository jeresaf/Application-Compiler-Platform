"""Separate crypto test profile. No trusted JwtDecoder and no interactive worker impersonation."""
from engineering.create_reliability.fixture import adapter_source as old
from engineering.source_intelligence.model import require

def adapter_source():
    source=old();start=source.index('@Bean JwtDecoder decoder()');end=source.index(' @RestController static class Fixture',start)
    source=source[:start]+source[end:]
    before='@Bean acp.infrastructure.JobRuntime.PrincipalPort principal(JwtDecoder decoder){return (id,revision,handle)->decoder.decode("browser-authorized");}'
    require(source.count(before)==1,'H5_WORKER_FIXTURE_DRIFT');source=source.replace(before,'@Bean acp.infrastructure.JobRuntime.PrincipalPort principal(){return (id,revision,handle)->{throw new SecurityException("INTERACTIVE_WORKER_IMPERSONATION_FORBIDDEN");};}')
    source=source.replace('@GetMapping("/__test/facts")','''@org.springframework.beans.factory.annotation.Autowired JwtDecoder h5Decoder;
 @GetMapping("/__test/h5-decode") Map<String,Object> h5Decode(@RequestHeader("Authorization") String header,@org.springframework.security.core.annotation.AuthenticationPrincipal Jwt jwt){long started=System.nanoTime();Jwt verified=h5Decoder.decode(header.substring(7));long elapsed=System.nanoTime()-started;return Map.of("nanoseconds",elapsed,"sameSubject",verified.getSubject().equals(jwt.getSubject()));}
 @GetMapping("/__test/facts")''',1)
    require('@Bean JwtDecoder' not in source and 'decoder.decode(' not in source,'H5_TRUSTED_ADAPTER_FALLBACK');return source
