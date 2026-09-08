"""Loading, versioning and rendering of the formalization prompts.

Prompts live in `prompts/formalize/` as standalone markdown files rather than
inside Python, because they are the part of this pipeline that gets iterated
on: a prompt is edited and re-run far more often than the code around it is.
Keeping them in files means a prompt change is a readable diff, and means a
run can record *which* prompt produced it.

File naming is `<order>_<stage>.v<version>.md`, e.g. `02_rules.v1.md`. Loading
a stage without pinning a version takes the highest version present, so
iterating means copying `02_rules.v1.md` to `02_rules.v2.md` and editing --
the previous version stays runnable for comparison.

Each file starts with a small `---`-delimited front matter carrying the
per-stage model configuration (so switching one stage to a cheaper model is a
prompt edit, not a code change), followed by the body. The body may pull in
shared fragments with `{{include:_shared/grammar}}` and takes runtime values
through `{{variable}}` placeholders; an unfilled placeholder is an error
rather than a silently empty prompt.

Two hashes are recorded per prompt. `template_sha256` covers the source files
(front matter, body and every include) and is the prompt's *identity* across
cases -- it is what provenance records. `rendered_sha256` covers the exact
text sent to the model and is what the response cache is keyed on.
"""
import hashlib
import re

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_PROMPTS_DIR = REPO_ROOT / "prompts" / "formalize"

_FILENAME_RE = re.compile(r"^(?:\d+_)?(?P<stage>[a-z0-9_]+)\.v(?P<version>\d+)\.md$")
_INCLUDE_RE = re.compile(r"\{\{include:\s*(?P<target>[A-Za-z0-9_./-]+)\s*\}\}")
_VARIABLE_RE = re.compile(r"\{\{\s*(?P<name>[a-z][a-z0-9_]*)\s*\}\}")
_MAX_INCLUDE_DEPTH = 4

#: Front-matter keys forwarded to the model call. Anything else is metadata.
CONFIG_KEYS = ("model", "temperature", "thinking_budget", "max_output_tokens")


class PromptError(RuntimeError):
    """Raised for a missing prompt file, unknown include or unfilled variable."""


@dataclass(frozen=True)
class PromptSpec:
    """A prompt ready to send, plus everything needed to reproduce it."""
    stage: str
    version: int
    path: Path
    text: str
    config: Dict[str, object] = field(default_factory=dict)
    template_sha256: str = ""
    rendered_sha256: str = ""
    includes: List[str] = field(default_factory=list)

    @property
    def relative_path(self) -> str:
        try:
            return str(self.path.relative_to(REPO_ROOT))
        except ValueError:
            return str(self.path)

    @property
    def model(self) -> Optional[str]:
        value = self.config.get("model")
        return str(value) if value else None


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _coerce(value: str):
    lowered = value.strip().lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if lowered in ("null", "none", ""):
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value.strip().strip('"').strip("'")


def split_front_matter(raw: str):
    """`(front_matter_dict, body)`. A file without front matter yields `({}, raw)`."""
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    meta: Dict[str, object] = {}
    for line in parts[1].splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = _coerce(value)
    return meta, parts[2].lstrip("\n")


def stage_files(prompts_dir: Optional[Path] = None) -> Dict[str, Dict[int, Path]]:
    """`{stage: {version: path}}` for every prompt file in `prompts_dir`."""
    directory = Path(prompts_dir or DEFAULT_PROMPTS_DIR)
    found: Dict[str, Dict[int, Path]] = {}
    if not directory.is_dir():
        return found
    for path in sorted(directory.glob("*.md")):
        match = _FILENAME_RE.match(path.name)
        if match:
            found.setdefault(match["stage"], {})[int(match["version"])] = path
    return found


def available_versions(stage: str, prompts_dir: Optional[Path] = None) -> List[int]:
    return sorted(stage_files(prompts_dir).get(stage, {}))


def resolve_path(stage: str, version: Optional[int] = None,
                 prompts_dir: Optional[Path] = None) -> tuple:
    """`(path, version)` for `stage`, defaulting to the highest version."""
    versions = stage_files(prompts_dir).get(stage, {})
    if not versions:
        directory = Path(prompts_dir or DEFAULT_PROMPTS_DIR)
        raise PromptError(f"Nenhum prompt para o estágio {stage!r} em {directory}")
    if version is None:
        version = max(versions)
    if version not in versions:
        raise PromptError(
            f"Estágio {stage!r} não tem versão v{version} "
            f"(disponíveis: {', '.join(f'v{v}' for v in sorted(versions))})"
        )
    return versions[version], version


def _expand_includes(body: str, directory: Path, seen: List[str], depth: int = 0) -> str:
    if depth > _MAX_INCLUDE_DEPTH:
        raise PromptError(f"Includes aninhados demais (>{_MAX_INCLUDE_DEPTH}) em {directory}")

    def replace(match: "re.Match") -> str:
        target = match["target"]
        path = directory / (target if target.endswith(".md") else f"{target}.md")
        if not path.is_file():
            raise PromptError(f"Include inexistente: {target!r} (procurado em {path})")
        seen.append(target)
        _, included = split_front_matter(path.read_text(encoding="utf-8"))
        return _expand_includes(included.strip(), directory, seen, depth + 1)

    return _INCLUDE_RE.sub(replace, body)


def render(body: str, variables: Dict[str, str]) -> str:
    """Substitute `{{name}}` in one pass, so substituted content is never
    rescanned for placeholders (annotator text may contain braces)."""
    missing: List[str] = []

    def replace(match: "re.Match") -> str:
        name = match["name"]
        if name not in variables:
            missing.append(name)
            return match.group(0)
        return str(variables[name])

    result = _VARIABLE_RE.sub(replace, body)
    if missing:
        raise PromptError(
            "Variáveis não fornecidas ao renderizar o prompt: "
            + ", ".join(sorted(set(missing)))
        )
    return result


def load(stage: str, *, version: Optional[int] = None,
         variables: Optional[Dict[str, str]] = None,
         prompts_dir: Optional[Path] = None) -> PromptSpec:
    """Read, expand and render the prompt for `stage`."""
    directory = Path(prompts_dir or DEFAULT_PROMPTS_DIR)
    path, resolved_version = resolve_path(stage, version, directory)
    raw = path.read_text(encoding="utf-8")
    meta, body = split_front_matter(raw)

    includes: List[str] = []
    expanded = _expand_includes(body, directory, includes)

    template_parts = [raw]
    for target in includes:
        include_path = directory / (target if target.endswith(".md") else f"{target}.md")
        template_parts.append(include_path.read_text(encoding="utf-8"))

    text = render(expanded, variables or {}).strip() + "\n"
    config = {key: meta[key] for key in CONFIG_KEYS if meta.get(key) is not None}

    return PromptSpec(
        stage=stage,
        version=resolved_version,
        path=path,
        text=text,
        config=config,
        template_sha256=_sha256("\x00".join(template_parts)),
        rendered_sha256=_sha256(text),
        includes=list(dict.fromkeys(includes)),
    )
