"""Copy Directory plugin assets into .cursor/ so the local workspace cannot drift."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIRRORS = ("skills", "agents", "commands")


def _body(text: str) -> str:
    parts = text.split("---", 2)
    if len(parts) < 3:
        return text
    return parts[2].lstrip("\n")


def sync_rules(check: bool) -> list[str]:
    errors: list[str] = []
    src_dir = ROOT / "rules"
    dest_dir = ROOT / ".cursor" / "rules"
    dest_dir.mkdir(parents=True, exist_ok=True)
    for source in sorted(src_dir.glob("*.mdc")):
        dest = dest_dir / source.name
        original = source.read_text(encoding="utf-8")
        body = _body(original)
        header, _, _ = original.partition("---")
        # Keep Directory globs; this workspace always applies the rule.
        description = "When scientific models change, run Veyra instead of guessing results."
        for line in original.splitlines():
            if line.startswith("description:"):
                description = line.split(":", 1)[1].strip()
                break
        generated = (
            "---\n"
            f"description: {description}\n"
            'globs: "**/*.{veyra,py,ipynb,jl,m,r}"\n'
            "alwaysApply: true\n"
            "---\n\n"
            f"{body.rstrip()}\n"
        )
        if check:
            if not dest.is_file():
                errors.append(f"missing {dest.relative_to(ROOT)}")
            elif _body(dest.read_text(encoding="utf-8")) != body:
                errors.append(f"drift {dest.relative_to(ROOT)} (rule body)")
        else:
            dest.write_text(generated, encoding="utf-8")
        _ = header
    return errors


def sync_trees(check: bool) -> list[str]:
    errors: list[str] = []
    for name in MIRRORS:
        src = ROOT / name
        dest = ROOT / ".cursor" / name
        if check:
            if not dest.is_dir():
                errors.append(f"missing {dest.relative_to(ROOT)}")
                continue
            src_files = {p.relative_to(src).as_posix() for p in src.rglob("*") if p.is_file()}
            dest_files = {p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file()}
            if src_files != dest_files:
                errors.append(f"file set drift {name}/ vs .cursor/{name}/")
            for relative in sorted(src_files & dest_files):
                if (src / relative).read_bytes() != (dest / relative).read_bytes():
                    errors.append(f"drift .cursor/{name}/{relative}")
            continue
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if .cursor/ drifted from plugin roots.",
    )
    args = parser.parse_args(argv)
    errors = sync_trees(args.check) + sync_rules(args.check)
    if args.check:
        if errors:
            print("plugin mirror drift:", file=sys.stderr)
            for item in errors:
                print(f"  {item}", file=sys.stderr)
            return 1
        print("plugin mirrors match")
        return 0
    print("synced skills, agents, commands, and rules into .cursor/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
