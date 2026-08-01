"""WebSocket 端到端测试固定直连 localhost。"""

import websockets


_connect = websockets.connect


def connect_without_proxy(*args, **kwargs):
    kwargs.setdefault("proxy", None)
    return _connect(*args, **kwargs)


websockets.connect = connect_without_proxy
