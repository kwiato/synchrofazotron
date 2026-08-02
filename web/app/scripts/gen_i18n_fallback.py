#!/usr/bin/env python3
"""Extracts the panel's STR dict into src/i18n.fallback.json — the bundle's
baked-in copy of every translation. The device's /api/i18n still wins at
runtime; the fallback only covers keys the (older) device does not know yet,
and full offline/first-run boots. Regenerated on every `npm run build`, so it
can never drift further than one build behind pistream_panel.py."""
import ast
import json
import pathlib
import re

APP_DIR = pathlib.Path(__file__).resolve().parent.parent          # web/app
PANEL = APP_DIR.parent / "pistream_panel.py"                       # web/
OUT = APP_DIR / "src" / "i18n.fallback.json"

# Static stand-ins for the placeholders _fill() resolves server-side with live
# values. Only a handful of strings carry them; a generic value beats a raw
# {{DEVICE}} in the UI.
FILLS = {
    "{{DEVICE}}": "Synchrofazotron",
    "{{PLAYER}}": "Synchrofazotron",
    "{{PAIR_WIN}}": "180",
    "{{LMS_URL}}": "http://synchrofazotron:9000/material",
}

tree = ast.parse(PANEL.read_text(encoding="utf-8"))
ns = {}
for node in tree.body:
    if isinstance(node, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == "STR" for t in node.targets
    ):
        exec(compile(ast.Module(body=[node], type_ignores=[]), "<STR>", "exec"), {}, ns)
        break
STR = ns.get("STR")
if not STR:
    raise SystemExit("STR dict not found in pistream_panel.py")

T_REF = re.compile(r"\{\{T:(\w+)\}\}")


def fill(lang, s):
    s = T_REF.sub(lambda m: STR[lang].get(m.group(1), STR["en"].get(m.group(1), m.group(1))), s)
    for ph, v in FILLS.items():
        s = s.replace(ph, v)
    return s.replace("{{LANG}}", lang)


out = {lang: {k: fill(lang, v) for k, v in d.items()} for lang, d in STR.items()}
OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n",
               encoding="utf-8")
print("i18n fallback: " + ", ".join(f"{l}: {len(d)} keys" for l, d in out.items()))
