"""Downloads remote images on the thread pool; results are delivered on the main thread."""

import itertools
import urllib.request
from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

MAX_BYTES = 50 * 1024 * 1024
TIMEOUT_SECONDS = 15
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

Callback = Callable[[bytes | None, str | None], None]  # (data, error)


def download(url: str) -> bytes:
    """Blocking download with a size cap. Only http(s) is allowed."""
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("Only http(s) URLs can be downloaded")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/*"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("File is too large")
    return data


class _Task(QRunnable):
    def __init__(self, fetcher: "RemoteImageFetcher", token: int, url: str):
        super().__init__()
        self._fetcher = fetcher
        self._token = token
        self._url = url

    def run(self) -> None:
        try:
            self._fetcher.done.emit(self._token, download(self._url), None)
        except Exception as exc:  # any failure is reported to the node, never raised
            self._fetcher.done.emit(self._token, None, str(exc) or type(exc).__name__)


class RemoteImageFetcher(QObject):
    # Emitted from a worker thread. The slot below lives on the main thread, so Qt queues it.
    done = Signal(int, object, object)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._tokens = itertools.count(1)
        self._callbacks: dict[int, Callback] = {}
        self.done.connect(self._on_done)

    def fetch(self, url: str, callback: Callback) -> None:
        token = next(self._tokens)
        self._callbacks[token] = callback
        QThreadPool.globalInstance().start(_Task(self, token, url))

    @Slot(int, object, object)
    def _on_done(self, token: int, data: bytes | None, error: str | None) -> None:
        callback = self._callbacks.pop(token, None)
        if callback:
            callback(data, error)
