from __future__ import annotations

import os
import sys
from pathlib import Path


class SingleInstance:
    """Cross-platform single-instance guard for long-running bot processes.

    Windows: real file lock via msvcrt.locking, handle kept open for process lifetime.
    Linux/Termux: fcntl file lock, handle kept open for process lifetime.

    Important: stale .lock files are harmless. The active lock is the OS-level lock,
    not the mere existence of the file.
    """

    def __init__(self, name: str, lock_path: str | Path):
        self.name = name
        self.lock_path = Path(lock_path)
        self._fh = None
        self._locked = False

    def __enter__(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            self._acquire_windows_file_lock()
        else:
            self._acquire_posix_file_lock()
        self._write_pid_keep_handle()
        return self

    def _acquire_windows_file_lock(self) -> None:
        import msvcrt

        # Binary read/write. Keep this handle open while the bot runs.
        self._fh = self.lock_path.open("a+b")

        # msvcrt.locking locks bytes from the current file pointer. Ensure the
        # file has at least one byte and lock byte 0.
        self._fh.seek(0, os.SEEK_END)
        if self._fh.tell() == 0:
            self._fh.write(b"0")
            self._fh.flush()
            os.fsync(self._fh.fileno())

        self._fh.seek(0)
        try:
            msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
            self._locked = True
        except OSError:
            print(
                f"{self.name} zaten calisiyor. Yeni kopya baslatilmadi. Lock: {self.lock_path}",
                flush=True,
            )
            try:
                self._fh.close()
            finally:
                self._fh = None
            sys.exit(0)

    def _acquire_posix_file_lock(self) -> None:
        import fcntl

        self._fh = self.lock_path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._locked = True
        except OSError:
            print(
                f"{self.name} zaten calisiyor. Yeni kopya baslatilmadi. Lock: {self.lock_path}",
                flush=True,
            )
            try:
                self._fh.close()
            finally:
                self._fh = None
            sys.exit(0)

    def _write_pid_keep_handle(self) -> None:
        if not self._fh:
            return

        pid_text = f"pid={os.getpid()}\n"
        self._fh.seek(0)
        self._fh.truncate()

        if "b" in getattr(self._fh, "mode", ""):
            self._fh.write(pid_text.encode("utf-8"))
        else:
            self._fh.write(pid_text)

        self._fh.flush()
        try:
            os.fsync(self._fh.fileno())
        except OSError:
            pass

    def __exit__(self, exc_type, exc, tb):
        if self._fh:
            try:
                if self._locked:
                    if os.name == "nt":
                        import msvcrt

                        self._fh.seek(0)
                        try:
                            msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
                        except OSError:
                            pass
                    else:
                        import fcntl

                        try:
                            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
                        except OSError:
                            pass
            finally:
                self._fh.close()
                self._fh = None
                self._locked = False
        return False


def single_instance(name: str, lock_path: str | Path) -> SingleInstance:
    return SingleInstance(name, lock_path)
