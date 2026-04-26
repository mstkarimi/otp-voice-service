"""
Check Python environment on the remote server.

Usage:
    python tools/check_server.py --host SERVER_IP --password PASSWORD
"""
import argparse
import os
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--host",     default=os.environ.get("SERVER_HOST"))
    p.add_argument("--user",     default=os.environ.get("SERVER_USER", "root"))
    p.add_argument("--password", default=os.environ.get("SERVER_PASS"))
    args = p.parse_args()
    if not args.host or not args.password:
        p.error("--host and --password are required")
    return args


def main():
    args = parse_args()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(args.host, username=args.user, password=args.password,
                   timeout=30, allow_agent=False, look_for_keys=False)

    cmds = [
        "pip3 --version 2>/dev/null || echo no_pip3",
        "python3 -m pip --version 2>/dev/null || echo no_pip_module",
        "yum list installed 2>/dev/null | grep python3 | head -8",
        "which virtualenv 2>/dev/null || echo no_virtualenv",
        "python3 -c 'import ensurepip; print(\"ensurepip ok\")' 2>&1",
        "which python3.8 2>/dev/null || echo no_python38",
        "python3.8 --version 2>&1",
    ]
    for cmd in cmds:
        _, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode("utf-8", "replace").strip()
        err = stderr.read().decode("utf-8", "replace").strip()
        print(f">>> {cmd[:60]}")
        if out: print(out[:300])
        if err: print("E:", err[:200])
        print()

    client.close()


if __name__ == "__main__":
    main()
