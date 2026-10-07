"""Derive descriptive tables; missing hard gates prohibit a weighted ranking."""
import json
import math
from pathlib import Path
from run import AREA, save


def percentile(values, fraction):
    return round(sorted(values)[max(0,math.ceil(len(values)*fraction)-1)],3) if values else None


if __name__ == "__main__":
    rows=[]
    for candidate in ("antlr","langium","xtext"):
        evidence=json.loads((AREA/f"results/{candidate}.json").read_text())
        for size,measurement in evidence["scale"].items():
            cold=[r for r in measurement["cold"] if r["status"]=="PASS"]
            parses=[r["output"]["parseMs"][0] for r in cold]
            warm=measurement["warm"]
            warm_times=warm.get("output",{}).get("parseMs",[])[1:]
            rss=[r["peakRssBytes"] for r in [*cold,warm] if "peakRssBytes" in r]
            rows.append({"candidate":candidate,"nodes":int(size),"coldSamples":len(parses),"warmSamples":len(warm_times),"coldParseP50Ms":percentile(parses,.5),"coldParseP95Ms":percentile(parses,.95),"warmParseP50Ms":percentile(warm_times,.5),"warmParseP95Ms":percentile(warm_times,.95),"coldProcessP50Ms":percentile([r["elapsedMs"] for r in cold],.5),"peakRssMiB":round(max(rss)/1048576,2) if rss else None,"observedRssBudgetPass":max(rss)<=1073741824 if rss else None,"statuses":[r["status"] for r in measurement["cold"]]+[warm["status"]]})
    save("comparison.json",{"percentileMethod":"Nearest rank; n=3 cold, n=5 warm. p95 is the maximum sample, not a statistically stable tail estimate.","ranked":False,"reason":"Hard-gate evidence incomplete; descriptive timings cannot compensate.","frontendParse":rows})
    lines=["# Descriptive frontend parse measurements", "", "No weighted ranking or technology selection. Hard gates remain incomplete.", "", "Nearest-rank percentiles: cold n=3, warm n=5. At these sample sizes p95 is", "the maximum sample, not a stable estimate of tail latency. Workload and hardware", "are in protocol.json, machine.json and each raw candidate result.", "", "| Frontend | Nodes | Cold parse p50/p95 ms | Warm parse p50/p95 ms | Cold process p50 ms | Peak RSS MiB |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for r in rows:
        lines.append(f'| {r["candidate"]} | {r["nodes"]} | {r["coldParseP50Ms"]} / {r["coldParseP95Ms"]} | {r["warmParseP50Ms"]} / {r["warmParseP95Ms"]} | {r["coldProcessP50Ms"]} | {r["peakRssMiB"]} |')
    lines.extend(["", "Scale declarations intentionally omit required semantic records. These results", "measure parsing, not full validation, incremental LSP edits or rename at scale.", "All three generated frameworks run in development/default validation mode.", "Graph-slice results are a distinct workload in core-runtime.json and are not", "combined with parser measurements. JVM/Node JIT warmup and ordinary laptop load", "limit interpretation. Initial prototype iterations overlapped some dependency", "builds; final serial scale reruns replace those pilot measurements.", ""])
    (AREA/"results/comparison.md").write_text("\n".join(lines))
