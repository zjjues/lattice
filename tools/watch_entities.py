#!/usr/bin/env python3
"""本地 entity stream WebSocket 客户端。"""

import argparse
import asyncio

import websockets


DEFAULT_STREAM_URL = "ws://127.0.0.1:8000/api/v1/entities/stream"


def parse_args():
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="监听本地 entity stream。")
    parser.add_argument(
        "--url",
        default=DEFAULT_STREAM_URL,
        help="本地 entity stream WebSocket URL",
    )
    return parser.parse_args()


async def watch_entities(url):
    """连接 WebSocket 并持续打印收到的消息。"""
    async with websockets.connect(url) as websocket:
        print(f"已连接: {url}")
        async for message in websocket:
            print(message)


def main():
    """程序入口。"""
    args = parse_args()
    try:
        asyncio.run(watch_entities(args.url))
    except KeyboardInterrupt:
        print("\n已退出本地 entity stream 监听。")


if __name__ == "__main__":
    main()
