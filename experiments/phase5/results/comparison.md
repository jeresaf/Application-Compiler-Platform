# Descriptive frontend parse measurements

No weighted ranking or technology selection. Hard gates remain incomplete.

Nearest-rank percentiles: cold n=3, warm n=5. At these sample sizes p95 is
the maximum sample, not a stable estimate of tail latency. Workload and hardware
are in protocol.json, machine.json and each raw candidate result.

| Frontend | Nodes | Cold parse p50/p95 ms | Warm parse p50/p95 ms | Cold process p50 ms | Peak RSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| antlr | 1000 | 115.724 / 123.276 | 12.581 / 15.577 | 401.081 | 72.66 |
| antlr | 10000 | 200.833 / 204.52 | 49.041 / 95.107 | 562.728 | 171.76 |
| antlr | 100000 | 622.748 / 625.305 | 361.189 / 423.808 | 890.27 | 708.89 |
| langium | 1000 | 99.597 / 108.619 | 34.872 / 53.75 | 667.041 | 137.96 |
| langium | 10000 | 479.265 / 481.034 | 284.641 / 355.396 | 1083.758 | 342.82 |
| langium | 100000 | 6171.256 / 6673.638 | 6313.803 / 6798.671 | 7032.727 | 873.88 |
| xtext | 1000 | 171.857 / 334.039 | 47.588 / 58.008 | 2308.786 | 151.16 |
| xtext | 10000 | 578.334 / 608.713 | 125.608 / 266.911 | 2885.817 | 330.88 |
| xtext | 100000 | 2080.879 / 2288.904 | 1255.121 / 1359.704 | 4199.773 | 840.05 |

Scale declarations intentionally omit required semantic records. These results
measure parsing, not full validation, incremental LSP edits or rename at scale.
All three generated frameworks run in development/default validation mode.
Graph-slice results are a distinct workload in core-runtime.json and are not
combined with parser measurements. JVM/Node JIT warmup and ordinary laptop load
limit interpretation. Initial prototype iterations overlapped some dependency
builds; final serial scale reruns replace those pilot measurements.
