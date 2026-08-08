"""Race-safe, bounded scanning for worker-local Obsidian vault mounts.

This module owns only the filesystem trust boundary. It deliberately does not
parse Markdown, dereference embeds, persist state, or expose paths in errors.
"""

from __future__ import annotations

import errno
import hashlib
import math
import os
import stat
import time
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

HARD_MAX_FILES = 10_000
HARD_MAX_ENTRIES = 100_000
HARD_MAX_TOTAL_BYTES = 256 * 1024 * 1024
HARD_MAX_DEPTH = 32
HARD_MAX_DURATION_SECONDS = 3_600.0
HARD_MAX_NOTE_BYTES = 16 * 1024 * 1024
HARD_MAX_SETTLE_SECONDS = 60.0
HARD_MAX_CONCURRENCY = 8

_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
_FILE_FLAGS = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
_EXPORT_DIRECTORY_NAMES = frozenset(
    {".obsidian", "digests", "summaries", "entities", "themes", "topics"}
)
_TEMP_SUFFIXES = (".tmp", ".swp", ".part", ".crdownload", ".icloud")
_METADATA_NAMES = frozenset(
    {
        ".obsidian-sync-manifest.json",
        ".obsidian-sync-manifest.json.bak",
    }
)


class _UnavailableError(ValueError):
    """Internal path-policy failure that intentionally carries no path."""

    def __init__(self) -> None:
        super().__init__("source_unavailable")


class _EntryLimitError(RuntimeError):
    """Signal that bounded directory production consumed its complete allowance."""


def validate_relative_path(value: str) -> tuple[str, ...]:
    """Validate and split one normalized Unix-relative path.

    Backslashes are rejected rather than interpreted so Windows traversal text
    cannot acquire a different meaning at a later boundary.
    """

    if (
        not isinstance(value, str)
        or not value
        or "\x00" in value
        or "\\" in value
        or value.startswith("/")
        or os.path.isabs(value)
    ):
        raise ValueError("unsafe_path")
    parts = tuple(value.split("/"))
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("unsafe_path")
    return parts


def _validated_absolute_path(value: str | Path) -> Path:
    raw = str(value)
    path = Path(value)
    if "\x00" in raw or "\\" in raw or not path.is_absolute():
        raise _UnavailableError
    if any(part in {".", ".."} for part in path.parts):
        raise _UnavailableError
    return path


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


@dataclass(frozen=True)
class ScanLimits:
    """Per-scan limits constrained by non-overridable hard ceilings."""

    max_files: int = 1_000
    max_entries: int = 10_000
    max_total_bytes: int = 64 * 1024 * 1024
    max_depth: int = 8
    max_duration_seconds: float = 300.0
    max_note_bytes: int = 4 * 1024 * 1024
    settle_seconds: float = 0.0
    max_concurrency: int = 1

    def __post_init__(self) -> None:
        integer_bounds = (
            (self.max_files, 1, HARD_MAX_FILES),
            (self.max_entries, 1, HARD_MAX_ENTRIES),
            (self.max_total_bytes, 1, HARD_MAX_TOTAL_BYTES),
            (self.max_depth, 0, HARD_MAX_DEPTH),
            (self.max_note_bytes, 1, HARD_MAX_NOTE_BYTES),
            (self.max_concurrency, 1, HARD_MAX_CONCURRENCY),
        )
        if any(
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < minimum
            or value > maximum
            for value, minimum, maximum in integer_bounds
        ):
            raise ValueError("invalid_scan_limits")
        if self.max_note_bytes > self.max_total_bytes:
            raise ValueError("invalid_scan_limits")
        numeric_bounds = (
            (self.max_duration_seconds, 0.0, HARD_MAX_DURATION_SECONDS, False),
            (self.settle_seconds, 0.0, HARD_MAX_SETTLE_SECONDS, True),
        )
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < minimum
            or value > maximum
            or (not inclusive_zero and value == 0)
            for value, minimum, maximum, inclusive_zero in numeric_bounds
        ):
            raise ValueError("invalid_scan_limits")


@dataclass(frozen=True)
class SourceReadiness:
    ready: bool
    code: str | None = None


@dataclass(frozen=True)
class ScanDiagnostic:
    code: str
    path_digest: str | None = None


