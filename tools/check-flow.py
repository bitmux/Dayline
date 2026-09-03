"""Check that every config-flow step, field and menu option has a translation.

A missing key does not raise in Home Assistant — it renders as a blank label in
the dialog, which is the kind of bug you only find by clicking through the UI on
a live instance. This finds it here instead.

    .venv/bin/python tools/check-flow.py
"""

from __future__ import annotations

import ast
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "day_spine"


def const_strings() -> dict[str, str]:
    tree = ast.parse((ROOT / "const.py").read_text())
    return {
        node.targets[0].id: node.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }


def main() -> int:
    tree = ast.parse((ROOT / "config_flow.py").read_text())
    tr = json.loads((ROOT / "translations" / "en.json").read_text())
    consts = const_strings()

    funcs = {
        node.name.removeprefix("async_step_"): node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name.startswith("async_step_")
    }

    problems: list[str] = []
    for name, fn in sorted(funcs.items()):
        step_id, keys, menu = None, set(), set()
        for node in ast.walk(fn):
            if isinstance(node, ast.keyword) and node.arg == "step_id" and isinstance(node.value, ast.Constant):
                step_id = node.value.value
            if isinstance(node, ast.keyword) and node.arg == "menu_options":
                menu = {e.value for e in node.value.elts if isinstance(e, ast.Constant)}
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("Required", "Optional")
                and node.args
            ):
                arg = node.args[0]
                if isinstance(arg, ast.Constant):
                    keys.add(arg.value)
                elif isinstance(arg, ast.Name):
                    keys.add(consts.get(arg.id, arg.id))

        if step_id is None:
            continue
        table = tr["config"]["step"] if step_id == "user" else tr["options"]["step"]
        if step_id not in table:
            problems.append(f"step '{step_id}' has no translation block")
            continue
        labels = table[step_id].get("data", {})
        # Per-calendar fields are generated at runtime and cannot be listed.
        problems += [
            f"step '{step_id}': field '{k}' has no label"
            for k in sorted(keys)
            if k and "__" not in k and k not in labels
        ]
        for option in sorted(menu):
            if option not in funcs:
                problems.append(f"menu option '{option}' has no handler")
            if option not in table[step_id].get("menu_options", {}):
                problems.append(f"menu option '{option}' has no label")

    if problems:
        print("\n".join(" - " + p for p in problems))
        return 1
    print(f"config flow: {len(funcs)} steps, translations complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
