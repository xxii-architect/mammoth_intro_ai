"""OS-released cross-process leases for private run state."""

import os


class RunBusyError(ValueError):
    pass


class RunLease:
    def __init__(self, path, *, blocking=False):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.file = path.open("a+b", buffering=0)
        try:
            if os.name == "nt":
                import msvcrt
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except OSError:
            self.file.close()
            raise RunBusyError("This run is already active or its state is being updated") from None

    def close(self):
        self.file.close()