@dataclass(frozen=True)
class FileIdentity:
    device: int
    inode: int
    mode: int
    size: int
    mtime_ns: int

    @classmethod
    def from_stat(cls, value: os.stat_result) -> FileIdentity:
        return cls(
            device=value.st_dev,
            inode=value.st_ino,
            mode=value.st_mode,
            size=value.st_size,
            mtime_ns=value.st_mtime_ns,
        )

    @property
    def is_directory(self) -> bool:
        return stat.S_ISDIR(self.mode)

    @property
    def is_regular(self) -> bool:
        return stat.S_ISREG(self.mode)

    @property
    def is_symlink(self) -> bool:
        return stat.S_ISLNK(self.mode)


@dataclass(frozen=True)
class ScannedNote:
    relative_path: str = field(repr=False)
    path_digest: str
    data: bytes = field(repr=False)
    content_sha256: str
    identity: FileIdentity


@dataclass(frozen=True)
class ScanResult:
    notes: tuple[ScannedNote, ...]
    diagnostics: tuple[ScanDiagnostic, ...]
    bytes_read: int
    files_examined: int
    entries_examined: int
    next_cursor: str | None = None
    concurrency_used: int = 1


@dataclass(frozen=True)
class DirectoryEntry:
    name: str
    identity: FileIdentity


class UnixFileSystem:
    """Injectable descriptor-oriented Unix filesystem operations."""

    def open_absolute_directory(self, path: Path) -> int:
        current_fd = os.open("/", _DIRECTORY_FLAGS)
        try:
            for part in path.parts[1:]:
                next_fd = self.open_directory_at(current_fd, part)
                os.close(current_fd)
                current_fd = next_fd
            return current_fd
        except BaseException:
            os.close(current_fd)
            raise

    def open_directory_at(self, directory_fd: int, name: str) -> int:
        return os.open(name, _DIRECTORY_FLAGS, dir_fd=directory_fd)

    def open_file_at(self, directory_fd: int, name: str) -> int:
        return os.open(name, _FILE_FLAGS, dir_fd=directory_fd)

    def duplicate(self, file_fd: int) -> int:
        return os.dup(file_fd)

    def stat_at(self, directory_fd: int, name: str) -> FileIdentity:
        return FileIdentity.from_stat(os.stat(name, dir_fd=directory_fd, follow_symlinks=False))

    def fstat(self, file_fd: int) -> FileIdentity:
        return FileIdentity.from_stat(os.fstat(file_fd))

    def scan_directory(self, directory_fd: int, max_entries: int) -> tuple[DirectoryEntry, ...]:
        duplicate = self.duplicate(directory_fd)
        try:
            with os.scandir(duplicate) as iterator:
                entries: list[DirectoryEntry] = []
                for entry in iterator:
                    entries.append(
                        DirectoryEntry(
                            name=entry.name,
                            identity=FileIdentity.from_stat(entry.stat(follow_symlinks=False)),
                        )
                    )
                    if len(entries) >= max_entries:
                        raise _EntryLimitError
        finally:
            os.close(duplicate)
        return tuple(entries)

    def read_file(self, file_fd: int, byte_limit: int) -> bytes:
        chunks: list[bytes] = []
        remaining = byte_limit
        while remaining:
            chunk = os.read(file_fd, min(remaining, 64 * 1024))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def close(self, file_fd: int) -> None:
        os.close(file_fd)


@dataclass
class _VaultMount:
    root_path: Path
    root_fd: int
    root_identity: FileIdentity
    vault_fd: int
    vault_identity: FileIdentity
    vault_parts: tuple[str, ...]
    ingest_fd: int
    ingest_identity: FileIdentity
    ingest_parts: tuple[str, ...]

    def close(self, filesystem: UnixFileSystem) -> None:
        filesystem.close(self.ingest_fd)
        filesystem.close(self.vault_fd)
        filesystem.close(self.root_fd)

    def verify(self, filesystem: UnixFileSystem) -> bool:
        try:
            root_fd = filesystem.open_absolute_directory(self.root_path)
            try:
                current_root = filesystem.fstat(root_fd)
                if (
                    current_root.device != self.root_identity.device
                    or current_root.inode != self.root_identity.inode
                    or not current_root.is_directory
                ):
                    return False
                vault_fd = _open_relative_directory(filesystem, root_fd, self.vault_parts)
                try:
                    current_vault = filesystem.fstat(vault_fd)
                    if (
                        current_vault.device != self.vault_identity.device
                        or current_vault.inode != self.vault_identity.inode
                        or not current_vault.is_directory
                    ):
                        return False
                    ingest_fd = _open_relative_directory(filesystem, vault_fd, self.ingest_parts)
                    try:
                        current_ingest = filesystem.fstat(ingest_fd)
                        return (
                            current_ingest.device == self.ingest_identity.device
                            and current_ingest.inode == self.ingest_identity.inode
                            and current_ingest.is_directory
                        )
                    finally:
                        filesystem.close(ingest_fd)
                finally:
                    filesystem.close(vault_fd)
            finally:
                filesystem.close(root_fd)
        except OSError:
            return False


