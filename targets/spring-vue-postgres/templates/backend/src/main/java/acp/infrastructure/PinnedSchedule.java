package acp.infrastructure;

import com.fasterxml.jackson.databind.*;
import java.time.*;
import java.util.*;

/** Evaluates packaged 2026d offset transitions; never calls ZoneId or host tzdb. */
public final class PinnedSchedule {
    private final JsonNode rules;
    public PinnedSchedule() {
        try(var stream=getClass().getResourceAsStream("/acp-tzdb-2026d.json")) {
            if(stream==null)throw new IllegalStateException("PINNED_TZDB_MISSING");
            byte[] bytes=stream.readAllBytes();
            try{String digest=java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(bytes));if(!"839f9dccf008ceb252b844ac98da295b20224f68fa257d7f86e93d6e3a68065e".equals(digest))throw new IllegalStateException("PINNED_TZDB_DIGEST");}
            catch(java.security.NoSuchAlgorithmException e){throw new IllegalStateException("SHA256_REQUIRED");}
            rules=new ObjectMapper().readTree(bytes);
            if(!"2026d".equals(rules.path("version").asText()))throw new IllegalStateException("PINNED_TZDB_VERSION");
        }catch(java.io.IOException e){throw new IllegalStateException("PINNED_TZDB_INVALID");}
    }
    public Instant occurrence(LocalDateTime local,String zone,String gap,String overlap) {
        var transitions=rules.path("zones").path(zone).path("transitions");
        if(!transitions.isArray())throw new IllegalArgumentException("PINNED_ZONE_UNSUPPORTED");
        long wall=local.toEpochSecond(ZoneOffset.UTC),start=rules.path("start").asLong(),end=rules.path("end").asLong();
        long minOffset=Long.MAX_VALUE,maxOffset=Long.MIN_VALUE;for(var t:transitions){minOffset=Math.min(minOffset,t.get(1).asLong());maxOffset=Math.max(maxOffset,t.get(1).asLong());}
        if(wall-maxOffset<start || wall-minOffset>=end)throw new IllegalArgumentException("PINNED_RULE_HORIZON");
        TreeSet<Instant> matches=new TreeSet<>();
        for(int i=0;i<transitions.size();i++) {
            long lo=transitions.get(i).get(0).asLong(),hi=i+1<transitions.size()?transitions.get(i+1).get(0).asLong():end;
            long utc=wall-transitions.get(i).get(1).asLong();
            if(utc>=lo && utc<hi)matches.add(Instant.ofEpochSecond(utc,local.getNano()));
        }
        if(matches.isEmpty()){if("SKIP".equals(gap))return null;throw new IllegalArgumentException("SCHEDULE_GAP");}
        if(matches.size()>1 && "REJECT".equals(overlap))throw new IllegalArgumentException("SCHEDULE_OVERLAP");
        if(!Set.of("EARLIER","LATER","REJECT").contains(overlap))throw new IllegalArgumentException("OVERLAP_POLICY");
        return "LATER".equals(overlap)?matches.last():matches.first();
    }
    public LocalDate dateAt(Instant instant,String zone) {
        long utc=instant.getEpochSecond();
        if(utc<rules.path("start").asLong() || utc>=rules.path("end").asLong())throw new IllegalArgumentException("PINNED_RULE_HORIZON");
        var transitions=rules.path("zones").path(zone).path("transitions");if(!transitions.isArray())throw new IllegalArgumentException("PINNED_ZONE_UNSUPPORTED");
        long offset=transitions.get(0).get(1).asLong();for(var t:transitions){if(t.get(0).asLong()>utc)break;offset=t.get(1).asLong();}
        return LocalDateTime.ofEpochSecond(utc+offset,instant.getNano(),ZoneOffset.UTC).toLocalDate();
    }
    public Instant daily(LocalDate date,JsonNode schedule) {
        if(!"2026d".equals(schedule.path("tzdbVersion").asText()) || !"LOCAL_DAILY".equals(schedule.path("mode").asText()))throw new IllegalArgumentException("SCHEDULE_VERSION_MODE");
        return occurrence(LocalDateTime.of(date,LocalTime.parse(schedule.path("localTime").asText())),schedule.path("timezone").asText(),schedule.path("gap").asText(),schedule.path("overlap").asText());
    }
}
