"""Multi-layer VfsStack overlay engine with base/ normalization and empty SiiNunit {} stubs."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Self

from ets2v2.vfs.hashfs import DEFAULT_SEEDED_PREFIXES, open_archive
from ets2v2.vfs.types import (
    ArchiveDiagnostic,
    ProtectedPayloadError,
    UnsupportedCompressionError,
    VfsArchive,
    VfsEntryMeta,
    decode_vfs_text,
    deduplicate_diagnostics,
    detect_3nk,
    filter_paths_by_prefixes,
    normalize_vfs_path,
)

MAX_STUB_INSPECT_BYTES = 1 * 1024 * 1024
_SII_TOKEN_RE = re.compile(r"\{|\}|[^\s{}]+")


def _strip_sii_comments(text: str) -> str:
    """Strip ``#``, ``//``, and ``/* ... */`` comments outside string literals."""
    out: list[str] = []
    idx = 0
    length = len(text)
    in_string = False

    while idx < length:
        ch = text[idx]
        if in_string:
            out.append(ch)
            if ch == "\\" and idx + 1 < length:
                out.append(text[idx + 1])
                idx += 2
                continue
            if ch == '"':
                in_string = False
            idx += 1
            continue

        if ch == '"':
            in_string = True
            out.append(ch)
            idx += 1
            continue

        if ch == "#":
            newline = text.find("\n", idx)
            if newline == -1:
                break
            out.append("\n")
            idx = newline + 1
            continue

        if ch == "/" and idx + 1 < length:
            nxt = text[idx + 1]
            if nxt == "/":
                newline = text.find("\n", idx)
                if newline == -1:
                    break
                out.append("\n")
                idx = newline + 1
                continue
            if nxt == "*":
                end = text.find("*/", idx + 2)
                if end == -1:
                    break
                out.append(" ")
                idx = end + 2
                continue

        out.append(ch)
        idx += 1

    return "".join(out)


def is_empty_sii_stub(data: bytes) -> bool:
    """Return True when ``data`` represents an empty ``SiiNunit {}`` or ``{}`` stub."""
    if detect_3nk(data):
        return False
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False

    cleaned = _strip_sii_comments(text.removeprefix("\ufeff"))
    tokens = _SII_TOKEN_RE.findall(cleaned)
    return tokens in (["SiiNunit", "{", "}"], ["{", "}"])


def classify_mount_path(
    raw_path: str,
    *,
    enabled_dlcs: set[str] | None = None,
) -> tuple[str, str]:
    """Classify an archive-relative path into ``(canonical_path, mount_scope)``.

    Always strips a leading ``base/`` mount prefix into the canonical VFS view
    (``mount_scope="base"``). Paths under ``dlc_<id>/`` receive ``mount_scope="dlc:<id>"``
    and remain unflattened unless ``dlc_<id>`` (or ``<id>``) is listed in ``enabled_dlcs``.
    """
    norm = normalize_vfs_path(raw_path)
    if "/" in norm:
        head, rest = norm.split("/", 1)
        if head == "base" and rest:
            return (rest, "base")
        if head.startswith("dlc_") and len(head) > 4:
            dlc_id = head[4:]
            scope = f"dlc:{dlc_id}"
            if enabled_dlcs is not None and (head in enabled_dlcs or dlc_id in enabled_dlcs):
                return (rest, scope)
            return (norm, scope)
    return (norm, "root")


def _intra_layer_rank(mount_scope: str) -> int:
    if mount_scope == "base":
        return 0
    if mount_scope == "root":
        return 1
    return 2


@dataclass(frozen=True, slots=True)
class VfsLayer:
    """A mounted archive layer with explicit name and overlay priority."""

    name: str
    priority: int
    archive: VfsArchive


@dataclass(frozen=True, slots=True)
class EffectiveVfsEntry:
    """Winning canonical VFS entry with full layer and mount provenance."""

    canonical_path: str
    raw_path: str
    layer_name: str
    priority: int
    mount_scope: str
    archive: VfsArchive
    meta: VfsEntryMeta
    is_empty_stub: bool = False

    @property
    def source_layer(self) -> str:
        """Alias for ``layer_name`` provenance."""
        return self.layer_name


