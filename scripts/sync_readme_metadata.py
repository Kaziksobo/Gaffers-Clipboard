"""Sync README metadata from pyproject.toml and uv tree output.

Usage:
    uv run python scripts/sync_readme_metadata.py
    uv run python scripts/sync_readme_metadata.py --sync-tree

By default, this script updates selected README sections and the root package line
in the README dependency tree code block (for example:
``gaffers-clipboard v0.6.9``). With ``--sync-tree``, it refreshes the entire
dependency tree block by running ``uv tree``.

The script also syncs selected README sections from ``pyproject.toml``:
- Python version badge.
- Run command snippet (from ``[project.scripts]``).
- Coverage threshold sentence (from ``[tool.coverage.report].fail_under``).
- Author/contact block (from ``[project].authors`` and repository owner).
"""

from __future__ import annotations

import argparse
import logging
import re
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
DEFAULT_README_PATH = PROJECT_ROOT / "README.md"

README_TREE_BLOCK_PATTERN = re.compile(
    (
        r"(<summary><b>Click to view full dependency tree "
        r"\(uv tree\)</b></summary>\s*\n\s*```text\n)(.*?)(\n```)"
    ),
    flags=re.DOTALL,
)
PYTHON_BADGE_PATTERN = re.compile(
    r"!\[Python [^\]]+\]\(https://img\.shields\.io/badge/python-[^)]+\)",
)
RUN_COMMAND_BLOCK_PATTERN = re.compile(
    r"(### Running the Application\s*\n\s*\n"
    r"Launch the application using our configured entry point:\s*\n\s*\n"
    r"```bash\n)(.*?)(\n```)",
    flags=re.DOTALL,
)
COVERAGE_SENTENCE_PATTERN = re.compile(
    r"(Run the test suite \(including coverage checks "
    r"which fail if core logic drops below )"
    r"[0-9]+(?:\.[0-9]+)?"
    r"(%\):)"
)
AUTHOR_NAME_PATTERN = re.compile(
    r"^\*\*.*\*\* Lead Architect & Developer$",
    flags=re.MULTILINE,
)
AUTHOR_EMAIL_PATTERN = re.compile(
    r"^\* \*\*Email:\*\* \[[^\]]+\]\(mailto:[^)]+\)$",
    flags=re.MULTILINE,
)
AUTHOR_GITHUB_PATTERN = re.compile(
    r"^\* \*\*GitHub:\*\* \[@[^\]]+\]\(https://github\.com/[^)]+\)$",
    flags=re.MULTILINE,
)


@dataclass(frozen=True)
class ProjectMetadata:
    """Normalized metadata extracted from pyproject.toml."""

    name: str
    version: str
    requires_python: str
    run_command: str
    coverage_fail_under: int | float
    author_name: str
    author_email: str
    github_owner: str | None


class ReadmeSyncError(RuntimeError):
    """Raised when the README dependency tree section cannot be updated."""


def _require_non_empty_str(
    table: dict[str, object],
    key: str,
    *,
    error: str,
) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value:
        raise ReadmeSyncError(error)
    return value


def _extract_author(authors_section: object) -> tuple[str, str]:
    if not isinstance(authors_section, list) or not authors_section:
        raise ReadmeSyncError("Invalid pyproject.toml: missing project.authors.")

    first_author = authors_section[0]
    if not isinstance(first_author, dict):
        raise ReadmeSyncError("Invalid pyproject.toml: project.authors[0] is invalid.")

    author_name = _require_non_empty_str(
        first_author,
        "name",
        error="Invalid pyproject.toml: author name missing.",
    )
    author_email = _require_non_empty_str(
        first_author,
        "email",
        error="Invalid pyproject.toml: author email missing.",
    )
    return author_name, author_email


def _extract_script_name(scripts_section: object) -> str:
    if not isinstance(scripts_section, dict) or not scripts_section:
        raise ReadmeSyncError("Invalid pyproject.toml: missing [project.scripts].")

    if "gaffer" in scripts_section:
        return "gaffer"

    script_name = next(iter(scripts_section), None)
    if not isinstance(script_name, str) or not script_name:
        raise ReadmeSyncError("Invalid pyproject.toml: could not resolve script name.")
    return script_name