def _open_relative_directory(
    filesystem: UnixFileSystem,
    starting_fd: int,
    parts: Sequence[str],
) -> int:
    current_fd = filesystem.duplicate(starting_fd)
    try:
        for part in parts:
            next_fd = filesystem.open_directory_at(current_fd, part)
            filesystem.close(current_fd)
            current_fd = next_fd
        return current_fd
    except BaseException:
        filesystem.close(current_fd)
        raise


def _open_mount_from_root(
    *,
    filesystem: UnixFileSystem,
    root: Path,
    vault: Path,
    ingest_parts: tuple[str, ...],
) -> _VaultMount:
    root_fd = filesystem.open_absolute_directory(root)
    try:
        root_identity = filesystem.fstat(root_fd)
        if not root_identity.is_directory:
            raise OSError(errno.ENOTDIR, "not a directory")
        vault_parts = tuple(vault.relative_to(root).parts)
        vault_fd = _open_relative_directory(filesystem, root_fd, vault_parts)
        try:
            vault_identity = filesystem.fstat(vault_fd)
            if not vault_identity.is_directory:
                raise OSError(errno.ENOTDIR, "not a directory")
            ingest_fd = _open_relative_directory(filesystem, vault_fd, ingest_parts)
            try:
                ingest_identity = filesystem.fstat(ingest_fd)
                if not ingest_identity.is_directory:
                    raise OSError(errno.ENOTDIR, "not a directory")
                return _VaultMount(
                    root_path=root,
                    root_fd=root_fd,
                    root_identity=root_identity,
                    vault_fd=vault_fd,
                    vault_identity=vault_identity,
                    vault_parts=vault_parts,
                    ingest_fd=ingest_fd,
                    ingest_identity=ingest_identity,
                    ingest_parts=ingest_parts,
                )
            except BaseException:
                filesystem.close(ingest_fd)
                raise
        except BaseException:
            filesystem.close(vault_fd)
            raise
    except BaseException:
        filesystem.close(root_fd)
        raise


class AllowedRootPolicy:
    """Fail-closed deployment root policy; source overrides can only narrow it."""

    def __init__(self, deployment_roots: Sequence[str | Path]) -> None:
        self._deployment_roots = tuple(deployment_roots)

    def open_mount(
        self,
        *,
        filesystem: UnixFileSystem,
        vault_path: str | Path,
        ingest_folder: str,
        narrowed_roots: Sequence[str | Path] | None,
        compatible_worker: bool,
    ) -> _VaultMount:
        if not compatible_worker or not self._deployment_roots:
            raise _UnavailableError
        try:
            vault = _validated_absolute_path(vault_path)
            deployment_roots = tuple(
                _validated_absolute_path(root) for root in self._deployment_roots
            )
            containing_deployment_roots = tuple(
                root for root in deployment_roots if _path_is_within(vault, root)
            )
            if not containing_deployment_roots:
                raise _UnavailableError

            effective_roots = containing_deployment_roots
            if narrowed_roots is not None:
                if not narrowed_roots:
                    raise _UnavailableError
                narrowed = tuple(_validated_absolute_path(root) for root in narrowed_roots)
                if any(
                    not any(_path_is_within(root, deployed) for deployed in deployment_roots)
                    for root in narrowed
                ):
                    raise _UnavailableError
                effective_roots = tuple(root for root in narrowed if _path_is_within(vault, root))
                if not effective_roots:
                    raise _UnavailableError

            ingest_parts = validate_relative_path(ingest_folder)
            for root in effective_roots:
                try:
                    return _open_mount_from_root(
                        filesystem=filesystem,
                        root=root,
                        vault=vault,
                        ingest_parts=ingest_parts,
                    )
                except OSError:
                    continue
            raise _UnavailableError
        except (OSError, ValueError) as exc:
            if isinstance(exc, _UnavailableError):
                raise
            raise _UnavailableError from None


