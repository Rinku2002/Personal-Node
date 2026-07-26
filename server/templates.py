"""Load HTML templates from server/html/."""

from pathlib import Path

HTML_DIR = Path(__file__).resolve().parent / "html"


def render_template(name, **context):
    """Read an HTML file and replace {{placeholders}} with escaped values."""
    template_path = HTML_DIR / name
    content = template_path.read_text(encoding="utf-8")

    for key, value in context.items():
        content = content.replace(f"{{{{{key}}}}}", str(value))

    return content
