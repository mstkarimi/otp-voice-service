"""
SSH deployment script — uploads project and runs installation on a remote server.

Usage:
    pip install paramiko scp
    python tools/deploy.py --host YOUR_SERVER_IP --user root --password YOUR_PASSWORD

Or set environment variables:
    SERVER_HOST, SERVER_USER, SERVER_PASS
"""
import argparse
import base64
import os
import sys
import time

import paramiko
from scp import SCPClient

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---- config ----
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROJ    = "/root/otp-voice-service"
INSTALL = "/opt/otp-service"
CONFIG  = "/etc/otp-service"
LOG_DIR = "/var/log/otp-service"
DATA_DIR= "/var/lib/otp-service"
SOUNDS  = "/var/lib/asterisk/sounds/otp"
PYTHON  = "/usr/local/bin/python3.8"


def parse_args():
    p = argparse.ArgumentParser(description="Deploy OTP voice service to remote server")
    p.add_argument("--host",     default=os.environ.get("SERVER_HOST"), help="Server IP/hostname")
    p.add_argument("--user",     default=os.environ.get("SERVER_USER", "root"))
    p.add_argument("--password", default=os.environ.get("SERVER_PASS"))
    p.add_argument("--port",     type=int, default=22)
    args = p.parse_args()
    if not args.host or not args.password:
        p.error("--host and --password are required (or set SERVER_HOST / SERVER_PASS env vars)")
    return args


def connect(args):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        args.host, port=args.port, username=args.user, password=args.password,
        timeout=30, allow_agent=False, look_for_keys=False,
    )
    return client


def run(client, cmd, timeout=120, check=True):
    print(f"\n  $ {cmd[:100]}")
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace").strip()
    err = stderr.read().decode("utf-8", "replace").strip()
    rc  = stdout.channel.recv_exit_status()
    if out: print(f"    {out[:500]}")
    if err and rc != 0: print(f"    ERR: {err[:300]}")
    if check and rc != 0:
        raise RuntimeError(f"Command failed (rc={rc}): {cmd}")
    return out, err, rc


