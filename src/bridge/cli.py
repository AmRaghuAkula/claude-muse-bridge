#!/usr/bin/env python3
"""Operator CLI for brief producers (Muse side).

    python -m bridge.cli seal                      # hash-seal all briefs
    python -m bridge.cli upload                    # upload sealed briefs (azure)
    python -m bridge.cli channels                  # list message channels
    python -m bridge.cli send -c CH -a AUTHOR TEXT  # post a channel message
    python -m bridge.cli read -c CH [--after ID] [--limit N]

Channel commands talk to whichever backend is configured (local dir or azure).
"""

from __future__ import annotations

import argparse
import json
import sys

from bridge.channels import get_channel_store
from bridge.config import load_settings
from bridge.integrity import seal_brief


def cmd_seal(settings) -> int:
    d = settings.briefs_dir
    files = (
        sorted(d.glob("*.md"), key=lambda p: p.stat().st_mtime)
        if d.is_dir()
        else []
    )
    if not files:
        print("no briefs to seal", file=sys.stderr)
        return 1
    for path in files:
        sidecar = seal_brief(path)
        print(f"sealed {path.name} -> {sidecar.name}")
    return 0


def cmd_upload(settings) -> int:
    if settings.backend != "azure":
        print("upload needs BRIDGE_BACKEND=azure", file=sys.stderr)
        return 1
    try:
        from azure.storage.blob import ContainerClient
    except ImportError:
        print("azure-storage-blob not installed", file=sys.stderr)
        return 1
    sas = settings.sas_token
    sas = sas[1:] if sas.startswith("?") else sas
    client = ContainerClient.from_container_url(
        f"https://{settings.storage_account}.blob.core.windows.net/"
        f"{settings.container}?{sas}"
    )
    d = settings.briefs_dir
    files = sorted(d.glob("*.md")) if d.is_dir() else []
    if not files:
        print("no briefs to upload", file=sys.stderr)
        return 1
    for path in files:
        for blob_name in (path.name, path.name + ".sha256"):
            blob_path = path.parent / blob_name
            if not blob_path.is_file():
                continue
            with blob_path.open("rb") as f:
                client.upload_blob(blob_name, f, overwrite=True)
            print(f"uploaded {blob_name}")
    return 0


def cmd_channels(settings) -> int:
    store = get_channel_store(settings)
    for name in store.list_channels():
        print(name)
    return 0


def cmd_send(args, settings) -> int:
    store = get_channel_store(settings)
    try:
        msg = store.send_message(args.channel, args.author, args.text)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(msg, ensure_ascii=False))
    return 0


def cmd_read(args, settings) -> int:
    store = get_channel_store(settings)
    try:
        msgs = store.read_messages(args.channel, after_id=args.after, limit=args.limit)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for m in msgs:
        print(f"[{m['ts']}] {m['author']}: {m['text']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="claude-muse-bridge operator CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("seal", help="write .sha256 sidecars for all briefs")
    sub.add_parser("upload", help="upload briefs + sidecars (azure backend)")

    sub.add_parser("channels", help="list message channels")

    p_send = sub.add_parser("send", help="post a message to a channel")
    p_send.add_argument("-c", "--channel", required=True)
    p_send.add_argument("-a", "--author", required=True)
    p_send.add_argument("text", nargs="?")

    p_read = sub.add_parser("read", help="read messages from a channel")
    p_read.add_argument("-c", "--channel", required=True)
    p_read.add_argument("--after", default="")
    p_read.add_argument("--limit", type=int, default=50)

    args = parser.parse_args(argv)
    settings = load_settings()

    if args.cmd == "seal":
        return cmd_seal(settings)
    if args.cmd == "upload":
        return cmd_upload(settings)
    if args.cmd == "channels":
        return cmd_channels(settings)
    if args.cmd == "send":
        text = args.text
        if text is None:
            text = sys.stdin.read()
        args.text = text
        return cmd_send(args, settings)
    if args.cmd == "read":
        return cmd_read(args, settings)
    return 1


if __name__ == "__main__":
    sys.exit(main())
