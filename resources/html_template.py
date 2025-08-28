from importlib import resources as _res
from pathlib import Path


def load_html_template() -> str:
    """
    Load template.html packaged with this module, regardless of the process CWD.
    Tries importlib.resources first, then falls back to a path next to this file,
    and finally to a minimal built-in template.
    """
    # 1) importlib.resources (works when run as a package/module)
    try:
        # __package__ should be "resources"; use that explicitly for clarity
        return _res.files("resources").joinpath("template.html").read_text(encoding="utf-8")
    except Exception:
        pass

    # 2) Path next to this python file (works when running from source tree)
    try:
        p = Path(__file__).resolve().parent / "template.html"
        if p.exists():
            return p.read_text(encoding="utf-8")
    except Exception:
        pass


# Public constant imported elsewhere
HTML_TEMPLATE = load_html_template()
