"""Generate experimental declarations without changing any reference fixture."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AREA = Path(__file__).resolve().parent


def literal(value):
    if isinstance(value, dict):
        if set(value) == {"id", "revision"}:
            return f'ref {json.dumps(value["id"])} @ {value["revision"]}'
        if value.get("kind") == "Money" and set(value) == {"kind", "currency", "precision", "scale", "rounding"}:
            return (f'Money {json.dumps(value["currency"])} precision {value["precision"]}'
                    f' scale {value["scale"]} rounding {json.dumps(value["rounding"])}')
        return "{" + ",".join(json.dumps(k) + ":" + literal(v) for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ",".join(map(literal, value)) + "]"
    return json.dumps(value, ensure_ascii=False)


def encode(model):
    header = {k: v for k, v in model.items() if k != "nodes"}
    lines = ["application " + literal(header) + ";"]
    for node in model["nodes"]:
        body = {k: v for k, v in node.items() if k not in {"id", "revision", "kind"}}
        lines.append(f'{node["kind"]} {json.dumps(node["id"])} @ {node["revision"]} {literal(body)};')
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    for name in ("payment", "case-management"):
        model = json.loads((ROOT / f"test-corpus/phase1/{name}.json").read_text())
        (AREA / f"corpora/{name}.acp").write_text(encode(model))
    for size in (1000, 10000, 100000):
        model = {"applicationId": "APP-SCALE", "modelVersion": "0.2.0", "snapshotId": "SCALE",
                 "nodes": [{"kind": "Entity", "id": f"ENT-{i:06d}", "revision": 1,
                            "name": f"Entity {i}"} for i in range(size)]}
        # Scale files are generated locally, never mistaken for valid semantic fixtures.
        output = AREA / ".cache" / "corpora"
        output.mkdir(parents=True, exist_ok=True)
        (output / f"scale-{size}.acp").write_text(encode(model))