def _load_project_metadata(pyproject_path: Path) -> ProjectMetadata:
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = data.get("project")
    if not isinstance(project, dict):
        raise ReadmeSyncError("Invalid pyproject.toml: missing [project] section.")

    name = _require_non_empty_str(
        project,
        "name",
        error="Invalid pyproject.toml: missing project.name.",
    )
    version = _require_non_empty_str(
        project,
        "version",
        error="Invalid pyproject.toml: missing project.version.",
    )
    requires_python = _require_non_empty_str(
        project,
        "requires-python",
        error="Invalid pyproject.toml: missing requires-python.",
    )
    author_name, author_email = _extract_author(project.get("authors"))
    script_name = _extract_script_name(project.get("scripts"))

    tool = data.get("tool")
    coverage_fail_under = _extract_coverage_fail_under(tool)
    github_owner = _extract_github_owner(project)

    return ProjectMetadata(
        name=name,
        version=version,
        requires_python=requires_python,
        run_command=f"uv run {script_name}",
        coverage_fail_under=coverage_fail_under,
        author_name=author_name,
        author_email=author_email,
        github_owner=github_owner,
    )


def _extract_coverage_fail_under(tool_section: object) -> int | float:
    if not isinstance(tool_section, dict):
        raise ReadmeSyncError("Invalid pyproject.toml: missing [tool] section.")

    coverage = tool_section.get("coverage")
    if not isinstance(coverage, dict):
        raise ReadmeSyncError(
            "Invalid pyproject.toml: missing [tool.coverage] section."
        )

    report = coverage.get("report")
    if not isinstance(report, dict):
        raise ReadmeSyncError(
            "Invalid pyproject.toml: missing [tool.coverage.report] section."
        )

    fail_under = report.get("fail_under")
    if isinstance(fail_under, bool) or not isinstance(fail_under, int | float):
        raise ReadmeSyncError(
            "Invalid pyproject.toml: missing numeric coverage fail_under value."
        )

    return fail_under


def _extract_github_owner(project_section: dict[str, object]) -> str | None:
    urls = project_section.get("urls")
    if not isinstance(urls, dict):
        return None

    repository = urls.get("Repository")
    if not isinstance(repository, str):
        return None

    match = re.search(r"github\.com/([^/]+)/", repository)
    if match is None:
        return None

    owner = match.group(1).strip()
    return owner or None


def _replace_once(
    pattern: re.Pattern[str],
    replacement: str,
    text: str,
    *,
    label: str,
) -> str:
    updated_text, replacements = pattern.subn(replacement, text)
    if replacements != 1:
        raise ReadmeSyncError(f"Could not uniquely update README {label}.")
    return updated_text


def _format_python_badge(requirement: str) -> str:
    match = re.match(r"^\s*>=\s*([0-9]+(?:\.[0-9]+){0,2})\s*$", requirement)
    display = f"{match.group(1)}+" if match is not None else requirement.strip()

    badge_version = quote(display, safe="")
    return (
        f"![Python {display}]"
        f"(https://img.shields.io/badge/python-{badge_version}-blue.svg)"
    )


def _format_coverage_threshold(value: int | float) -> str:
    if isinstance(value, int):
        return str(value)

    return str(int(value)) if value.is_integer() else str(value)


def _replace_run_command_block(readme_text: str, run_command: str) -> str:
    def _replacement(match: re.Match[str]) -> str:
        return f"{match.group(1)}{run_command}{match.group(3)}"

    updated_text, replacements = RUN_COMMAND_BLOCK_PATTERN.subn(
        _replacement,
        readme_text,
    )
    if replacements != 1:
        raise ReadmeSyncError(
            "Could not find a unique README run-command block to update."
        )
    return updated_text


