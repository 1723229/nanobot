#!/usr/bin/env python3
"""OpenViking Embedded Mode CLI

Wraps the OpenViking Python SDK for agent use. All commands share a
--data-dir option that sets the local workspace directory (default: ./data).

Usage:
    python openviking_client.py [--data-dir DIR] <command> [args...]

Commands:
    add-resource <path> [--wait]        Ingest file, directory, or URL
    wait-processed                      Wait for indexing to complete
    ls <uri>                            List directory contents
    tree <uri>                          Recursive directory tree (JSON)
    stat <uri>                          File/directory metadata
    glob <pattern> <uri>                Pattern-match URIs
    abstract <uri>                      L0 summary (~100 tokens)
    overview <uri>                      L1 overview (~2000 tokens) — directories only
    read <uri>                          Full content (L2)
    find <query> <target_uri>           Semantic search
    mkdir <uri>                         Create directory
    mv <src> <dst>                      Move or rename
    rm <uri>                            Delete file or directory
    add-skill <path>                    Register agent skill from local path
    session <spec_file>                 Commit a session from a JSON spec file
"""

import asyncio
import argparse
import json
import sys

from openviking import AsyncOpenViking


def make_parser():
    parser = argparse.ArgumentParser(
        description="OpenViking Embedded Mode CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--data-dir", default="./data",
        help="Workspace directory (default: ./data)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("add-resource", help="Ingest file, directory, or URL")
    p.add_argument("path", help="Local path or URL")
    p.add_argument("--wait", action="store_true", help="Block until indexing completes")

    sub.add_parser("wait-processed", help="Wait for all pending indexing")

    p = sub.add_parser("ls", help="List directory contents")
    p.add_argument("uri", help="viking:// URI")

    p = sub.add_parser("tree", help="Recursive directory tree (JSON)")
    p.add_argument("uri", help="viking:// URI")

    p = sub.add_parser("stat", help="File/directory metadata")
    p.add_argument("uri", help="viking:// URI")

    p = sub.add_parser("glob", help="Pattern-match URIs")
    p.add_argument("pattern", help="Glob pattern, e.g. **/*.md")
    p.add_argument("uri", help="Base viking:// URI")

    p = sub.add_parser("abstract", help="L0 summary (~100 tokens)")
    p.add_argument("uri", help="viking:// URI")

    p = sub.add_parser("overview", help="L1 overview (~2000 tokens) — directories only")
    p.add_argument("uri", help="viking:// directory URI")

    p = sub.add_parser("read", help="Full content (L2)")
    p.add_argument("uri", help="viking:// URI")

    p = sub.add_parser("find", help="Semantic search")
    p.add_argument("query", help="Natural language query")
    p.add_argument("target_uri", help="viking:// URI to search within")

    p = sub.add_parser("mkdir", help="Create directory")
    p.add_argument("uri", help="viking:// URI")

    p = sub.add_parser("mv", help="Move or rename")
    p.add_argument("src", help="Source viking:// URI")
    p.add_argument("dst", help="Destination viking:// URI")

    p = sub.add_parser("rm", help="Delete file or directory")
    p.add_argument("uri", help="viking:// URI")

    p = sub.add_parser("add-skill", help="Register agent skill from local path")
    p.add_argument("path", help="Local path to skill directory or SKILL.md file")
    p.add_argument("--wait", action="store_true", help="Block until indexing completes")

    p = sub.add_parser(
        "session",
        help="Commit a session from a JSON spec file",
        description=(
            "Spec file format:\n"
            "{\n"
            '  "messages": [\n'
            '    {"role": "user", "parts": ["..."]},\n'
            '    {"role": "assistant", "parts": ["..."]}\n'
            "  ],\n"
            '  "used": ["viking://resources/file.md"]\n'
            "}"
        ),
    )
    p.add_argument("spec_file", help="Path to session JSON spec file")

    return parser


def _serialize(obj):
    """Best-effort serialization for OpenViking return objects."""
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if isinstance(obj, list):
        return [_serialize(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    # Try known attribute names, fall back to vars()
    try:
        return {k: _serialize(v) for k, v in vars(obj).items()
                if not k.startswith("_")}
    except TypeError:
        return str(obj)


async def run(args):
    client = AsyncOpenViking(path=args.data_dir)
    await client.initialize()

    try:
        cmd = args.command

        if cmd == "add-resource":
            result = await client.add_resource(args.path)
            if args.wait:
                await client.wait_processed()
            print(json.dumps({"root_uri": result["root_uri"]}))

        elif cmd == "wait-processed":
            await client.wait_processed()
            print(json.dumps({"status": "done"}))

        elif cmd == "ls":
            items = await client.ls(args.uri)
            print(json.dumps([_serialize(i) for i in items]))

        elif cmd == "tree":
            result = await client.tree(args.uri)
            print(json.dumps([_serialize(i) for i in result]))

        elif cmd == "stat":
            meta = await client.stat(args.uri)
            print(json.dumps(_serialize(meta)))

        elif cmd == "glob":
            result = await client.glob(args.pattern, args.uri)
            matches = result["matches"] if isinstance(result, dict) else result
            print(json.dumps(matches))

        elif cmd == "abstract":
            result = await client.abstract(args.uri)
            print(result)

        elif cmd == "overview":
            result = await client.overview(args.uri)
            print(result)

        elif cmd == "read":
            result = await client.read(args.uri)
            print(result)

        elif cmd == "find":
            results = await client.find(args.query, args.target_uri)
            print(json.dumps([_serialize(m) for m in results.resources]))

        elif cmd == "mkdir":
            await client.mkdir(args.uri)
            print(json.dumps({"status": "ok"}))

        elif cmd == "mv":
            await client.mv(args.src, args.dst)
            print(json.dumps({"status": "ok"}))

        elif cmd == "rm":
            await client.rm(args.uri)
            print(json.dumps({"status": "ok"}))

        elif cmd == "add-skill":
            result = await client.add_skill(args.path, wait=args.wait)
            print(json.dumps(_serialize(result)))

        elif cmd == "session":
            with open(args.spec_file) as f:
                spec = json.load(f)

            session = client.session()
            for msg in spec.get("messages", []):
                session.add_message(role=msg["role"], parts=msg["parts"])
            if spec.get("used"):
                session.used(contexts=spec["used"])
            result = session.commit()
            print(json.dumps({"status": "committed", "session_id": result.get("session_id")}))

    finally:
        await client.close()


def main():
    parser = make_parser()
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
