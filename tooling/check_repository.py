"""Small dependency-free repository checks, shared by local runs and CI."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = [ROOT / "README.md", *ROOT.glob("docs/**/*.md"), *ROOT.glob("contracts/*.md"), *ROOT.glob("test-corpus/**/*.md")]
    problems = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)]+)\)", text):
            if not target.startswith(("https://", "http://", "#")) and not (path.parent / target.split("#")[0]).exists():
                problems.append(f"{path.relative_to(ROOT)}: missing link {target}")
    for folder in ("docs", "contracts", "test-corpus", "tooling", ".github"):
        for path in (ROOT / folder).rglob("*"):
            if path.suffix not in {".md", ".json", ".py", ".txt", ".yml"}:
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if line.rstrip() != line:
                    problems.append(f"{path.relative_to(ROOT)}:{number}: trailing whitespace")
    for problem in problems:
        print(problem)
    print(f"Repository contract checks: {'FAIL' if problems else 'PASS'}")
    return bool(problems)


if __name__ == "__main__":
    raise SystemExit(main())
