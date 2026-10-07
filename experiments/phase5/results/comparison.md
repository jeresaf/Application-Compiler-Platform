# Descriptive frontend parse measurements

No weighted ranking or technology selection. Hard gates remain incomplete.

Nearest-rank percentiles: cold n=3, warm n=5. At these sample sizes p95 is
the maximum sample, not a stable estimate of tail latency. Workload and hardware
are in protocol.json, machine.json and each raw candidate result.

| Frontend | Nodes | Cold parse p50/p95 ms | Warm parse p50/p95 ms | Cold process p50 ms | Peak RSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| antlr | 1000 | 112.07 / 144.872 | 13.289 / 16.666 | 518.794 | 73.77 |
| antlr | 10000 | 201.359 / 210.29 | 52.994 / 111.757 | 505.769 | 159.15 |
| antlr | 100000 | 614.571 / 627.428 | 337.997 / 438.983 | 876.496 | 640.89 |
| langium | 1000 | 98.743 / 106.579 | 28.178 / 65.712 | 562.684 | 123.98 |
| langium | 10000 | 436.193 / 447.683 | 278.408 / 341.355 | 882.163 | 333.14 |
| langium | 100000 | 5769.662 / 5906.48 | 6212.9 / 6394.472 | 6301.267 | 857.88 |
| xtext | 1000 | 175.526 / 176.128 | 40.366 / 57.799 | 2359.549 | 150.56 |
| xtext | 10000 | 570.581 / 577.1 | 124.504 / 226.353 | 2835.878 | 322.7 |
| xtext | 100000 | 2131.465 / 2481.438 | 1419.283 / 1803.422 | 4319.706 | 893.17 |

Scale declarations intentionally omit required semantic records. These results
measure parsing, not full validation, incremental LSP edits or rename at scale.
All three generated frameworks run in development/default validation mode.
Graph-slice results are a distinct workload in core-runtime.json and are not
combined with parser measurements. JVM/Node JIT warmup and ordinary laptop load
limit interpretation. Initial prototype iterations overlapped some dependency
builds; final serial scale reruns replace those pilot measurements.
