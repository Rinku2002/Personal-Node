import urllib.parse

def build_path_url(base_path, relative_path, item):
    """Build a safe URL path for files and folders."""

    parts = [base_path]
    if relative_path:
        parts.append(relative_path)
    parts.append(item)
    return "/".join(parts)
