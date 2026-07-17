from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler, FileSystemMovedEvent
from watchdog.observers import Observer

from . import database as db
from .config_store import ConfigStore, SourceSettings
from .extractor import SUPPORTED
from .indexing import index_source_directory, scan_source_directory
from .paths import RuntimePaths, normalize_path


class _SourceEventHandler(FileSystemEventHandler):
    def __init__(
        self,
        source_id: int,
        root: Path,
        recursive: bool,
        callback: Callable[[int, set[str]], None],
    ):
        self.source_id = source_id
        self.root = root
        self.recursive = recursive
        self.callback = callback

    def _relative_supported_path(self, path: str) -> str | None:
        candidate = normalize_path(path)
        try:
            relative = candidate.relative_to(self.root)
        except ValueError:
            return None
        if not self.recursive and len(relative.parts) != 1:
            return None
        if candidate.suffix.lower() not in SUPPORTED:
            return None
        return relative.as_posix()

    def _queue(self, event: FileSystemEvent) -> None:
        paths: set[str] = set()
        if not event.is_directory:
            relative = self._relative_supported_path(event.src_path)
            if relative:
                paths.add(relative)
        self.callback(self.source_id, paths)

    def on_created(self, event: FileSystemEvent) -> None:
        self._queue(event)

    def on_deleted(self, event: FileSystemEvent) -> None:
        self._queue(event)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._queue(event)

    def on_moved(self, event: FileSystemMovedEvent) -> None:
        paths: set[str] = set()
        if not event.is_directory:
            for path in (event.src_path, event.dest_path):
                relative = self._relative_supported_path(path)
                if relative:
                    paths.add(relative)
        self.callback(self.source_id, paths)


def sync_configured_sources(store: ConfigStore) -> list[int]:
    """Apply durable source settings to the disposable SQLite index."""
    source_ids: list[int] = []
    for source in store.sources():
        folder_id = db.upsert_source(
            str(source.path),
            name=source.name,
            enabled=source.enabled,
            recursive=source.recursive,
            source_status="reconnecting" if source.enabled else "disabled",
        )
        db.consolidate_legacy_source(str(source.path))
        source_ids.append(folder_id)
    return source_ids


