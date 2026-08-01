import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.request

import websockets


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(os.environ.get("CONDA_PREFIX", "")) / "python.exe"
if not PYTHON.exists():
    PYTHON = Path(os.sys.executable)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class RunningServer:
    def __init__(self, target: str) -> None:
        self.target = target
        self.port = free_port()
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        (root / "static").mkdir()
        (root / "static" / "index.html").write_text("ok", encoding="utf-8")
        (root / "data").mkdir()
        (root / "kb" / "raw").mkdir(parents=True)
        (root / "objects").mkdir()
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        self.process = subprocess.Popen(
            [str(PYTHON), "-m", "uvicorn", target, "--host", "127.0.0.1", "--port", str(self.port)],
            cwd=root, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self._wait_until_ready()

    def _wait_until_ready(self) -> None:
        deadline = time.monotonic() + 12
        url = f"http://127.0.0.1:{self.port}/health"
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"{self.target} 启动失败，退出码 {self.process.returncode}")
            try:
                with urllib.request.urlopen(url, timeout=0.5) as response:
                    if response.status == 200:
                        return
            except Exception:
                time.sleep(0.1)
        raise TimeoutError(f"{self.target} 健康检查超时")

    def close(self) -> None:
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        self.temp.cleanup()


class LiveEntrypointTests(unittest.TestCase):
    def test_stage1_http_ingest_and_websocket_envelope(self) -> None:
        server = RunningServer("stage1_app:app")
        try:
            event = asyncio.run(self._ingest_while_watching(server.port))
            self.assertEqual(event["type"], "entity.upserted")
            self.assertEqual(event["schemaVersion"], "1.0")
            self.assertEqual(event["subject"]["entityId"], "TEST_UAV_1")
            self.assertEqual(event["entityId"], "TEST_UAV_1")
        finally:
            server.close()

    def test_legacy_entrypoint_remains_healthy(self) -> None:
        server = RunningServer("mock_server:app")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{server.port}/health", timeout=2) as response:
                self.assertEqual(response.status, 200)
        finally:
            server.close()

    async def _ingest_while_watching(self, port: int) -> dict:
        uri = f"ws://127.0.0.1:{port}/api/v1/entities/stream"
        async with websockets.connect(uri) as websocket:
            connected = json.loads(await websocket.recv())
            self.assertEqual(connected["type"], "stream.connected")
            payload = {
                "sourceType": "test", "sourceId": "TEST_SENSOR", "eventType": "track.update",
                "track": {"trackId": "TEST_UAV_1", "name": "Test UAV", "platformType": "UAV",
                          "location": {"latitudeDegrees": 30.0, "longitudeDegrees": 120.0}},
            }
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/v1/ingest/events",
                data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST",
            )
            response_body = await asyncio.to_thread(lambda: urllib.request.urlopen(request, timeout=3).read())
            self.assertTrue(json.loads(response_body)["ok"])
            return json.loads(await asyncio.wait_for(websocket.recv(), timeout=3))


if __name__ == "__main__":
    unittest.main()
