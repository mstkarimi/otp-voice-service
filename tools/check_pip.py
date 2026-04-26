"""
Debug pip install issues on the remote server.

Usage:
    python tools/check_pip.py --host SERVER_IP --password PASSWORD
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

    def run(cmd, timeout=120):
        _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        rc  = stdout.channel.recv_exit_status()
        return out, err, rc

    out, _, _ = run("ls /root/otp-voice-service/vendor/")
    print("VENDOR FILES:\n", out)

    out, err, rc = run(
        "/opt/otp-service/venv/bin/pip install "
        "--no-index --find-links=/root/otp-voice-service/vendor "
        "-r /root/otp-voice-service/requirements.txt 2>&1",
    )
    print(f"\nPIP RC: {rc}")
    print("OUTPUT:\n", (out + err)[:3000])

    client.close()


if __name__ == "__main__":
    main()
