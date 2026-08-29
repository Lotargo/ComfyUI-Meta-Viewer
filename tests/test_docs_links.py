import re
from pathlib import Path


def test_docs_and_readme_links_are_valid():
    root = Path(__file__).resolve().parent.parent
    md_files = list(root.glob("docs/**/*.md")) + [root / "README.md"]

    broken = []
    link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')

    for md in md_files:
        content = md.read_text(encoding="utf-8")
        for match in link_pattern.finditer(content):
            text, url = match.group(1), match.group(2)
            if (
                url.startswith("http://")
                or url.startswith("https://")
                or url.startswith("#")
                or url.startswith("mailto:")
            ):
                continue
            file_part = url.split("#")[0]
            if not file_part:
                continue
            target = (md.parent / file_part).resolve()
            if not target.exists():
                rel_target = (
                    target.relative_to(root)
                    if root in target.parents or target == root
                    else target
                )
                broken.append((str(md.relative_to(root)), text, url, str(rel_target)))

    assert not broken, f"Broken markdown links found: {broken}"
