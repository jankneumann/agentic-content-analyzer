"""Security and resource-bound tests for worker-local Obsidian vault scanning."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from src.ingestion.obsidian_scanner import (
    HARD_MAX_CONCURRENCY,
    HARD_MAX_DEPTH,
    HARD_MAX_DURATION_SECONDS,
    HARD_MAX_FILES,
    HARD_MAX_NOTE_BYTES,
    HARD_MAX_SETTLE_SECONDS,
    HARD_MAX_TOTAL_BYTES,
    AllowedRootPolicy,
    DirectoryEntry,
    FileIdentity,
    ScanLimits,
    UnixFileSystem,
    VaultScanner,
    validate_relative_path,
)


def _note(body: str = "body") -> str:
    return (
        "---\n"
        "source_url: https://example.com/article\n"
        "captured_at: 2026-08-02T10:00:00Z\n"
        "---\n"
        f"{body}\n"
    )


def _vault(tmp_path: Path) -> tuple[Path, Path]:
    approved = tmp_path / "approved"
    inbox = approved / "vault" / "Inbox"
    inbox.mkdir(parents=True)
    return approved, inbox


def _scanner(
    approved: Path,
    *,
    limits: ScanLimits | None = None,
    filesystem: UnixFileSystem | None = None,
    clock: Callable[[], float] | None = None,
    sleeper: Callable[[float], None] | None = None,
    ingest_folder: str = "Inbox",
    narrowed_roots: tuple[Path, ...] | None = None,
    compatible_worker: bool = True,
) -> VaultScanner:
    return VaultScanner(
        policy=AllowedRootPolicy((approved,)),
        vault_path=approved / "vault",
        ingest_folder=ingest_folder,
        limits=limits or ScanLimits(settle_seconds=0),
        filesystem=filesystem,
        clock=clock,
        sleeper=sleeper,
        narrowed_roots=narrowed_roots,
        compatible_worker=compatible_worker,
    )


def _codes(scanner: VaultScanner) -> list[str]:
    return [diagnostic.code for diagnostic in scanner.scan().diagnostics]


def test_empty_deployment_allowed_roots_disable_source_without_leaking_path(tmp_path: Path) -> None:
    private_path = tmp_path / "private-vault"
    scanner = VaultScanner(
        policy=AllowedRootPolicy(()),
        vault_path=private_path,
        ingest_folder="Inbox",
        limits=ScanLimits(),
    )

    readiness = scanner.readiness()
    result = scanner.scan()

    assert readiness.ready is False
    assert readiness.code == "source_unavailable"
    assert str(private_path) not in repr(readiness)
    assert [item.code for item in result.diagnostics] == ["source_unavailable"]
    assert str(private_path) not in repr(result.diagnostics)


@pytest.mark.parametrize("compatible_worker", [True, False])
def test_missing_or_incompatible_worker_mount_fails_closed_without_path(
    tmp_path: Path, compatible_worker: bool
) -> None:
    approved = tmp_path / "approved"
    approved.mkdir()
    private_path = approved / "missing-vault"
    scanner = _scanner(
        approved,
        compatible_worker=compatible_worker,
    )
    if compatible_worker:
        scanner = VaultScanner(
            policy=AllowedRootPolicy((approved,)),
            vault_path=private_path,
            ingest_folder="Inbox",
            limits=ScanLimits(),
        )

    readiness = scanner.readiness()

    assert readiness.ready is False
    assert readiness.code == "source_unavailable"
    assert str(private_path) not in repr(readiness)


def test_override_may_narrow_but_cannot_widen_deployment_roots(tmp_path: Path) -> None:
    approved, inbox = _vault(tmp_path)
    narrowed = approved / "vault"
    inbox.joinpath("clip.md").write_text(_note())

    allowed = _scanner(approved, narrowed_roots=(narrowed,))
    widened = _scanner(approved, narrowed_roots=(tmp_path,))

    assert allowed.readiness().ready is True
    assert widened.readiness().ready is False
    assert widened.readiness().code == "source_unavailable"


@pytest.mark.parametrize(
    "value",
    ["/absolute", "../escape", "safe/../../escape", "safe\x00escape", "safe/./note.md"],
)
def test_relative_paths_reject_absolute_traversal_nul_and_dot_components(value: str) -> None:
    with pytest.raises(ValueError, match="unsafe_path"):
        validate_relative_path(value)


def test_symlink_in_deployment_root_path_fails_closed(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    (real / "vault" / "Inbox").mkdir(parents=True)
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)

    scanner = _scanner(alias)

    assert scanner.readiness().ready is False
    assert scanner.readiness().code == "source_unavailable"


class _RecordingDirectoryFileSystem(UnixFileSystem):
    def __init__(self) -> None:
        self.absolute_directories: list[Path] = []

    def open_absolute_directory(self, path: Path) -> int:
        self.absolute_directories.append(path)
        return super().open_absolute_directory(path)


def test_vault_is_opened_relative_to_the_already_open_approved_root(
    tmp_path: Path,
) -> None:
    approved, inbox = _vault(tmp_path)
    inbox.joinpath("clip.md").write_text(_note())
    filesystem = _RecordingDirectoryFileSystem()

    result = _scanner(approved, filesystem=filesystem).scan()

    assert len(result.notes) == 1
    assert filesystem.absolute_directories
    assert set(filesystem.absolute_directories) == {approved}


class _DecomposedNameFileSystem(UnixFileSystem):
    def __init__(self, raw_name: str) -> None:
        self.raw_name = raw_name
        self.descriptor_names: list[str] = []

    def scan_directory(
        self, directory_fd: int, max_entries: int = 10_000
    ) -> tuple[DirectoryEntry, ...]:
        entries = super().scan_directory(directory_fd, max_entries)
        assert len(entries) == 1
        return (DirectoryEntry(self.raw_name, entries[0].identity),)

    def stat_at(self, directory_fd: int, name: str) -> FileIdentity:
        self.descriptor_names.append(name)
        if name != self.raw_name:
            raise FileNotFoundError
        return super().stat_at(directory_fd, name)

    def open_file_at(self, directory_fd: int, name: str) -> int:
        self.descriptor_names.append(name)
        if name != self.raw_name:
            raise FileNotFoundError
        return super().open_file_at(directory_fd, name)


def test_decomposed_unicode_name_uses_raw_descriptor_spelling_and_canonical_output(
    tmp_path: Path,
) -> None:
    approved, inbox = _vault(tmp_path)
    raw_name = "cafe\u0301.md"
    inbox.joinpath(raw_name).write_text(_note("decomposed"))
    filesystem = _DecomposedNameFileSystem(raw_name)

    result = _scanner(approved, filesystem=filesystem).scan()

    assert [note.relative_path for note in result.notes] == ["café.md"]
    assert set(filesystem.descriptor_names) == {raw_name}


class _NormalizationCollisionFileSystem(UnixFileSystem):
    def __init__(self, backing_file: Path) -> None:
        self.backing_file = backing_file
        self.identity = FileIdentity.from_stat(backing_file.stat())
        self.opened_names: list[str] = []

    def scan_directory(
        self, directory_fd: int, max_entries: int | None = None
    ) -> tuple[DirectoryEntry, ...]:
        return (
            DirectoryEntry("cafe\u0301.md", self.identity),
            DirectoryEntry("café.md", self.identity),
        )

    def stat_at(self, directory_fd: int, name: str) -> FileIdentity:
        return self.identity

    def open_file_at(self, directory_fd: int, name: str) -> int:
        self.opened_names.append(name)
        return os.open(self.backing_file, os.O_RDONLY)


def test_normalization_equivalent_names_are_rejected_without_opening_either(
    tmp_path: Path,
) -> None:
    approved, inbox = _vault(tmp_path)
    backing_file = inbox / "backing"
    backing_file.write_text(_note("ambiguous"))
    filesystem = _NormalizationCollisionFileSystem(backing_file)

    result = _scanner(approved, filesystem=filesystem).scan()

    assert result.notes == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["normalization_collision"]
    assert filesystem.opened_names == []


def test_nested_directory_symlink_is_rejected_without_reading_target(tmp_path: Path) -> None:
    approved, inbox = _vault(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    outside.joinpath("secret.md").write_text("TOP-SECRET")
    inbox.joinpath("linked").symlink_to(outside, target_is_directory=True)
    inbox.joinpath("safe.md").write_text(_note("safe"))

    result = _scanner(approved).scan()

    assert [note.data.decode() for note in result.notes] == [_note("safe")]
    assert "unsafe_path" in [item.code for item in result.diagnostics]
    assert "TOP-SECRET" not in repr(result)


def test_leaf_symlink_and_non_regular_file_are_rejected(tmp_path: Path) -> None:
    approved, inbox = _vault(tmp_path)
    outside = tmp_path / "secret.md"
    outside.write_text("TOP-SECRET")
    inbox.joinpath("link.md").symlink_to(outside)
    fifo = inbox / "pipe.md"
    os.mkfifo(fifo)

    result = _scanner(approved).scan()

    assert result.notes == ()
    assert [item.code for item in result.diagnostics] == [
        "unsafe_path",
        "non_regular_file",
    ]
    assert "TOP-SECRET" not in repr(result)


class _SwapBeforeOpenFileSystem(UnixFileSystem):
    def __init__(self, leaf: Path, target: Path) -> None:
        self._leaf = leaf
        self._target = target
        self._swapped = False

    def open_file_at(self, directory_fd: int, name: str) -> int:
        if name == self._leaf.name and not self._swapped:
            self._swapped = True
            self._leaf.unlink()
            self._leaf.symlink_to(self._target)
        return super().open_file_at(directory_fd, name)


def test_swap_after_enumeration_is_blocked_by_no_follow_open(tmp_path: Path) -> None:
    approved, inbox = _vault(tmp_path)
    leaf = inbox / "clip.md"
    leaf.write_text(_note("safe"))
    secret = tmp_path / "secret.md"
    secret.write_text("TOP-SECRET")

    scanner = _scanner(
        approved,
        filesystem=_SwapBeforeOpenFileSystem(leaf, secret),
    )
    result = scanner.scan()

    assert result.notes == ()
    assert [item.code for item in result.diagnostics] == ["unsafe_path"]
    assert "TOP-SECRET" not in repr(result)


def test_root_replacement_during_settle_defers_without_reading_replacement(tmp_path: Path) -> None:
    approved, inbox = _vault(tmp_path)
    inbox.joinpath("clip.md").write_text(_note("safe"))
    old_vault = approved / "old-vault"

    def replace_root(_seconds: float) -> None:
        (approved / "vault").rename(old_vault)
        replacement = approved / "vault" / "Inbox"
        replacement.mkdir(parents=True)
        replacement.joinpath("clip.md").write_text("TOP-SECRET")

    scanner = _scanner(
        approved,
        limits=ScanLimits(settle_seconds=0.01),
        sleeper=replace_root,
    )
    result = scanner.scan()

    assert result.notes == ()
    assert [item.code for item in result.diagnostics] == ["unsafe_path"]
    assert "TOP-SECRET" not in repr(result)


@pytest.mark.parametrize("mutation", ["same_size", "partial", "inode"])
def test_settle_check_defers_same_size_partial_and_inode_changes(
    tmp_path: Path, mutation: str
) -> None:
    approved, inbox = _vault(tmp_path)
    leaf = inbox / "clip.md"
    original = _note("AAAA")
    leaf.write_text(original)

    def mutate(_seconds: float) -> None:
        if mutation == "same_size":
            previous = leaf.stat().st_mtime_ns
            leaf.write_text(_note("BBBB"))
            os.utime(leaf, ns=(previous + 1_000_000, previous + 1_000_000))
        elif mutation == "partial":
            leaf.write_text(original + "partial")
        else:
            replacement = inbox / "replacement.md"
            replacement.write_text(original)
            os.replace(replacement, leaf)

    result = _scanner(
        approved,
        limits=ScanLimits(settle_seconds=0.01),
        sleeper=mutate,
    ).scan()

    assert result.notes == ()
    assert [item.code for item in result.diagnostics] == ["file_unstable"]


class _MutateAfterReadFileSystem(UnixFileSystem):
    def __init__(self, leaf: Path) -> None:
        self._leaf = leaf
        self._mutated = False

    def read_file(self, file_fd: int, byte_limit: int) -> bytes:
        data = super().read_file(file_fd, byte_limit)
        if not self._mutated:
            self._mutated = True
            self._leaf.write_text(_note("changed-after-read"))
        return data


def test_post_read_restat_defers_file_changed_during_read(tmp_path: Path) -> None:
    approved, inbox = _vault(tmp_path)
    leaf = inbox / "clip.md"
    leaf.write_text(_note("before"))

    result = _scanner(
        approved,
        filesystem=_MutateAfterReadFileSystem(leaf),
    ).scan()

    assert result.notes == ()
    assert [item.code for item in result.diagnostics] == ["file_unstable"]


def test_scan_is_stably_sorted_and_cursor_resumes_without_exposing_path(tmp_path: Path) -> None:
    approved, inbox = _vault(tmp_path)
    for name in ("c.md", "a.md", "b.md"):
        inbox.joinpath(name).write_text(_note(name))
    scanner = _scanner(approved, limits=ScanLimits(max_files=2, settle_seconds=0))

    first = scanner.scan()
    second = scanner.scan(cursor=first.next_cursor)

    assert [note.relative_path for note in first.notes] == ["a.md", "b.md"]
    assert [note.relative_path for note in second.notes] == ["c.md"]
    assert first.next_cursor is not None
    assert "b.md" not in first.next_cursor
    assert [item.code for item in first.diagnostics] == ["scan_file_limit"]


def test_total_byte_limit_stops_before_reading_next_candidate(tmp_path: Path) -> None:
    approved, inbox = _vault(tmp_path)
    first_data = _note("first")
    inbox.joinpath("a.md").write_text(first_data)
    inbox.joinpath("b.md").write_text(_note("other"))

    result = _scanner(
        approved,
        limits=ScanLimits(
            max_total_bytes=len(first_data.encode()),
            max_note_bytes=len(first_data.encode()),
            settle_seconds=0,
        ),
    ).scan()

    assert [note.relative_path for note in result.notes] == ["a.md"]
    assert [item.code for item in result.diagnostics] == ["scan_byte_limit"]
    assert result.bytes_read == len(first_data.encode())


def test_byte_limit_cursor_resumes_after_last_completed_candidate(tmp_path: Path) -> None:
    approved, inbox = _vault(tmp_path)
    note_data = _note("same-size")
    for name in ("a.md", "b.md", "c.md"):
        inbox.joinpath(name).write_text(note_data)
    scanner = _scanner(
        approved,
        limits=ScanLimits(
            max_total_bytes=len(note_data.encode()),
            max_note_bytes=len(note_data.encode()),
            settle_seconds=0,
        ),
    )

    first = scanner.scan()
    second = scanner.scan(cursor=first.next_cursor)

    assert [note.relative_path for note in first.notes] == ["a.md"]
    assert [note.relative_path for note in second.notes] == ["b.md"]
    assert first.next_cursor is not None


def test_depth_limit_skips_deeper_directories_but_keeps_siblings(tmp_path: Path) -> None:
    approved, inbox = _vault(tmp_path)
    inbox.joinpath("root.md").write_text(_note("root"))
    level_one = inbox / "one"
    level_one.mkdir()
    level_one.joinpath("one.md").write_text(_note("one"))
    level_two = level_one / "two"
    level_two.mkdir()
    level_two.joinpath("two.md").write_text(_note("two"))

    result = _scanner(
        approved,
        limits=ScanLimits(max_depth=1, settle_seconds=0),
    ).scan()

    assert [note.relative_path for note in result.notes] == ["one/one.md", "root.md"]
    assert [item.code for item in result.diagnostics] == ["scan_depth_limit"]


class _AdvancingClock:
    def __init__(self, values: list[float]) -> None:
        self._values = iter(values)
        self._last = values[-1]

    def __call__(self) -> float:
        self._last = next(self._values, self._last)
        return self._last


def test_duration_limit_is_deterministic_with_injected_clock(tmp_path: Path) -> None:
    approved, inbox = _vault(tmp_path)
    inbox.joinpath("a.md").write_text(_note("a"))
    inbox.joinpath("b.md").write_text(_note("b"))
    clock = _AdvancingClock([0.0, 0.0, 0.0, 2.0])

    result = _scanner(
        approved,
        limits=ScanLimits(max_duration_seconds=1, settle_seconds=0),
        clock=clock,
    ).scan()

    assert len(result.notes) <= 1
    assert "scan_duration_limit" in [item.code for item in result.diagnostics]


def test_note_size_limit_skips_oversized_note_without_returning_bytes(tmp_path: Path) -> None:
    approved, inbox = _vault(tmp_path)
    inbox.joinpath("large.md").write_bytes(b"12345")

    result = _scanner(
        approved,
        limits=ScanLimits(max_note_bytes=4, settle_seconds=0),
    ).scan()

    assert result.notes == ()
    assert result.bytes_read == 0
    assert [item.code for item in result.diagnostics] == ["note_too_large"]


def test_note_size_limit_cannot_exceed_total_byte_limit() -> None:
    with pytest.raises(ValueError, match="invalid_scan_limits"):
        ScanLimits(max_note_bytes=5, max_total_bytes=4)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_files", HARD_MAX_FILES + 1),
        ("max_total_bytes", HARD_MAX_TOTAL_BYTES + 1),
        ("max_depth", HARD_MAX_DEPTH + 1),
        ("max_duration_seconds", HARD_MAX_DURATION_SECONDS + 1),
        ("max_note_bytes", HARD_MAX_NOTE_BYTES + 1),
        ("settle_seconds", HARD_MAX_SETTLE_SECONDS + 1),
        ("max_concurrency", HARD_MAX_CONCURRENCY + 1),
        ("max_duration_seconds", float("nan")),
        ("settle_seconds", float("nan")),
        ("max_entries", 100_001),
    ],
)
def test_scan_limits_reject_values_above_hard_ceiling(field: str, value: int | float) -> None:
    with pytest.raises(ValueError, match="invalid_scan_limits"):
        ScanLimits(**cast("dict[str, Any]", {field: value}))


def test_scanner_is_serial_and_reports_bounded_concurrency(tmp_path: Path) -> None:
    approved, inbox = _vault(tmp_path)
    inbox.joinpath("clip.md").write_text(_note())

    result = _scanner(
        approved,
        limits=ScanLimits(max_concurrency=HARD_MAX_CONCURRENCY, settle_seconds=0),
    ).scan()

    assert result.concurrency_used == 1
    assert result.concurrency_used <= HARD_MAX_CONCURRENCY


def test_total_directory_fanout_is_bounded_before_non_markdown_entries_are_processed(
    tmp_path: Path,
) -> None:
    approved, inbox = _vault(tmp_path)
    inbox.joinpath("a.md").write_text(_note("first"))
    fanout = inbox / "z-fanout"
    fanout.mkdir()
    for index in range(10):
        fanout.joinpath(f"ignored-{index}.txt").write_text("ignored")
    scanner = _scanner(
        approved,
        limits=ScanLimits(max_entries=4, settle_seconds=0),
    )

    first = scanner.scan()
    resumed = scanner.scan(cursor=first.next_cursor)

    assert [note.relative_path for note in first.notes] == ["a.md"]
    assert first.entries_examined == 4
    assert [diagnostic.code for diagnostic in first.diagnostics] == ["scan_entry_limit"]
    assert first.next_cursor is not None
    assert resumed.notes == ()
    assert resumed.entries_examined == 4
    assert [diagnostic.code for diagnostic in resumed.diagnostics] == ["scan_entry_limit"]


class _BrokenDirectoryFileSystem(UnixFileSystem):
    def open_directory_at(self, directory_fd: int, name: str) -> int:
        if name == "broken":
            raise PermissionError("private filesystem detail")
        return super().open_directory_at(directory_fd, name)


class _CandidateOSErrorFileSystem(UnixFileSystem):
    def __init__(self, failure_phase: str) -> None:
        self.failure_phase = failure_phase
        self.target_fds: set[int] = set()
        self.after_read: set[int] = set()

    def open_file_at(self, directory_fd: int, name: str) -> int:
        file_fd = super().open_file_at(directory_fd, name)
        if name == "a-bad.md":
            self.target_fds.add(file_fd)
        return file_fd

    def fstat(self, file_fd: int) -> FileIdentity:
        if file_fd in self.target_fds and (
            self.failure_phase == "open_fstat"
            or (self.failure_phase == "post_read_fstat" and file_fd in self.after_read)
        ):
            raise OSError("private path and filesystem detail")
        return super().fstat(file_fd)

    def read_file(self, file_fd: int, byte_limit: int) -> bytes:
        if file_fd in self.target_fds and self.failure_phase == "read":
            raise OSError("private path and filesystem detail")
        data = super().read_file(file_fd, byte_limit)
        if file_fd in self.target_fds:
            self.after_read.add(file_fd)
        return data

    def close(self, file_fd: int) -> None:
        self.target_fds.discard(file_fd)
        self.after_read.discard(file_fd)
        super().close(file_fd)


@pytest.mark.parametrize("failure_phase", ["open_fstat", "read", "post_read_fstat"])
def test_candidate_io_error_is_redacted_and_does_not_abort_safe_siblings(
    tmp_path: Path, failure_phase: str
) -> None:
    approved, inbox = _vault(tmp_path)
    inbox.joinpath("a-bad.md").write_text(_note("bad"))
    inbox.joinpath("z-safe.md").write_text(_note("safe"))

    result = _scanner(
        approved,
        filesystem=_CandidateOSErrorFileSystem(failure_phase),
    ).scan()

    assert [note.relative_path for note in result.notes] == ["z-safe.md"]
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["file_unavailable"]
    assert "private path and filesystem detail" not in repr(result)


def test_directory_error_isolated_and_diagnostic_is_redacted(tmp_path: Path) -> None:
    approved, inbox = _vault(tmp_path)
    inbox.joinpath("ok.md").write_text(_note("ok"))
    broken = inbox / "broken"
    broken.mkdir()
    broken.joinpath("hidden.md").write_text("TOP-SECRET")

    result = _scanner(
        approved,
        filesystem=_BrokenDirectoryFileSystem(),
    ).scan()

    assert [note.relative_path for note in result.notes] == ["ok.md"]
    assert [item.code for item in result.diagnostics] == ["directory_unavailable"]
    assert "private filesystem detail" not in repr(result)
    assert str(broken) not in repr(result)


def test_temp_metadata_and_export_directories_are_ignored(tmp_path: Path) -> None:
    approved, inbox = _vault(tmp_path)
    inbox.joinpath("clip.md").write_text(_note("clip"))
    inbox.joinpath(".~draft.md").write_text("TEMP")
    inbox.joinpath("partial.md.part").write_text("TEMP")
    inbox.joinpath("clip.md.icloud").write_text("TEMP")
    for dirname in (".obsidian", "Digests", "Summaries", "Entities", "Themes", "Topics"):
        directory = inbox / dirname
        directory.mkdir()
        directory.joinpath("managed.md").write_text("TOP-SECRET")
    inbox.joinpath(".obsidian-sync-manifest.json").write_text("TOP-SECRET")

    result = _scanner(approved).scan()

    assert [note.relative_path for note in result.notes] == ["clip.md"]
    assert result.diagnostics == ()
    assert "TOP-SECRET" not in repr(result)


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_aca_generated_note_is_ignored_outside_export_directory(
    tmp_path: Path, newline: str
) -> None:
    approved, inbox = _vault(tmp_path)
    inbox.joinpath("generated.md").write_text(
        newline.join(("---", "generator: aca", 'aca_id: "digest-1"', "---", "# Generated", ""))
    )
    inbox.joinpath("clip.md").write_text(_note("clip"))

    result = _scanner(approved).scan()

    assert [note.relative_path for note in result.notes] == ["clip.md"]
    assert [item.code for item in result.diagnostics] == ["generated_content"]


class _RecordingFileSystem(UnixFileSystem):
    def __init__(self) -> None:
        self.opened_files: list[str] = []

    def open_file_at(self, directory_fd: int, name: str) -> int:
        self.opened_files.append(name)
        return super().open_file_at(directory_fd, name)


def test_embed_target_is_never_dereferenced(tmp_path: Path) -> None:
    approved, inbox = _vault(tmp_path)
    target = inbox / "attachment.pdf"
    target.write_text("TOP-SECRET")
    body = "Before ![[attachment.pdf]] after"
    inbox.joinpath("clip.md").write_text(_note(body))
    filesystem = _RecordingFileSystem()

    result = _scanner(approved, filesystem=filesystem).scan()

    assert filesystem.opened_files == ["clip.md"]
    assert result.notes[0].data.decode() == _note(body)
    assert "TOP-SECRET" not in repr(result)


def test_cancellation_checkpoint_runs_before_vault_enumeration(tmp_path: Path) -> None:
    approved, inbox = _vault(tmp_path)
    inbox.joinpath("clip.md").write_text(_note())

    class CancelledError(RuntimeError):
        pass

    def checkpoint() -> None:
        raise CancelledError("cancelled")

    with pytest.raises(CancelledError, match="cancelled"):
        _scanner(approved).scan(checkpoint=checkpoint)


def test_cancellation_checkpoint_runs_during_enumeration_and_before_reads(tmp_path: Path) -> None:
    approved, inbox = _vault(tmp_path)
    for name in ("a.md", "b.md"):
        inbox.joinpath(name).write_text(_note(name))
    calls = 0

    class CancelledError(RuntimeError):
        pass

    def checkpoint() -> None:
        nonlocal calls
        calls += 1
        if calls == 4:
            raise CancelledError("cancelled")

    with pytest.raises(CancelledError, match="cancelled"):
        _scanner(approved).scan(checkpoint=checkpoint)
    assert calls == 4
