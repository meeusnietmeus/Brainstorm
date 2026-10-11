import http.server
import threading

import pytest
from PySide6.QtTest import QTest

from brainstorm.services import RemoteImageFetcher
from brainstorm.services.remote_fetcher import download


@pytest.fixture
def server(png):
    image = png(10, 10)

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/ok.png":
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.end_headers()
                self.wfile.write(image)
            else:
                self.send_error(404)

        def log_message(self, *args):
            pass

    httpd = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}", image
    httpd.shutdown()


def wait_for(results, timeout_ms=5000):
    waited = 0
    while not results and waited < timeout_ms:
        QTest.qWait(20)
        waited += 20


def test_download_returns_bytes(server):
    base, image = server
    assert download(base + "/ok.png") == image


def test_download_rejects_non_http_schemes():
    with pytest.raises(ValueError):
        download("file:///C:/Windows/win.ini")


def test_fetcher_delivers_result_on_the_main_thread(server):
    base, image = server
    fetcher = RemoteImageFetcher()
    results = []
    main_thread = threading.get_ident()
    fetcher.fetch(
        base + "/ok.png", lambda data, error: results.append((data, error, threading.get_ident()))
    )
    wait_for(results)
    assert results == [(image, None, main_thread)]


def test_fetcher_reports_http_errors(server):
    base, _ = server
    fetcher = RemoteImageFetcher()
    results = []
    fetcher.fetch(base + "/missing.png", lambda data, error: results.append((data, error)))
    wait_for(results)
    [(data, error)] = results
    assert data is None and "404" in error
