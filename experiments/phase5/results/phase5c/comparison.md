# Phase 5C descriptive integration measurements

These are laptop observations, not weighted rankings. Cold measurement excludes approved fixture construction; superseded values remain in raw JSON. Direct calls are real native parser functions. Split core calls exercise a representative stage, not a complete compiler.

| Frontend | Cold + first response median ms | Warm response median ms | Largest sampled warm RSS MiB | Direct warm parse median ms | Request/response bytes |
| --- | ---: | ---: | ---: | ---: | --- |
| antlr | 479.38 | 178.91 | 161.49 | 39.63 | 57827 / 65767 |
| langium | 436.13 | 87.66 | 120.59 | 44.48 | 57829 / 68585 |
| xtext | 2531.26 | 173.79 | 220.61 | 129.83 | 57827 / 64577 |

Raw data: [integration.json](integration.json), [fault results](core-faults.json), [maintenance](maintenance.json). RSS is sampled steady process RSS, not an independently sampled continuous peak. Native heap and serialization measurements remain separate. Deployment footprint counts installed experiment dependencies; it is not a minimized production distribution.

Weights stay editor 25, performance 20, memory 15, integration 20, ergonomics 10, operations 10. Missing comparable editor/team ergonomics data prevent aggregate normalized scores. Xtext is excluded on generator provenance, not timing. Java/TS/Rust remain viable; no speed-only production selection.

Operationally, workers add process supervision, correlation and version negotiation but contain parser crashes. Direct native calls avoid wire cost but share process failure. Authority remains external in the accepted default worker architecture. Native runtime dependencies and core runtime are pinned/versioned independently.

Observed first integration failure: placing the ANTLR4 complete JAR before Xtext’s Maven ANTLR3 runtime caused `java.lang.NoSuchFieldError: org.antlr.runtime.Token.EOF_TOKEN`. Maven ANTLR3 precedence fixes Xtext experimentation. ANTLR production-eligible worker uses only its generated classes, worker classes, ANTLR4 and Gson; Xtext remains rejected on generator source/build provenance.