@dataclass
class _ScanState:
    start_time: float
    notes: list[ScannedNote] = field(default_factory=list)
    diagnostics: list[ScanDiagnostic] = field(default_factory=list)
    bytes_read: int = 0
    files_examined: int = 0
    entries_examined: int = 0
    cursor_seen: bool = True
    last_cursor: str | None = None
    next_cursor: str | None = None
    stopped: bool = False


class VaultScanner:
    """Perform one deterministic, bounded, descriptor-relative vault scan."""

    def __init__(
        self,
        *,
        policy: AllowedRootPolicy,
        vault_path: str | Path,
        ingest_folder: str,
        limits: ScanLimits,
        filesystem: UnixFileSystem | None = None,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
        narrowed_roots: Sequence[str | Path] | None = None,
        compatible_worker: bool = True,
    ) -> None:
        self._policy = policy
        self._vault_path = vault_path
        self._ingest_folder = ingest_folder
        self._limits = limits
        self._filesystem = filesystem or UnixFileSystem()
        self._clock = clock or time.monotonic
        self._sleeper = sleeper or time.sleep
        self._narrowed_roots = narrowed_roots
        self._compatible_worker = compatible_worker

    def _open_mount(self) -> _VaultMount:
        return self._policy.open_mount(
            filesystem=self._filesystem,
            vault_path=self._vault_path,
            ingest_folder=self._ingest_folder,
            narrowed_roots=self._narrowed_roots,
            compatible_worker=self._compatible_worker,
        )

    def readiness(self) -> SourceReadiness:
        try:
            mount = self._open_mount()
        except _UnavailableError:
            return SourceReadiness(ready=False, code="source_unavailable")
        mount.close(self._filesystem)
        return SourceReadiness(ready=True)

    def scan(
        self,
        *,
        cursor: str | None = None,
        checkpoint: Callable[[], None] | None = None,
    ) -> ScanResult:
        if checkpoint is not None:
            checkpoint()
        try:
            mount = self._open_mount()
        except _UnavailableError:
            return ScanResult(
                notes=(),
                diagnostics=(ScanDiagnostic("source_unavailable"),),
                bytes_read=0,
                files_examined=0,
                entries_examined=0,
            )

        state = _ScanState(start_time=self._clock(), cursor_seen=cursor is None)
        try:
            self._walk_directory(
                mount=mount,
                directory_fd=mount.ingest_fd,
                relative_parts=(),
                depth=0,
                cursor=cursor,
                state=state,
                checkpoint=checkpoint,
            )
            if cursor is not None and not state.cursor_seen and not state.stopped:
                state.diagnostics.append(ScanDiagnostic("invalid_cursor"))
        finally:
            mount.close(self._filesystem)

        return ScanResult(
            notes=tuple(state.notes),
            diagnostics=tuple(state.diagnostics),
            bytes_read=state.bytes_read,
            files_examined=state.files_examined,
            entries_examined=state.entries_examined,
            next_cursor=state.next_cursor,
            concurrency_used=1,
        )

    def _walk_directory(
        self,
        *,
        mount: _VaultMount,
        directory_fd: int,
        relative_parts: tuple[str, ...],
        depth: int,
        cursor: str | None,
        state: _ScanState,
        checkpoint: Callable[[], None] | None,
    ) -> None:
        if checkpoint is not None:
            checkpoint()
        if state.stopped or self._stop_for_duration(state):
            return
        remaining_entries = self._limits.max_entries - state.entries_examined
        if remaining_entries <= 0:
            state.diagnostics.append(ScanDiagnostic("scan_entry_limit"))
            state.next_cursor = state.last_cursor
            state.stopped = True
            return
        try:
            entries = sorted(
                self._filesystem.scan_directory(directory_fd, remaining_entries),
                key=lambda entry: (
                    unicodedata.normalize("NFC", entry.name),
                    entry.name,
                ),
            )
        except _EntryLimitError:
            state.entries_examined += remaining_entries
            state.diagnostics.append(ScanDiagnostic("scan_entry_limit"))
            state.next_cursor = state.last_cursor
            state.stopped = True
            return
        except OSError:
            state.diagnostics.append(ScanDiagnostic("directory_unavailable"))
            return
        state.entries_examined += len(entries)

        canonical_counts: dict[str, int] = {}
        for entry in entries:
            canonical_name = unicodedata.normalize("NFC", entry.name)
            canonical_counts[canonical_name] = canonical_counts.get(canonical_name, 0) + 1
        collisions = {
            canonical_name for canonical_name, count in canonical_counts.items() if count > 1
        }
        diagnosed_collisions: set[str] = set()

        for entry in entries:
            if checkpoint is not None:
                checkpoint()
            if state.stopped or self._stop_for_duration(state):
                return
            raw_name = entry.name
            name = unicodedata.normalize("NFC", entry.name)
            current_parts = (*relative_parts, name)
            relative_path = "/".join(current_parts)
            path_digest = hashlib.sha256(relative_path.encode()).hexdigest()
            try:
                validate_relative_path(relative_path)
            except ValueError:
                state.diagnostics.append(ScanDiagnostic("unsafe_path", path_digest))
                continue

            if name in collisions:
                if name not in diagnosed_collisions:
                    state.diagnostics.append(ScanDiagnostic("normalization_collision", path_digest))
                    diagnosed_collisions.add(name)
                continue
            if entry.identity.is_symlink:
                state.diagnostics.append(ScanDiagnostic("unsafe_path", path_digest))
                continue
            if entry.identity.is_directory:
                if name.casefold() in _EXPORT_DIRECTORY_NAMES:
                    continue
                if depth >= self._limits.max_depth:
                    state.diagnostics.append(ScanDiagnostic("scan_depth_limit", path_digest))
                    continue
                try:
                    child_fd = self._filesystem.open_directory_at(directory_fd, raw_name)
                except OSError as exc:
                    code = "unsafe_path" if _is_no_follow_error(exc) else "directory_unavailable"
                    state.diagnostics.append(ScanDiagnostic(code, path_digest))
                    continue
                try:
                    opened = self._filesystem.fstat(child_fd)
                    if not opened.is_directory or opened != entry.identity:
                        state.diagnostics.append(ScanDiagnostic("unsafe_path", path_digest))
                        continue
                    self._walk_directory(
                        mount=mount,
                        directory_fd=child_fd,
                        relative_parts=current_parts,
                        depth=depth + 1,
                        cursor=cursor,
                        state=state,
                        checkpoint=checkpoint,
                    )
                finally:
                    self._filesystem.close(child_fd)
                continue

            if _skip_filename(name) or not name.casefold().endswith(".md"):
                continue
            if not state.cursor_seen:
                if path_digest == cursor:
                    state.cursor_seen = True
                continue
            if state.files_examined >= self._limits.max_files:
                state.diagnostics.append(ScanDiagnostic("scan_file_limit"))
                state.next_cursor = state.last_cursor
                state.stopped = True
                return

            state.files_examined += 1
            if not entry.identity.is_regular:
                state.diagnostics.append(ScanDiagnostic("non_regular_file", path_digest))
                state.last_cursor = path_digest
                continue
            if checkpoint is not None:
                checkpoint()
            self._read_candidate(
                mount=mount,
                directory_fd=directory_fd,
                name=raw_name,
                relative_path=relative_path,
                path_digest=path_digest,
                enumerated_identity=entry.identity,
                state=state,
            )
            if not state.stopped:
                state.last_cursor = path_digest

    def _read_candidate(
        self,
        *,
        mount: _VaultMount,
        directory_fd: int,
        name: str,
        relative_path: str,
        path_digest: str,
        enumerated_identity: FileIdentity,
        state: _ScanState,
    ) -> None:
        try:
            before_settle = self._filesystem.stat_at(directory_fd, name)
        except OSError:
            state.diagnostics.append(ScanDiagnostic("unsafe_path", path_digest))
            return
        if before_settle.is_symlink:
            state.diagnostics.append(ScanDiagnostic("unsafe_path", path_digest))
            return
        if not before_settle.is_regular:
            state.diagnostics.append(ScanDiagnostic("non_regular_file", path_digest))
            return
        if before_settle != enumerated_identity:
            state.diagnostics.append(ScanDiagnostic("file_unstable", path_digest))
            return
        if before_settle.size > self._limits.max_note_bytes:
            state.diagnostics.append(ScanDiagnostic("note_too_large", path_digest))
            return
        if before_settle.size > self._limits.max_total_bytes - state.bytes_read:
            state.diagnostics.append(ScanDiagnostic("scan_byte_limit"))
            state.next_cursor = state.last_cursor
            state.stopped = True
            return

        if self._limits.settle_seconds:
            try:
                self._sleeper(self._limits.settle_seconds)
            except Exception:
                state.diagnostics.append(ScanDiagnostic("file_unstable", path_digest))
                return
        if not mount.verify(self._filesystem):
            state.diagnostics.append(ScanDiagnostic("unsafe_path", path_digest))
            state.stopped = True
            return
        try:
            settled = self._filesystem.stat_at(directory_fd, name)
        except OSError:
            state.diagnostics.append(ScanDiagnostic("unsafe_path", path_digest))
            return
        if settled.is_symlink:
            state.diagnostics.append(ScanDiagnostic("unsafe_path", path_digest))
            return
        if settled != before_settle:
            state.diagnostics.append(ScanDiagnostic("file_unstable", path_digest))
            return
        if settled.size > self._limits.max_note_bytes:
            state.diagnostics.append(ScanDiagnostic("note_too_large", path_digest))
            return
        if settled.size > self._limits.max_total_bytes - state.bytes_read:
            state.diagnostics.append(ScanDiagnostic("scan_byte_limit"))
            state.next_cursor = state.last_cursor
            state.stopped = True
            return

        try:
            file_fd = self._filesystem.open_file_at(directory_fd, name)
        except OSError:
            state.diagnostics.append(ScanDiagnostic("unsafe_path", path_digest))
            return
        try:
            try:
                opened = self._filesystem.fstat(file_fd)
                if not opened.is_regular or opened != settled:
                    state.diagnostics.append(ScanDiagnostic("file_unstable", path_digest))
                    return
                data = self._filesystem.read_file(file_fd, opened.size)
                state.bytes_read += len(data)
                after_read = self._filesystem.fstat(file_fd)
                try:
                    after_path = self._filesystem.stat_at(directory_fd, name)
                except OSError:
                    state.diagnostics.append(ScanDiagnostic("unsafe_path", path_digest))
                    return
                if after_path.is_symlink:
                    state.diagnostics.append(ScanDiagnostic("unsafe_path", path_digest))
                    return
                if (
                    opened != after_read
                    or opened != after_path
                    or len(data) != opened.size
                    or not mount.verify(self._filesystem)
                ):
                    state.diagnostics.append(ScanDiagnostic("file_unstable", path_digest))
                    return
                if _is_aca_generated(data):
                    state.diagnostics.append(ScanDiagnostic("generated_content", path_digest))
                    return
                state.notes.append(
                    ScannedNote(
                        relative_path=relative_path,
                        path_digest=path_digest,
                        data=data,
                        content_sha256=hashlib.sha256(data).hexdigest(),
                        identity=opened,
                    )
                )
            except OSError:
                state.diagnostics.append(ScanDiagnostic("file_unavailable", path_digest))
        finally:
            self._filesystem.close(file_fd)

    def _stop_for_duration(self, state: _ScanState) -> bool:
        if self._clock() - state.start_time <= self._limits.max_duration_seconds:
            return False
        if not state.stopped:
            state.diagnostics.append(ScanDiagnostic("scan_duration_limit"))
        state.next_cursor = state.last_cursor
        state.stopped = True
        return True


def _is_no_follow_error(exc: OSError) -> bool:
    return exc.errno in {errno.ELOOP, errno.ENOTDIR}


def _skip_filename(name: str) -> bool:
    folded = name.casefold()
    return name.startswith(".~") or folded in _METADATA_NAMES or folded.endswith(_TEMP_SUFFIXES)


def _is_aca_generated(data: bytes) -> bool:
    """Recognize exporter ownership metadata without parsing or following links."""

    lines = data.splitlines()
    if not lines or lines[0] != b"---":
        return False
    generated = False
    for line in lines[1:]:
        if line.strip() == b"---":
            return generated
        key, separator, value = line.partition(b":")
        if separator and key.strip().lower() == b"generator":
            generated = value.strip().strip(b"\"'").lower() == b"aca"
    return False
