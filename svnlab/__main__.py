from __future__ import annotations

import argparse
import shutil

import uvicorn

from svnlab.app import app


def port_number(value: str) -> int:
    port = int(value)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="SVNLab",
        description="Run the local SVNLab repository browser.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="address to listen on (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=port_number,
        default=8000,
        help="TCP port to listen on (default: 8000)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    display_host = "127.0.0.1" if args.host in {"0.0.0.0", "::"} else args.host
    print(f"SVNLab: http://{display_host}:{args.port}")
    svn_path = shutil.which("svn")
    if svn_path:
        print(f"SVN CLI: {svn_path}")
    else:
        print("WARNING: SVN CLI was not found in PATH; repository requests will fail.")
    uvicorn.run(app, host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()

