#!/usr/bin/env python3
"""
AskCode installer

- Creates/updates a user-level External Tool named "AskCode" for JetBrains IDEs
  and Android Studio across *old* (tools/External Tools.xml) and *new* (options/tools.xml) schemas.
- Leaves any other external tools untouched.
- Adds/updates a launcher script at ~/.local/bin/ask-code (optional but recommended).
- Provides: install (default), uninstall, doctor

Usage:
  python installer.py
  python installer.py install
  python installer.py uninstall
  python installer.py doctor
"""

from __future__ import annotations

import argparse
import glob
import shutil
import stat
import xml.etree.ElementTree as ET
from pathlib import Path

HOME = Path.home()
ASKCODE_ROOT = Path(__file__).resolve().parent
LAUNCHER = HOME / ".local" / "bin" / "ask-code"
MAIN_PY = ASKCODE_ROOT / "main.py"  # your top-level entrypoint in this repo

# External Tool arguments (robust to missing macros)
ARGS = ("--file $FileName$ --filepath $FilePath$ "
        "--sel-start $SelectionStart$ --sel-end $SelectionEnd$ "
        "--sel-start-line $SelectionStartLine$ --sel-start-col $SelectionStartColumn$ "
        "--sel-end-line $SelectionEndLine$ --sel-end-col $SelectionEndColumn$"
        )

IDE_GLOB_ROOTS = [
    HOME / "Library/Application Support/JetBrains/*",  # macOS JetBrains family
    HOME / "Library/Application Support/Google/AndroidStudio*",  # Android Studio
]


# ---------- utils ----------

def info(msg: str):
    print(msg)


def warn(msg: str):
    print(f"WARNING: {msg}")


def backup_file(path: Path):
    try:
        if path.exists():
            bak = path.with_suffix(path.suffix + ".bak")
            shutil.copy2(path, bak)
    except Exception as e:
        warn(f"Could not backup {path}: {e}")


def ensure_parent(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)


def xml_write(path: Path, tree: ET.ElementTree):
    ensure_parent(path)
    backup_file(path)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def find_config_roots() -> list[Path]:
    roots: list[Path] = []
    for g in IDE_GLOB_ROOTS:
        roots.extend([Path(p) for p in glob.glob(str(g)) if Path(p).is_dir()])
    # de-dup and sort for consistent output
    seen = set()
    uniq = []
    for r in sorted(roots, key=str):
        if str(r) not in seen:
            seen.add(str(r))
            uniq.append(r)
    return uniq


# ---------- launcher (optional but nice) ----------

