"""
Check Python 3.8 availability on the remote server.

Usage:
    python tools/fix_and_install.py --host SERVER_IP --password PASSWORD
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

    def run(cmd):
        print(f"\n>>> {cmd}")
        _, stdout, stderr = client.exec_command(cmd, get_pty=False)
        out = stdout.read().decode("utf-8", "replace").strip()
        err = stderr.read().decode("utf-8", "replace").strip()
        if out: print(out)
        if err: print("STDERR:", err[:500])
        return out, err

    run("which python3.8 2>/dev/null || find /usr/local/bin /usr/bin -name 'python3.8' 2>/dev/null | head -3")
    run("python3.8 --version 2>&1 || echo 'no python3.8 binary'")
    run("ls /usr/local/bin/python3*")

    client.close()


if __name__ == "__main__":
    main()
