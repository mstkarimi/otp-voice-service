"""
Sync vendor/ to server and install Python packages into the venv.

Usage:
    python tools/install_packages.py --host SERVER_IP --password PASSWORD

Or set env vars: SERVER_HOST, SERVER_USER, SERVER_PASS
"""
import argparse
import os
import sys

import paramiko
from scp import SCPClient

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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

    def run(cmd, timeout=180):
        print(f"  $ {cmd[:80]}")
        _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        rc  = stdout.channel.recv_exit_status()
        combined = (out + err).strip()
        if combined:
            print(combined[:1000])
        return rc

    print("Syncing vendor/ to server...")
    with SCPClient(client.get_transport()) as scp:
        scp.put(os.path.join(PROJECT_DIR, "vendor"),
                remote_path="/root/otp-voice-service", recursive=True)
        scp.put(os.path.join(PROJECT_DIR, "requirements.txt"),
                remote_path="/root/otp-voice-service/requirements.txt")
    print("Sync done")

    print("\nInstalling packages into venv...")
    rc = run(
        "/opt/otp-service/venv/bin/pip install "
        "--no-index --find-links=/root/otp-voice-service/vendor "
        "-r /root/otp-voice-service/requirements.txt",
    )
    if rc != 0:
        print(f"\nFailed (rc={rc})")
    else:
        print("\n[OK] All packages installed!")
        run("/opt/otp-service/venv/bin/pip list")

    client.close()


if __name__ == "__main__":
    main()
