"""测试进程只访问 localhost，不应经过机器的全局 HTTP 代理。"""

import urllib.request


urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))