def step(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")


def main():
    args = parse_args()
    client = connect(args)

    step("STEP 1: Backup Asterisk configs")
    run(client, "BACKUP=/root/otp-backup-$(date +%Y%m%d_%H%M%S); mkdir -p $BACKUP; "
                "cp /etc/asterisk/extensions_custom.conf $BACKUP/ 2>/dev/null || true; "
                "cp /etc/asterisk/manager_custom.conf $BACKUP/ 2>/dev/null || true; "
                "echo Backup done: $BACKUP")

    step("STEP 2: Create service user")
    run(client, "id otp-service 2>/dev/null || useradd --system --no-create-home --shell /sbin/nologin otp-service; echo OK")

    step("STEP 3: Create directories")
    run(client, f"mkdir -p {INSTALL} {CONFIG} {LOG_DIR} {DATA_DIR} {SOUNDS}/digits; "
                f"chown otp-service:otp-service {LOG_DIR} {DATA_DIR}; "
                f"chmod 755 {LOG_DIR} {DATA_DIR}; chmod 750 {CONFIG}; echo OK")

    step("STEP 4: Upload project files")
    with SCPClient(client.get_transport()) as scp:
        scp.put(os.path.join(PROJECT_DIR, "src"),       remote_path=PROJ, recursive=True)
        scp.put(os.path.join(PROJECT_DIR, "vendor"),    remote_path=PROJ, recursive=True)
        scp.put(os.path.join(PROJECT_DIR, "sounds"),    remote_path=PROJ, recursive=True)
        scp.put(os.path.join(PROJECT_DIR, "asterisk"),  remote_path=PROJ, recursive=True)
        scp.put(os.path.join(PROJECT_DIR, "systemd"),   remote_path=PROJ, recursive=True)
        scp.put(os.path.join(PROJECT_DIR, "requirements.txt"), remote_path=f"{PROJ}/requirements.txt")
    run(client, f"cp -r {PROJ}/src {INSTALL}/; chown -R otp-service:otp-service {INSTALL}/src; echo OK")

    step("STEP 5: Create virtualenv + install packages")
    run(client, f"rm -rf {INSTALL}/venv", check=False)
    run(client, f"{PYTHON} -m venv {INSTALL}/venv")
    run(client,
        f"{INSTALL}/venv/bin/pip install "
        f"--no-index --find-links={PROJ}/vendor "
        f"-r {PROJ}/requirements.txt 2>&1",
        timeout=180)

    step("STEP 6: Install sound files")
    run(client, f"cp {PROJ}/sounds/*.wav {SOUNDS}/ 2>/dev/null || true", check=False)
    run(client, f"cp {PROJ}/sounds/digits/*.wav {SOUNDS}/digits/ 2>/dev/null || true", check=False)
    run(client, f"chown -R asterisk:asterisk {SOUNDS}; chmod -R 755 {SOUNDS}; echo OK")

    step("STEP 7: AMI user")
    out, _, _ = run(client, f"{PYTHON} -c \"import secrets; print(secrets.token_hex(16))\"")
    ami_secret = out.strip()
    existing, _, _ = run(client, "grep -c otp_service /etc/asterisk/manager_custom.conf 2>/dev/null; echo done", check=False)
    if existing.split("\n")[0].strip() == "0":
        ami_block = (
            f"\n; --- OTP Voice Call Service ---\n"
            f"[otp_service]\nsecret = {ami_secret}\n"
            f"deny = 0.0.0.0/0.0.0.0\npermit = 127.0.0.1/255.255.255.255\n"
            f"read = call\nwrite = originate,call\nwritetimeout = 5000\n"
        )
        encoded = base64.b64encode(ami_block.encode()).decode()
        run(client, f"echo {encoded} | base64 -d >> /etc/asterisk/manager_custom.conf && echo added")
    else:
        out2, _, _ = run(client, "awk \"/otp_service/{f=1} f && /^secret/{print; exit}\" /etc/asterisk/manager_custom.conf", check=False)
        ami_secret = out2.split("=")[1].strip() if "=" in out2 else ami_secret

    step("STEP 8: Dialplan")
    existing2, _, _ = run(client, "grep -c otp-playback /etc/asterisk/extensions_custom.conf 2>/dev/null; echo done", check=False)
    if existing2.split("\n")[0].strip() == "0":
        run(client, f"cat {PROJ}/asterisk/extensions_custom.conf >> /etc/asterisk/extensions_custom.conf && echo added")
    run(client, "asterisk -rx 'dialplan reload'", timeout=30, check=False)
    run(client, "asterisk -rx 'manager reload'",  timeout=30, check=False)

    step("STEP 9: Generate API key & config.yaml")
    out3, _, _ = run(client, f"{PYTHON} -c \"import secrets; print(secrets.token_urlsafe(32))\"")
    api_key = out3.strip()
    hash_py = (
        f"from passlib.context import CryptContext\n"
        f"ctx = CryptContext(schemes=['bcrypt'], deprecated='auto')\n"
        f"print(ctx.hash('{api_key}'))\n"
    )
    encoded_hash = base64.b64encode(hash_py.encode()).decode()
    run(client, f"echo {encoded_hash} | base64 -d > /tmp/hash_api.py")
    out4, _, _ = run(client, f"{INSTALL}/venv/bin/python /tmp/hash_api.py", timeout=30)
    api_key_hash = out4.strip()

    trunk   = input("\nSIP Trunk number [90004455]: ").strip() or "90004455"
    caller  = input("CallerID number  [90004455]: ").strip() or "90004455"

    config_content = f"""api:
  host: "0.0.0.0"
  port: 8080
  api_key_hash: "{api_key_hash}"
  ip_whitelist: []

asterisk:
  host: "127.0.0.1"
  port: 5038
  username: "otp_service"
  secret: "{ami_secret}"
  trunk: "{trunk}"
  caller_id: "{caller}"
  call_timeout: 30
  reconnect_delay: 5

rate_limit:
  per_number_calls: 3
  per_number_window_minutes: 10
  max_concurrent_calls: 20
  hourly_limit: 500

sounds:
  base_path: "{SOUNDS}"
  use_system_digits: false

logging:
  level: "INFO"
  dir: "{LOG_DIR}"
  max_bytes: 10485760
  backup_count: 5

database:
  path: "{DATA_DIR}/otp.db"
"""
    encoded_cfg = base64.b64encode(config_content.encode()).decode()
    run(client, f"mkdir -p {CONFIG}")
    run(client, f"echo {encoded_cfg} | base64 -d > {CONFIG}/config.yaml")
    run(client, f"chmod 640 {CONFIG}/config.yaml; chown root:otp-service {CONFIG}/config.yaml 2>/dev/null || true")
    run(client, f"chown root:otp-service {CONFIG}")

    step("STEP 10: Systemd service")
    with SCPClient(client.get_transport()) as scp:
        scp.put(
            os.path.join(PROJECT_DIR, "systemd", "otp-service.service"),
            remote_path="/etc/systemd/system/otp-service.service",
        )
    run(client, "systemctl daemon-reload")
    run(client, "systemctl enable otp-service")
    run(client, "systemctl restart otp-service; sleep 5; systemctl status otp-service --no-pager | head -10")

    step("STEP 11: Health check")
    time.sleep(5)
    out5, _, rc = run(client, "curl -sf http://127.0.0.1:8080/api/v1/health", timeout=15, check=False)
    health_ok = rc == 0

    client.close()

    print(f"\n{'='*60}")
    if health_ok:
        print("  ✅ DEPLOYMENT SUCCESSFUL!")
    else:
        print("  ⚠️  Service started but health check failed — check: journalctl -u otp-service -f")
    print(f"""
  API KEY (save this — shown once!):
  {api_key}

  Endpoints:
    http://{args.host}:8080/api/v1/health
    POST http://{args.host}:8080/api/v1/otp/call

  Management:
    systemctl status otp-service
    journalctl -u otp-service -f
{'='*60}
""")


if __name__ == "__main__":
    main()