def ensure_launcher() -> Path:
    """
    Write ~/.local/bin/ask-code which runs this repo's main.py with the user's default Python.
    Uses /usr/bin/env python3 to avoid hard-coding a path.
    """
    script = f"""#!/bin/sh
    # AskCode launcher
    exec /usr/bin/env python3 "{MAIN_PY}" "$@"
    """
    ensure_parent(LAUNCHER)
    LAUNCHER.write_text(script, encoding="utf-8")
    # chmod +x
    LAUNCHER.chmod(LAUNCHER.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return LAUNCHER


# ---------- XML patchers ----------

def ensure_tool_in_legacy(root_dir: Path) -> bool:
    """
    Old schema: ~/…/<IDE>/tools/External Tools.xml
    Root element is usually <toolSet name="External Tools"> or a container with <toolSet>.
    """
    path = root_dir / "tools" / "External Tools.xml"
    if not path.exists():
        # Create a minimal legacy file with our tool
        tset = ET.Element("toolSet", {"name": "External Tools"})
        tree = ET.ElementTree(tset)
    else:
        try:
            tree = ET.parse(path)
        except ET.ParseError:
            warn(f"{path} is not valid XML; recreating minimal structure.")
            tset = ET.Element("toolSet", {"name": "External Tools"})
            tree = ET.ElementTree(tset)

    root = tree.getroot()

    # Locate or create the <toolSet name="External Tools">
    if root.tag == "toolSet":
        tset = root
    else:
        tset = root.find(".//toolSet[@name='External Tools']") or root.find(".//toolSet")
        if tset is None:
            # Try to create classic container:
            # <application><component name="Tools"><toolSet name="External Tools">…</toolSet></component></application>
            if root.tag != "application":
                app = ET.Element("application")
                app.extend(list(root))
                root.clear()
                root.append(app)
                root = app
            comp = root.find("./component[@name='Tools']") or ET.SubElement(root, "component", {"name": "Tools"})
            tset = ET.SubElement(comp, "toolSet", {"name": "External Tools"})

    # Remove existing AskCode entries
    for t in list(tset.findall("./tool")):
        if t.get("name") == "AskCode":
            tset.remove(t)

    # Add new AskCode tool
    tool = ET.SubElement(tset, "tool", {
        "name": "AskCode",
        "description": "Send current selection to AskCode",
        "showInMainMenu": "true",
        "showInEditor": "true",
        "showInProject": "true",
        "showInSearchPopup": "true",
        "disabled": "false",
        "useConsole": "true",
        "showConsoleOnStdOut": "false",
        "showConsoleOnStdErr": "false",
        "synchronizeAfterRun": "false",
    })
    exec_el = ET.SubElement(tool, "exec")
    ET.SubElement(exec_el, "option", {"name": "COMMAND", "value": str(LAUNCHER)})
    ET.SubElement(exec_el, "option", {"name": "PARAMETERS", "value": ARGS})
    ET.SubElement(exec_el, "option", {"name": "WORKING_DIRECTORY", "value": "$ProjectFileDir$"})

    xml_write(path, tree)
    info(f"✔ Updated (legacy): {path}")
    return True


def ensure_tool_in_options(root_dir: Path) -> bool:
    """
    New schema: ~/…/<IDE>/options/tools.xml  (with <application><component name="ExternalTools"><toolSet…)
    """
    path = root_dir / "options" / "tools.xml"
    created = False
    if not path.exists():
        app = ET.Element("application")
        tree = ET.ElementTree(app)
        created = True
    else:
        try:
            tree = ET.parse(path)
        except ET.ParseError:
            warn(f"{path} is not valid XML; recreating minimal structure.")
            app = ET.Element("application")
            tree = ET.ElementTree(app)
            created = True

    app = tree.getroot()
    # Allow either ExternalTools or Tools (some IDE builds used 'Tools')
    comp = app.find("./component[@name='ExternalTools']") \
           or app.find("./component[@name='Tools']")
    if comp is None:
        comp = ET.SubElement(app, "component", {"name": "ExternalTools"})

    tset = comp.find("./toolSet[@name='External Tools']")
    if tset is None:
        tset = ET.SubElement(comp, "toolSet", {"name": "External Tools"})

    # Remove existing AskCode entries
    changed = created
    for t in list(tset.findall("./tool")):
        if t.get("name") == "AskCode":
            tset.remove(t)
            changed = True

    tool = ET.SubElement(tset, "tool", {
        "name": "AskCode",
        "description": "Send current selection to AskCode",
        "showInMainMenu": "true",
        "showInEditor": "true",
        "showInProject": "true",
        "showInSearchPopup": "true",
        "disabled": "false",
        "useConsole": "true",
        "showConsoleOnStdOut": "false",
        "showConsoleOnStdErr": "false",
        "synchronizeAfterRun": "false",
    })
    exec_el = ET.SubElement(tool, "exec")
    ET.SubElement(exec_el, "option", {"name": "COMMAND", "value": str(LAUNCHER)})
    ET.SubElement(exec_el, "option", {"name": "PARAMETERS", "value": ARGS})
    ET.SubElement(exec_el, "option", {"name": "WORKING_DIRECTORY", "value": "$ProjectFileDir$"})
    changed = True

    xml_write(path, tree)
    info(f"✔ Updated (options): {path}")
    return changed


def remove_tool_from_file(path: Path) -> bool:
    """
    Remove AskCode tool from a specific XML file (legacy or options).
    Returns True if a change was made.
    """
    if not path.exists():
        return False
    try:
        tree = ET.parse(path)
    except ET.ParseError:
        return False
    root = tree.getroot()
    changed = False
    # remove any <tool name="AskCode"> anywhere
    for tool in root.findall(".//tool[@name='AskCode']"):
        parent = None
        # find parent by scanning (ElementTree lacks .getparent())
        for elem in root.iter():
            for child in list(elem):
                if child is tool:
                    parent = elem
                    break
            if parent is not None:
                break
        if parent is not None:
            parent.remove(tool)
            changed = True
    if changed:
        xml_write(path, tree)
        info(f"✔ Removed AskCode: {path}")
    return changed


def uninstall_everywhere(roots: list[Path]) -> bool:
    changed = False
    for r in roots:
        changed |= remove_tool_from_file(r / "tools" / "External Tools.xml")
        changed |= remove_tool_from_file(r / "options" / "tools.xml")
    return changed


# ---------- project-level purger ----------

def purge_project_shadow(project_dir: Path) -> int:
    """
    Remove project-scoped AskCode tool(s) that can shadow user-level tools.
    Looks for .idea/**/External Tools*.xml and .idea/options/tools.xml
    """
    n = 0
    idea = project_dir / ".idea"
    if not idea.is_dir():
        return n
    for path in idea.rglob("*.xml"):
        if "External Tools" in path.name or path.name == "tools.xml":
            try:
                if remove_tool_from_file(path):
                    n += 1
            except Exception:
                pass
    return n


# ---------- doctor ----------

def doctor(roots: list[Path]):
    print("Launcher:", LAUNCHER, ("(exists)" if LAUNCHER.exists() else "(MISSING)"))
    if LAUNCHER.exists():
        print("  ->", LAUNCHER.read_text(encoding="utf-8").splitlines()[0])

    if not roots:
        print("\nNo JetBrains/Android Studio config roots found.")
        return

    print("\nScanning config roots:")
    for r in roots:
        print(" -", r)
        leg = r / "tools" / "External Tools.xml"
        opt = r / "options" / "tools.xml"
        for p in (leg, opt):
            if p.exists():
                try:
                    tree = ET.parse(p)
                    root = tree.getroot()
                    found = root.findall(".//tool[@name='AskCode']")
                    print(f"    {p}: {'FOUND' if found else 'not present'}")
                except ET.ParseError:
                    print(f"    {p}: invalid XML")
            else:
                print(f"    {p}: (absent)")


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", nargs="?", choices=["install", "uninstall", "doctor"], default="install")
    ap.add_argument("--no-launcher", action="store_true", help="Do not write ~/.local/bin/ask-code")
    ap.add_argument("--purge-project", action="store_true",
                    help="Also remove project-level AskCode entries from the current directory's .idea")
    args = ap.parse_args()

    # (Optional) ensure launcher
    if args.action in ("install",) and not args.no_launcher:
        ensure_launcher()
        info(f"Launcher: {LAUNCHER}")

    roots = find_config_roots()

    if args.action == "doctor":
        doctor(roots)
        return

    if args.action == "uninstall":
        changed = uninstall_everywhere(roots)
        if args.purge_project:
            n = purge_project_shadow(Path.cwd())
            if n:
                info(f"Removed {n} project-level AskCode definition(s).")
        print("\nDone." if changed else "\nAskCode not found in user-level config.")
        print("Restart the IDE(s).")
        return

    # install
    if not roots:
        warn("No JetBrains/Android Studio user config folders found under ~/Library/Application Support.")
        print("You can still use AskCode by running the launcher directly:")
        print(f'  {LAUNCHER} --selection "hello" --file demo.txt')
        return

    print("Writing AskCode tool into these configs:")
    for r in roots:
        print(" -", r)
        # Write to *both* schemas so it’s picked up regardless of IDE version
        try:
            ensure_tool_in_legacy(r)
        except Exception as e:
            warn(f"Legacy patch failed for {r}: {e}")
        try:
            ensure_tool_in_options(r)
        except Exception as e:
            warn(f"Options patch failed for {r}: {e}")

    if args.purge_project:
        n = purge_project_shadow(Path.cwd())
        if n:
            info(f"\nRemoved {n} project-level AskCode definition(s) that could shadow the user-level tool.")

    print("\nAll set. Fully QUIT and relaunch the IDE(s), then check:")
    print("Preferences → Tools → External Tools → AskCode")
    print("Program:", LAUNCHER)
    print("Parameters:", ARGS)
    print("\nMenu: Tools → External Tools → AskCode")


if __name__ == "__main__":
    main()