class SourceMonitor:
    """Coalesce native events and periodically reconcile configured sources."""

    def __init__(
        self,
        paths: RuntimePaths,
        *,
        debounce_seconds: float = 1.0,
        stability_seconds: float = 0.75,
        reconcile_interval: float = 300.0,
        reconnect_interval: float = 15.0,
        observer_factory: Callable[[], Any] = Observer,
    ):
        self.paths = paths
        self.store = ConfigStore(paths.config)
        self.debounce_seconds = max(0.0, debounce_seconds)
        self.stability_seconds = max(0.0, stability_seconds)
        self.reconcile_interval = max(1.0, reconcile_interval)
        self.reconnect_interval = max(1.0, reconnect_interval)
        self._observer = observer_factory()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._lock = threading.RLock()
        self._due: dict[int, float] = {}
        self._forced_paths: dict[int, set[str]] = {}
        self._event_generations: dict[int, int] = {}
        self._watches: dict[int, Any] = {}
        self._watch_settings: dict[int, tuple[str, bool]] = {}
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        source_ids = sync_configured_sources(self.store)
        self._stop_event.clear()
        self._observer.start()
        self._running = True
        self.refresh_watches()
        now = time.monotonic()
        with self._lock:
            for source_id in source_ids:
                self._due[source_id] = now
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="MetaViewerSourceMonitor",
        )
        self._thread.start()
        self._wake_event.set()

    def stop(self, *, timeout: float = 10.0) -> bool:
        if not self._running:
            return True
        self._stop_event.set()
        self._wake_event.set()
        try:
            self._observer.stop()
        except RuntimeError:
            pass
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)
        try:
            self._observer.join(timeout)
        except RuntimeError:
            pass
        stopped = (
            (thread is None or not thread.is_alive())
            and not self._observer.is_alive()
        )
        self._running = not stopped
        return stopped

    def _unschedule(self, source_id: int) -> None:
        watch = self._watches.pop(source_id, None)
        self._watch_settings.pop(source_id, None)
        if watch is None:
            return
        try:
            self._observer.unschedule(watch)
        except (KeyError, RuntimeError):
            pass

    def refresh_watches(self) -> None:
        records = {int(item["id"]): item for item in db.get_source_records()}
        with self._lock:
            for source_id in list(self._watches):
                record = records.get(source_id)
                settings = None if record is None else (
                    str(normalize_path(record["path"])),
                    bool(record["recursive"]),
                )
                if (
                    record is None
                    or not bool(record["enabled"])
                    or not normalize_path(record["path"]).is_dir()
                    or self._watch_settings.get(source_id) != settings
                ):
                    self._unschedule(source_id)

            for source_id, record in records.items():
                if source_id in self._watches or not bool(record["enabled"]):
                    continue
                root = normalize_path(record["path"])
                if not root.is_dir():
                    continue
                recursive = bool(record["recursive"])
                handler = _SourceEventHandler(
                    source_id,
                    root,
                    recursive,
                    self._on_file_event,
                )
                try:
                    watch = self._observer.schedule(
                        handler,
                        str(root),
                        recursive=recursive,
                    )
                except OSError as exc:
                    db.update_source_state(source_id, "error", str(exc))
                    self.request_reconcile(
                        source_id,
                        delay=self.reconnect_interval,
                    )
                    continue
                self._watches[source_id] = watch
                self._watch_settings[source_id] = (str(root), recursive)

    def request_reconcile(
        self,
        source_id: int,
        *,
        delay: float = 0.0,
        force_rel_paths: set[str] | None = None,
        debounce: bool = False,
    ) -> None:
        due = time.monotonic() + max(0.0, delay)
        with self._lock:
            existing = self._due.get(source_id)
            self._due[source_id] = (
                due
                if debounce or existing is None
                else min(existing, due)
            )
            if force_rel_paths:
                self._forced_paths.setdefault(source_id, set()).update(force_rel_paths)
            if debounce:
                self._event_generations[source_id] = (
                    self._event_generations.get(source_id, 0) + 1
                )
        self._wake_event.set()

    def _on_file_event(self, source_id: int, paths: set[str]) -> None:
        self.request_reconcile(
            source_id,
            delay=self.debounce_seconds,
            force_rel_paths=paths,
            debounce=True,
        )

    def update_source(
        self,
        source_id: int,
        *,
        name: str | None = None,
        enabled: bool | None = None,
        recursive: bool | None = None,
    ) -> dict[str, Any] | None:
        record = db.get_folder_record(source_id)
        if record is None or str(record["path"]).startswith("__uploads"):
            return None
        settings = self.store.update_source(
            record["path"],
            name=name,
            enabled=enabled,
            recursive=recursive,
        )
        if settings is None:
            return None
        db.update_source_settings(
            source_id,
            name=settings.name if name is not None else None,
            enabled=settings.enabled if enabled is not None else None,
            recursive=settings.recursive if recursive is not None else None,
        )
        if not settings.enabled:
            with self._lock:
                self._unschedule(source_id)
                self._due.pop(source_id, None)
                self._forced_paths.pop(source_id, None)
                self._event_generations.pop(source_id, None)
            db.update_source_state(source_id, "disabled")
        else:
            self.refresh_watches()
            self.request_reconcile(source_id)
        return db.get_folder_record(source_id)

    def forget_source(self, source_id: int) -> None:
        with self._lock:
            self._unschedule(source_id)
            self._due.pop(source_id, None)
            self._forced_paths.pop(source_id, None)
            self._event_generations.pop(source_id, None)

    def source_added(self, settings: SourceSettings, source_id: int) -> None:
        db.upsert_source(
            str(settings.path),
            name=settings.name,
            enabled=settings.enabled,
            recursive=settings.recursive,
        )
        self.refresh_watches()
        self.request_reconcile(source_id, delay=self.reconcile_interval)

    def _next_due_source(self) -> tuple[int | None, float]:
        with self._lock:
            if not self._due:
                return None, 0.5
            source_id, due = min(self._due.items(), key=lambda item: item[1])
            remaining = due - time.monotonic()
            if remaining > 0:
                return None, min(0.5, remaining)
            self._due.pop(source_id, None)
            return source_id, 0.0

    def _run(self) -> None:
        while not self._stop_event.is_set():
            source_id, wait_time = self._next_due_source()
            if source_id is None:
                self._wake_event.wait(wait_time)
                self._wake_event.clear()
                continue
            self._reconcile(source_id)

    def _reschedule_retry(self, source_id: int) -> None:
        self.request_reconcile(source_id, delay=self.reconnect_interval)

    def _reconcile(self, source_id: int) -> None:
        record = db.get_folder_record(source_id)
        if record is None:
            self.forget_source(source_id)
            return
        if not bool(record["enabled"]):
            db.update_source_state(source_id, "disabled")
            self.forget_source(source_id)
            return

        root = normalize_path(record["path"])
        recursive = bool(record["recursive"])
        if not root.is_dir():
            with self._lock:
                self._unschedule(source_id)
            db.update_source_state(
                source_id,
                "unavailable",
                f"Source directory is unavailable: {root}",
            )
            self._reschedule_retry(source_id)
            return

        if record["source_status"] in ("unavailable", "error", "disabled"):
            db.update_source_state(source_id, "reconnecting")
        self.refresh_watches()

        try:
            first = scan_source_directory(root, recursive=recursive)
            if self._stop_event.wait(self.stability_seconds):
                return
            second = scan_source_directory(root, recursive=recursive)
            if first.signature != second.signature:
                self.request_reconcile(
                    source_id,
                    delay=self.debounce_seconds,
                    debounce=True,
                )
                return

            with self._lock:
                forced = set(self._forced_paths.get(source_id, set()))
                event_generation = self._event_generations.get(source_id, 0)
            result = index_source_directory(
                root,
                thumbnail_dir=self.paths.thumbnails,
                cutout_dir=self.paths.cutouts,
                preview_dir=self.paths.previews,
                name=record["name"],
                recursive=recursive,
                snapshot=second,
                force_rel_paths=forced,
            )
            with self._lock:
                pending = self._forced_paths.get(source_id)
                events_arrived_during_reconcile = (
                    self._event_generations.get(source_id, 0) != event_generation
                )
                if pending is not None and not events_arrived_during_reconcile:
                    pending.difference_update(forced)
                    if not pending:
                        self._forced_paths.pop(source_id, None)
            if result.processed:
                from .worker import start_worker

                start_worker(self.paths.thumbnails)
            self.request_reconcile(source_id, delay=self.reconcile_interval)
        except FileNotFoundError as exc:
            with self._lock:
                self._unschedule(source_id)
            db.update_source_state(source_id, "unavailable", str(exc))
            self._reschedule_retry(source_id)
        except db.DatabaseMaintenanceError:
            self._reschedule_retry(source_id)
        except Exception as exc:
            db.update_source_state(source_id, "error", str(exc))
            self._reschedule_retry(source_id)


_runtime_lock = threading.Lock()
_runtime_monitor: SourceMonitor | None = None


def start_source_monitor(paths: RuntimePaths) -> SourceMonitor:
    global _runtime_monitor
    with _runtime_lock:
        if _runtime_monitor is not None and _runtime_monitor.running:
            return _runtime_monitor
        _runtime_monitor = SourceMonitor(paths)
        _runtime_monitor.start()
        return _runtime_monitor


def get_source_monitor() -> SourceMonitor | None:
    return _runtime_monitor


def source_monitor_is_running() -> bool:
    return _runtime_monitor is not None and _runtime_monitor.running


def stop_source_monitor(*, timeout: float = 10.0) -> bool:
    global _runtime_monitor
    with _runtime_lock:
        monitor = _runtime_monitor
        if monitor is None:
            return True
        stopped = monitor.stop(timeout=timeout)
        if stopped:
            _runtime_monitor = None
        return stopped