def _sync_selected_readme_sections(readme_text: str, metadata: ProjectMetadata) -> str:
    updated_text = readme_text

    updated_text = _replace_once(
        PYTHON_BADGE_PATTERN,
        _format_python_badge(metadata.requires_python),
        updated_text,
        label="Python badge",
    )

    updated_text = _replace_run_command_block(updated_text, metadata.run_command)

    coverage_text, coverage_replacements = COVERAGE_SENTENCE_PATTERN.subn(
        rf"\1{_format_coverage_threshold(metadata.coverage_fail_under)}\2",
        updated_text,
        count=1,
    )
    if coverage_replacements != 1:
        raise ReadmeSyncError("Could not uniquely update README coverage sentence.")
    updated_text = coverage_text

    updated_text = _replace_once(
        AUTHOR_NAME_PATTERN,
        f"**{metadata.author_name}** Lead Architect & Developer",
        updated_text,
        label="author name line",
    )
    updated_text = _replace_once(
        AUTHOR_EMAIL_PATTERN,
        (f"* **Email:** [{metadata.author_email}](mailto:{metadata.author_email})"),
        updated_text,
        label="author email line",
    )

    if metadata.github_owner is not None:
        updated_text = _replace_once(
            AUTHOR_GITHUB_PATTERN,
            (
                "* **GitHub:** "
                f"[@{metadata.github_owner}]"
                f"(https://github.com/{metadata.github_owner})"
            ),
            updated_text,
            label="author GitHub line",
        )

    return updated_text


def _run_uv_tree(project_root: Path) -> str:
    uv_executable = shutil.which("uv")
    if uv_executable is None:
        raise ReadmeSyncError("Could not find 'uv' executable on PATH.")

    completed = subprocess.run(  # noqa: S603
        [uv_executable, "tree"],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.rstrip("\n")


def _replace_tree_block(readme_text: str, new_block_content: str) -> str:
    def _replacement(match: re.Match[str]) -> str:
        return f"{match.group(1)}{new_block_content}{match.group(3)}"

    updated_text, replacements = README_TREE_BLOCK_PATTERN.subn(
        _replacement,
        readme_text,
    )
    if replacements != 1:
        raise ReadmeSyncError(
            "Could not find a unique README dependency tree block to update."
        )
    return updated_text


def _update_root_line_only(existing_tree_block: str, package_line: str) -> str:
    lines = existing_tree_block.splitlines()
    first_content_index = next(
        (index for index, line in enumerate(lines) if line),
        None,
    )

    if first_content_index is None:
        return package_line

    lines[first_content_index] = package_line
    return "\n".join(lines)


def _extract_existing_tree_block(readme_text: str) -> str:
    match = README_TREE_BLOCK_PATTERN.search(readme_text)
    if match is None:
        raise ReadmeSyncError(
            "Could not find README dependency tree block marked with 'uv tree'."
        )
    return match.group(2)


def sync_readme(
    *,
    pyproject_path: Path,
    readme_path: Path,
    sync_tree: bool,
) -> None:
    """Sync README dependency-tree metadata from project sources."""
    metadata = _load_project_metadata(pyproject_path)
    root_line = f"{metadata.name} v{metadata.version}"

    readme_text = readme_path.read_text(encoding="utf-8")
    readme_text = _sync_selected_readme_sections(readme_text, metadata)

    if sync_tree:
        new_tree_block = _run_uv_tree(pyproject_path.parent)
    else:
        current_tree_block = _extract_existing_tree_block(readme_text)
        new_tree_block = _update_root_line_only(current_tree_block, root_line)

    updated_readme = _replace_tree_block(readme_text, new_tree_block)
    if updated_readme == readme_text:
        logger.info("README already in sync; no changes written.")
        return

    readme_path.write_text(updated_readme, encoding="utf-8")
    logger.info("Updated README metadata at %s", readme_path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sync README package version from pyproject.toml and optionally refresh "
            "the full uv tree block."
        )
    )
    parser.add_argument(
        "--pyproject",
        type=Path,
        default=DEFAULT_PYPROJECT_PATH,
        help="Path to pyproject.toml (default: project root pyproject.toml).",
    )
    parser.add_argument(
        "--readme",
        type=Path,
        default=DEFAULT_README_PATH,
        help="Path to README markdown file (default: project root README.md).",
    )
    parser.add_argument(
        "--sync-tree",
        action="store_true",
        help="Refresh the entire dependency block using `uv tree`.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the CLI entry point."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = _parse_args()

    pyproject_path = args.pyproject.resolve()
    readme_path = args.readme.resolve()

    if not pyproject_path.exists():
        raise FileNotFoundError(f"pyproject.toml not found: {pyproject_path}")
    if not readme_path.exists():
        raise FileNotFoundError(f"README file not found: {readme_path}")

    sync_readme(
        pyproject_path=pyproject_path,
        readme_path=readme_path,
        sync_tree=args.sync_tree,
    )


if __name__ == "__main__":
    main()