class VfsStack:
    """Priority-ordered multi-layer VFS overlay across HashFS, ZIP, and directory archives."""

    def __init__(
        self,
        layers: Sequence[VfsLayer] = (),
        *,
        seeded_prefixes: Sequence[str] = DEFAULT_SEEDED_PREFIXES,
        enabled_dlcs: Iterable[str] | None = None,
    ) -> None:
        del seeded_prefixes  # Retained for call-site compatibility; layers own their seeds.
        self._enabled_dlcs: set[str] | None = (
            set(enabled_dlcs) if enabled_dlcs is not None else None
        )
        self._layers: list[tuple[int, VfsLayer]] = []
        self._seq_counter = 0
        self._index: dict[str, EffectiveVfsEntry] = {}
        self._stub_cache: dict[str, bool] = {}
        self._dirty = True
        for layer in layers:
            self._layers.append((self._seq_counter, layer))
            self._seq_counter += 1

    @classmethod
    def from_paths(
        cls,
        paths: Sequence[Path | tuple[str, Path]],
        *,
        seeded_prefixes: Sequence[str] = DEFAULT_SEEDED_PREFIXES,
        enabled_dlcs: Iterable[str] | None = None,
    ) -> VfsStack:
        """Build a ``VfsStack`` from ordered paths (later paths take higher priority)."""
        stack = cls(enabled_dlcs=enabled_dlcs)
        for idx, item in enumerate(paths):
            if isinstance(item, tuple):
                name, path = item
            else:
                path = item
                name = path.name
            archive = open_archive(path, seeded_prefixes=seeded_prefixes)
            stack.mount(archive, name=name, priority=idx)
        return stack

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        for _, layer in self._layers:
            layer.archive.close()

    @property
    def layers(self) -> list[VfsLayer]:
        """Return mounted layers ordered from lowest to highest effective priority."""
        ordered = sorted(self._layers, key=lambda pair: (pair[1].priority, pair[0]))
        return [layer for _, layer in ordered]

    def mount(
        self,
        archive: VfsArchive,
        *,
        name: str | None = None,
        priority: int | None = None,
    ) -> VfsLayer:
        """Mount ``archive`` onto the stack and return its ``VfsLayer``."""
        layer_name = name if name is not None else archive.path.name
        if priority is None:
            max_prio = max((layer.priority for _, layer in self._layers), default=-1)
            layer_prio = max_prio + 1
        else:
            layer_prio = priority
        layer = VfsLayer(name=layer_name, priority=layer_prio, archive=archive)
        self._layers.append((self._seq_counter, layer))
        self._seq_counter += 1
        self._dirty = True
        return layer

    def _ensure_index(self) -> None:
        if not self._dirty:
            return
        ordered = sorted(self._layers, key=lambda pair: (pair[1].priority, pair[0]))
        winner_ranks: dict[str, tuple[int, int, int]] = {}
        new_index: dict[str, EffectiveVfsEntry] = {}

        for seq, layer in ordered:
            for raw_path in layer.archive.list_paths():
                canonical_path, mount_scope = classify_mount_path(
                    raw_path,
                    enabled_dlcs=self._enabled_dlcs,
                )
                rank = (layer.priority, seq, _intra_layer_rank(mount_scope))
                prev_rank = winner_ranks.get(canonical_path)
                if prev_rank is not None and prev_rank > rank:
                    continue

                meta = layer.archive.get_meta(raw_path) or VfsEntryMeta(path=raw_path)
                winner_ranks[canonical_path] = rank
                new_index[canonical_path] = EffectiveVfsEntry(
                    canonical_path=canonical_path,
                    raw_path=raw_path,
                    layer_name=layer.name,
                    priority=layer.priority,
                    mount_scope=mount_scope,
                    archive=layer.archive,
                    meta=meta,
                    is_empty_stub=False,
                )

        self._index = new_index
        self._stub_cache.clear()
        self._dirty = False

    def _with_stub_status(self, entry: EffectiveVfsEntry) -> EffectiveVfsEntry:
        cached = self._stub_cache.get(entry.canonical_path)
        if cached is not None:
            meta = entry.archive.get_meta(entry.raw_path) or entry.meta
            return replace(entry, meta=meta, is_empty_stub=cached)

        is_stub = False
        meta = entry.meta
        if (
            entry.canonical_path.lower().endswith((".sii", ".sui"))
            and not entry.meta.encrypted
            and entry.meta.compression != "unknown"
            and 0 <= entry.meta.size <= MAX_STUB_INSPECT_BYTES
        ):
            try:
                payload = entry.archive.read_bytes(entry.raw_path)
                is_stub = is_empty_sii_stub(payload)
            except (ProtectedPayloadError, UnsupportedCompressionError, OSError, ValueError):
                is_stub = False
            meta = entry.archive.get_meta(entry.raw_path) or entry.meta

        updated = replace(entry, meta=meta, is_empty_stub=is_stub)
        self._stub_cache[entry.canonical_path] = is_stub
        self._index[entry.canonical_path] = updated
        return updated

    def resolve(self, path: str) -> EffectiveVfsEntry | None:
        """Resolve the highest-priority ``EffectiveVfsEntry`` for ``path``."""
        norm = normalize_vfs_path(path)
        self._ensure_index()
        entry = self._index.get(norm)
        if entry is None and norm.startswith("base/"):
            stripped = norm[len("base/") :]
            if stripped:
                entry = self._index.get(stripped)
        if entry is None:
            return None
        return self._with_stub_status(entry)

    def exists(self, path: str) -> bool:
        """Return True if ``path`` resolves to a winning entry in the stack."""
        return self.resolve(path) is not None

    def list_paths(self, prefix: str = "") -> list[str]:
        """List sorted canonical POSIX paths in the effective overlay."""
        self._ensure_index()
        return filter_paths_by_prefixes(self._index, [prefix])

    def empty_stub_paths(self, prefix: str = "") -> list[str]:
        """Return sorted canonical paths whose winning payload is an empty ``SiiNunit {}`` stub."""
        stubs: list[str] = []
        for canonical_path in self.list_paths(prefix):
            if not canonical_path.lower().endswith((".sii", ".sui")):
                continue
            entry = self.resolve(canonical_path)
            if entry is not None and entry.is_empty_stub:
                stubs.append(canonical_path)
        return stubs

    def read_bytes(self, path: str) -> bytes:
        """Read raw bytes from the highest-priority layer owning ``path``."""
        entry = self.resolve(path)
        if entry is None:
            raise FileNotFoundError(f"{path!r} not found in VfsStack")
        return entry.archive.read_bytes(entry.raw_path)

    def read_text(self, path: str, encoding: str = "utf-8") -> str:
        """Read and decode UTF-8 text from the highest-priority layer owning ``path``."""
        return decode_vfs_text(self.read_bytes(path), path, encoding)

    def diagnostics(self) -> list[ArchiveDiagnostic]:
        """Aggregate deduplicated diagnostics across all mounted layers."""
        ordered = sorted(self._layers, key=lambda pair: (pair[1].priority, pair[0]))
        return deduplicate_diagnostics(
            diag for _, layer in ordered for diag in layer.archive.diagnostics
        )
