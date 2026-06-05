#!/usr/bin/env python3
"""Phased deploy orchestrator for the static-sites infrastructure.

Runs the full Phase 1 bring-up step by step and validates each step:

  1. preflight  - delete existing apex A-records in Cloudflare (mail/MX untouched)
  2. bootstrap  - create the S3 bucket for Terraform remote state
  3. apply      - terraform apply (EC2, EIP, SG, SSH key, ECR Public repos, DNS A-records)
  4. outputs    - read terraform outputs and write EC2_HOST / ECR_PUBLIC_ALIAS into .env
  5. seed       - build and push the first image for all 6 sites to ECR Public
  6. ship       - copy compose/ and scripts/ to the EC2 host over SSH
  7. up         - docker compose pull && up -d on the EC2 host
  8. validate   - DNS + HTTPS + HTTP->HTTPS redirect checks for all 6 domains

Only the Python standard library is used. Requires terraform, docker, aws, ssh, scp on PATH.

Examples:
  python scripts/deploy_all.py --phase all
  python scripts/deploy_all.py --phase preflight --dns-dry-run
  python scripts/deploy_all.py --phase validate
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env"

# domain -> service_name (must match terraform locals and docker-compose)
SERVICES: dict[str, str] = {
    "buyraq.com": "buyraq",
    "codehelp.pp.ua": "codehelp",
    "cosmeticpro.pp.ua": "cosmeticpro",
    "ddnsteltonicka.pp.ua": "ddnsteltonicka",
    "solovkadmytro.pp.ua": "solovkadmytro",
    "solovkaskincare.pp.ua": "solovkaskincare",
}

PHASES = ["preflight", "bootstrap", "apply", "outputs", "seed", "ship", "up", "validate"]
# 'destroy', 'secrets', and 'github' are intentionally NOT part of 'all'; they are run explicitly.
EXTRA_PHASES = ["destroy", "secrets", "github"]
CF_API = "https://api.cloudflare.com/client/v4"
GITHUB_API = "https://api.github.com"

# GitHub Actions secrets sourced straight from .env (key in .env -> secret name).
SECRET_ENV_KEYS = [
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_EMAIL",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_REGION",
    "AWS_BUCKET_NAME",
    "ECR_PUBLIC_ALIAS",
    "EC2_HOST",
]


# --------------------------------------------------------------------------- logging
def log(msg: str) -> None:
    print(f"[deploy] {msg}", flush=True)


def step(msg: str) -> None:
    print(f"\n=== {msg} ===", flush=True)


def die(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    print(f"[deploy][ERROR] {msg}", file=sys.stderr, flush=True)
    sys.exit(1)


# --------------------------------------------------------------------------- helpers
def load_env(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE .env file into a dict (no export semantics)."""
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name:
            env[name] = value
    return env


def require(env: dict[str, str], *keys: str) -> None:
    missing = [k for k in keys if not env.get(k)]
    if missing:
        die(f"missing required .env values: {', '.join(missing)}")


def validate_s3_bucket_name(name: str) -> None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", name):
        die(
            "AWS_BUCKET_NAME is not a valid S3 bucket name. Use 3-63 chars: "
            "lowercase letters, numbers, dots, and hyphens only. No underscores."
        )
    if "_" in name:
        die("AWS_BUCKET_NAME cannot contain underscores. Use hyphens instead.")


def run(cmd: list[str], cwd: Path | None = None, extra_env: dict[str, str] | None = None) -> None:
    """Run a command, stream output, raise on non-zero exit."""
    printable = " ".join(cmd)
    log(f"$ {printable}")
    proc_env = os.environ.copy()
    if extra_env:
        proc_env.update(extra_env)
    result = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=proc_env)
    if result.returncode != 0:
        die(f"command failed ({result.returncode}): {printable}")


def run_capture(cmd: list[str], cwd: Path | None = None, extra_env: dict[str, str] | None = None) -> str:
    proc_env = os.environ.copy()
    if extra_env:
        proc_env.update(extra_env)
    result = subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, env=proc_env,
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        die(f"command failed ({result.returncode}): {' '.join(cmd)}\n{result.stderr}")
    return result.stdout


def cf_request(method: str, url: str, token: str) -> dict:
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        die(f"Cloudflare API {method} {url} failed: {exc.code} {body}")


# --------------------------------------------------------------------------- phases
def phase_preflight(env: dict[str, str], dns_dry_run: bool) -> None:
    step("Phase 1: Cloudflare DNS preflight (apex A-records only)")
    require(env, "CLOUDFLARE_API_TOKEN")
    token = env["CLOUDFLARE_API_TOKEN"]

    for domain in SERVICES:
        zones = cf_request("GET", f"{CF_API}/zones?name={domain}", token)
        if not zones.get("success") or not zones.get("result"):
            log(f"{domain}: zone not found in account; skipping")
            continue
        zone_id = zones["result"][0]["id"]
        recs = cf_request("GET", f"{CF_API}/zones/{zone_id}/dns_records?type=A&name={domain}", token)
        apex = [r for r in recs.get("result", []) if r["type"] == "A" and r["name"] == domain]
        if not apex:
            log(f"{domain}: no apex A-record; nothing to delete")
            continue
        for rec in apex:
            if dns_dry_run:
                log(f"{domain}: [dry-run] would delete A -> {rec['content']} (proxied={rec['proxied']})")
            else:
                cf_request("DELETE", f"{CF_API}/zones/{zone_id}/dns_records/{rec['id']}", token)
                log(f"{domain}: deleted A -> {rec['content']}")
    if dns_dry_run:
        log("dry-run complete; re-run without --dns-dry-run to delete")


def phase_bootstrap(env: dict[str, str]) -> None:
    step("Phase 2: bootstrap S3 state bucket")
    require(env, "AWS_BUCKET_NAME")
    validate_s3_bucket_name(env["AWS_BUCKET_NAME"])
    region = env.get("AWS_REGION", "us-east-1")
    bdir = REPO_ROOT / "terraform" / "bootstrap"
    run(["terraform", "init", "-input=false"], cwd=bdir)
    run(
        ["terraform", "apply", "-auto-approve", "-input=false",
         f"-var=bucket_name={env['AWS_BUCKET_NAME']}",
         f"-var=aws_region={region}"],
        cwd=bdir,
    )


def phase_apply(env: dict[str, str], auto_approve: bool) -> None:
    step("Phase 3: terraform apply (infrastructure + DNS)")
    require(env, "AWS_BUCKET_NAME", "CLOUDFLARE_API_TOKEN")
    validate_s3_bucket_name(env["AWS_BUCKET_NAME"])
    tdir = REPO_ROOT / "terraform"
    region = env.get("AWS_REGION", "us-east-1")
    tf_env = {
        "TF_VAR_cloudflare_api_token": env["CLOUDFLARE_API_TOKEN"],
        "TF_VAR_aws_region": region,
    }
    terraform_init(env, tdir)
    run(["terraform", "plan", "-input=false"], cwd=tdir, extra_env=tf_env)
    if not auto_approve:
        ans = input("[deploy] Review the plan above. Type 'yes' to apply: ").strip().lower()
        if ans != "yes":
            die("aborted by user before apply")
    run(["terraform", "apply", "-auto-approve", "-input=false"], cwd=tdir, extra_env=tf_env)


def terraform_init(env: dict[str, str], tdir: Path) -> None:
    require(env, "AWS_BUCKET_NAME")
    validate_s3_bucket_name(env["AWS_BUCKET_NAME"])
    region = env.get("AWS_REGION", "us-east-1")
    run(
        ["terraform", "init", "-input=false", "-reconfigure",
         f"-backend-config=bucket={env['AWS_BUCKET_NAME']}",
         f"-backend-config=region={region}"],
        cwd=tdir,
    )


def write_ssh_key(tdir: Path) -> None:
    """Write the deploy private/public keys from terraform output and lock down permissions."""
    ssh_dir = REPO_ROOT / ".ssh"
    ssh_dir.mkdir(exist_ok=True)
    priv = run_capture(["terraform", "output", "-raw", "ssh_private_key"], cwd=tdir)
    pub = run_capture(["terraform", "output", "-raw", "ssh_public_key"], cwd=tdir)
    key_path = ssh_dir / "project_key"
    # A previous run may have locked the key down to read-only; restore write access first.
    _make_writable(key_path)
    # OpenSSH requires a trailing newline on the private key.
    key_path.write_text(priv if priv.endswith("\n") else priv + "\n", encoding="utf-8", newline="\n")
    (ssh_dir / "project_key.pub").write_text(
        pub if pub.endswith("\n") else pub + "\n", encoding="utf-8", newline="\n"
    )
    _restrict_key_permissions(key_path)
    log(f"wrote SSH key to {key_path}")


def _make_writable(key_path: Path) -> None:
    """Restore write access to a key that a previous run locked down to read-only.

    The file owner can always rewrite its DACL, so `icacls /reset` (restore inherited, writable
    permissions) is reliable even when the current ACL grants only read. The read-only attribute is
    cleared too for good measure.
    """
    if not key_path.exists():
        return
    if sys.platform == "win32":
        subprocess.run(["icacls", str(key_path), "/reset"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["attrib", "-R", str(key_path)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        os.chmod(key_path, 0o600)


def _restrict_key_permissions(key_path: Path) -> None:
    """Make the private key readable only by the current user (ssh refuses world-readable keys)."""
    if sys.platform == "win32":
        user = os.environ.get("USERNAME", "")
        if not user:
            return
        subprocess.run(["icacls", str(key_path), "/inheritance:r"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["icacls", str(key_path), "/grant:r", f"{user}:R"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["icacls", str(key_path), "/remove:g", "BUILTIN\\Users",
                        "Authenticated Users", "Everyone", "Users"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        os.chmod(key_path, 0o600)


def phase_outputs(env: dict[str, str]) -> dict[str, str]:
    step("Phase 4: read terraform outputs and update .env")
    tdir = REPO_ROOT / "terraform"
    terraform_init(env, tdir)
    raw = run_capture(["terraform", "output", "-json"], cwd=tdir)
    outputs = json.loads(raw)

    public_ip = outputs.get("public_ip", {}).get("value")
    if not public_ip:
        die("terraform output 'public_ip' is empty")

    uris = outputs.get("ecr_repository_uris", {}).get("value", {})
    alias = ""
    for uri in uris.values():
        # public.ecr.aws/<alias>/<service>
        parts = uri.split("/")
        if len(parts) >= 3:
            alias = parts[1]
            break
    if not alias:
        die("could not derive ECR_PUBLIC_ALIAS from terraform outputs")

    # Terraform no longer writes the key to disk; pull it from the sensitive output and write it
    # locally so the ship/up phases can SSH into the instance.
    write_ssh_key(tdir)

    _update_env_file({"EC2_HOST": public_ip, "ECR_PUBLIC_ALIAS": alias})
    log(f"EC2_HOST={public_ip}")
    log(f"ECR_PUBLIC_ALIAS={alias}")
    env["EC2_HOST"] = public_ip
    env["ECR_PUBLIC_ALIAS"] = alias
    return env


def _update_env_file(updates: dict[str, str]) -> None:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                out.append(f"{key}={updates[key]}")
                seen.add(key)
                continue
        out.append(line)
    for key, value in updates.items():
        if key not in seen:
            out.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")


def ensure_docker_daemon(timeout: int = 180) -> None:
    """Verify the Docker daemon is reachable; on Windows try to start Docker Desktop and wait."""
    if subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        return
    if sys.platform == "win32":
        candidates = [
            Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Docker" / "Docker" / "Docker Desktop.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Docker" / "Docker Desktop.exe",
        ]
        exe = next((c for c in candidates if c.exists()), None)
        if exe is not None:
            log(f"Docker daemon not running; starting {exe.name} ...")
            subprocess.Popen([str(exe)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            die("Docker daemon not running and Docker Desktop.exe not found; start Docker manually")
    else:
        die("Docker daemon not running; start it and re-run")

    log("Waiting for Docker daemon to become ready ...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        if subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            log("Docker daemon is ready")
            return
        time.sleep(5)
    die("Docker daemon did not become ready in time; start Docker Desktop and re-run")


def phase_seed(env: dict[str, str]) -> None:
    step("Phase 5: build and push first images to ECR Public")
    require(env, "ECR_PUBLIC_ALIAS")
    alias = env["ECR_PUBLIC_ALIAS"]

    ensure_docker_daemon()

    # Write the registry auth directly into an isolated DOCKER_CONFIG instead of calling
    # `docker login`. On Windows the Docker Desktop credential helper ("desktop") fails to save the
    # long ECR Public token ("The stub received bad data"); writing the base64 auth inline (with no
    # credsStore) lets `docker push` authenticate without ever invoking the broken helper.
    # ECR Public's API only exists in us-east-1, so the region is pinned regardless of AWS_REGION.
    pwd = run_capture(["aws", "ecr-public", "get-login-password", "--region", "us-east-1"])
    auth_b64 = base64.b64encode(f"AWS:{pwd}".encode()).decode()
    config = {"auths": {"public.ecr.aws": {"auth": auth_b64}}}
    docker_cfg = Path(tempfile.mkdtemp(prefix="docker-cfg-"))
    (docker_cfg / "config.json").write_text(json.dumps(config), encoding="utf-8")
    docker_env = {"DOCKER_CONFIG": str(docker_cfg)}

    dockerfile = str(REPO_ROOT / "templates" / "app-repo" / "Dockerfile")
    for domain, service in SERVICES.items():
        image = f"public.ecr.aws/{alias}/{service}"
        context = str(REPO_ROOT / "sites" / service)
        run(["docker", "build", "-t", f"{image}:latest", "-f", dockerfile, context], extra_env=docker_env)
        run(["docker", "push", f"{image}:latest"], extra_env=docker_env)
        log(f"{domain}: pushed {image}:latest")


def phase_ship(env: dict[str, str]) -> None:
    step("Phase 6: ship compose/ and scripts/ to EC2")
    require(env, "EC2_HOST")
    host = env["EC2_HOST"]
    key = str(REPO_ROOT / ".ssh" / "project_key")
    target = f"ubuntu@{host}"
    run(["ssh", "-i", key, "-o", "StrictHostKeyChecking=accept-new", target, "mkdir -p ~/infra-repo"])
    run(["scp", "-i", key, "-r",
         str(REPO_ROOT / "compose"), str(REPO_ROOT / "scripts"),
         f"{target}:~/infra-repo/"])


def phase_up(env: dict[str, str]) -> None:
    step("Phase 7: docker compose up on EC2")
    require(env, "EC2_HOST", "ECR_PUBLIC_ALIAS")
    host = env["EC2_HOST"]
    key = str(REPO_ROOT / ".ssh" / "project_key")
    alias = env["ECR_PUBLIC_ALIAS"]
    remote = (
        f"cd ~/infra-repo/compose && export ECR_PUBLIC_ALIAS={alias} && "
        "docker compose pull && docker compose up -d && docker compose ps"
    )
    run(["ssh", "-i", key, "-o", "StrictHostKeyChecking=accept-new", f"ubuntu@{host}", remote])


def phase_validate(env: dict[str, str], wait: int) -> None:
    step("Phase 8: validate DNS + HTTPS + redirect for all 6 domains")
    expected_ip = env.get("EC2_HOST", "")
    failures: list[str] = []

    for domain in SERVICES:
        # DNS
        try:
            _, _, ips = socket.gethostbyname_ex(domain)
        except socket.gaierror as exc:
            failures.append(f"DNS: {domain} did not resolve ({exc})")
            ips = []
        if ips:
            if expected_ip and expected_ip not in ips:
                failures.append(f"DNS: {domain} -> {ips}, expected {expected_ip}")
            else:
                log(f"{domain}: DNS -> {', '.join(ips)}")

        # HTTPS (retry for ACME cert issuance)
        https_ok = _wait_https(domain, wait)
        if not https_ok:
            failures.append(f"HTTPS: https://{domain} not healthy within {wait}s")
        else:
            log(f"{domain}: HTTPS 200 OK")

        # HTTP -> HTTPS redirect
        code = _http_status(f"http://{domain}")
        if code in (301, 308):
            log(f"{domain}: HTTP redirect {code} OK")
        else:
            failures.append(f"REDIRECT: http://{domain} returned {code}, expected 301/308")

    if failures:
        for f in failures:
            print(f"[deploy][FAIL] {f}", file=sys.stderr)
        die(f"validation failed: {len(failures)} issue(s)")
    log("validation passed: 6/6 domains healthy")


def _gh_request(method: str, path: str, token: str, payload: dict | None = None) -> dict:
    url = f"{GITHUB_API}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, method=method, data=data)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        die(f"GitHub API {method} {path} failed: {exc.code} {detail}")


def _repo_slug() -> str:
    """Derive 'owner/repo' from the origin remote URL."""
    url = run_capture(["git", "config", "--get", "remote.origin.url"]).strip()
    slug = url.removesuffix(".git").replace("git@github.com:", "").replace("https://github.com/", "")
    if slug.count("/") != 1:
        die(f"could not parse owner/repo from remote url: {url}")
    return slug


def _github_token(env: dict[str, str]) -> str:
    token = env.get("GITHUB_TOKEN") or env.get("INFRA_REPO_DISPATCH_TOKEN")
    if not token:
        die("set GITHUB_TOKEN (or INFRA_REPO_DISPATCH_TOKEN) in .env with 'repo' scope")
    return token


def _current_branch() -> str:
    branch = run_capture(["git", "branch", "--show-current"]).strip()
    if not branch:
        die("could not determine the current git branch")
    return branch


def _ensure_branch_pushed(repo: str, token: str, branch: str) -> None:
    dirty = run_capture(["git", "status", "--porcelain"]).strip()
    if dirty:
        die(
            "local changes are not committed. GitHub Actions runs code from GitHub, "
            "not from this working tree. Commit and push the changes first."
        )

    # When already on main, the commit is promoted directly by _push_head_to_main, so there is
    # nothing to compare against yet. Only feature branches must already exist on the remote.
    if branch == "main":
        return

    local_sha = run_capture(["git", "rev-parse", "HEAD"]).strip()
    try:
        remote_ref = _gh_request("GET", f"/repos/{repo}/git/ref/heads/{branch}", token)
    except SystemExit:
        die(f"branch '{branch}' is not available on GitHub; commit and push this branch before triggering Actions")
    remote_sha = remote_ref.get("object", {}).get("sha")
    if remote_sha != local_sha:
        die(
            f"GitHub branch '{branch}' is not at local HEAD. "
            "Commit/push local changes first so Actions runs the same code."
        )


def validate_aws_credentials(env: dict[str, str]) -> None:
    """Verify the AWS credentials from .env before syncing them to GitHub Secrets.

    The .env values are validated in isolation: any ambient AWS_* variables (e.g. a stale
    AWS_SESSION_TOKEN or AWS_PROFILE left in the shell) are stripped so we test exactly the keys
    that get pushed to GitHub Secrets, not whatever the local shell happens to hold.
    """
    require(env, "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION")
    clean_env = {k: v for k, v in os.environ.items() if not k.startswith("AWS_")}
    clean_env["AWS_ACCESS_KEY_ID"] = env["AWS_ACCESS_KEY_ID"]
    clean_env["AWS_SECRET_ACCESS_KEY"] = env["AWS_SECRET_ACCESS_KEY"]
    clean_env["AWS_REGION"] = env["AWS_REGION"]
    clean_env["AWS_DEFAULT_REGION"] = env["AWS_REGION"]
    if env.get("AWS_SESSION_TOKEN"):
        clean_env["AWS_SESSION_TOKEN"] = env["AWS_SESSION_TOKEN"]
    result = subprocess.run(
        ["aws", "sts", "get-caller-identity"],
        env=clean_env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        die("AWS credentials from .env are invalid; update AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY"
            " (and AWS_SESSION_TOKEN if these are temporary credentials), then rerun\n"
            + result.stderr.strip())
    log("AWS credentials verified")


def phase_secrets(env: dict[str, str]) -> None:
    step("Push GitHub Actions secrets from .env")
    from nacl import encoding, public  # local import: only needed for this phase

    token = _github_token(env)
    repo = _repo_slug()
    log(f"target repository: {repo}")

    validate_aws_credentials(env)

    # Collect secret name -> value. Region for EC2/S3 comes from .env; ECR Public is separate.
    secrets: dict[str, str] = {}
    for key in SECRET_ENV_KEYS:
        if env.get(key):
            secrets[key] = env[key]
    missing = [k for k in SECRET_ENV_KEYS if k not in secrets]
    if missing:
        log(f"warning: skipping unset .env keys: {', '.join(missing)}")
    dispatch_token = env.get("INFRA_REPO_DISPATCH_TOKEN") or env.get("GITHUB_TOKEN")
    if dispatch_token:
        secrets["INFRA_REPO_DISPATCH_TOKEN"] = dispatch_token

    key_file = REPO_ROOT / ".ssh" / "project_key"
    if key_file.exists():
        secrets["EC2_SSH_PRIVATE_KEY"] = key_file.read_text(encoding="utf-8")
    else:
        log("warning: .ssh/project_key not found; skipping EC2_SSH_PRIVATE_KEY")

    if not secrets:
        die("no secrets to push; populate .env first")

    pk = _gh_request("GET", f"/repos/{repo}/actions/secrets/public-key", token)
    box = public.SealedBox(public.PublicKey(pk["key"].encode(), encoding.Base64Encoder()))

    for name, value in secrets.items():
        encrypted = base64.b64encode(box.encrypt(value.encode("utf-8"))).decode("utf-8")
        _gh_request(
            "PUT", f"/repos/{repo}/actions/secrets/{name}", token,
            {"encrypted_value": encrypted, "key_id": pk["key_id"]},
        )
        log(f"set secret {name}")
    log(f"pushed {len(secrets)} secret(s) to {repo}")


def _push_head_to_main(token: str) -> None:
    """Push the current commit to origin/main (the only trigger for the deploy workflow).

    The token is passed via an inline http.extraHeader and is never logged.
    """
    basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    proc_env = os.environ.copy()
    proc_env["GIT_TERMINAL_PROMPT"] = "0"
    log("$ git push origin HEAD:main")
    result = subprocess.run(
        ["git", "-c", f"http.extraHeader=Authorization: Basic {basic}", "push", "origin", "HEAD:main"],
        env=proc_env,
    )
    if result.returncode != 0:
        die("git push to main failed (main may have diverged; merge origin/main locally and retry)")


def phase_github(env: dict[str, str]) -> None:
    step("Sync secrets and promote to main (Actions deploys on main push only)")
    token = _github_token(env)
    repo = _repo_slug()
    branch = _current_branch()

    # Keep generated runtime values and SSH key synced before uploading secrets.
    env = phase_outputs(env)
    phase_secrets(env)

    # Infra updates run only when main advances; push the committed HEAD onto main.
    _ensure_branch_pushed(repo, token, branch)
    _push_head_to_main(token)
    log(f"pushed '{branch}' -> main; GitHub Actions 'Deploy' runs on the main push")


def empty_ecr_public_repos() -> None:
    """Delete all images from each ECR Public repo so Terraform can drop the repos.

    ECR Public is a global service whose API lives only in us-east-1, so the region is pinned
    regardless of AWS_REGION. Missing repos are ignored.
    """
    log("emptying ECR Public repositories before destroy")
    for service in SERVICES.values():
        describe = subprocess.run(
            ["aws", "ecr-public", "describe-images", "--region", "us-east-1",
             "--repository-name", service,
             "--query", "imageDetails[].imageDigest", "--output", "text"],
            capture_output=True, text=True,
        )
        if describe.returncode != 0:
            log(f"{service}: repo not found or no access; skipping")
            continue
        digests = describe.stdout.split()
        if not digests:
            log(f"{service}: already empty")
            continue
        image_ids = [arg for d in digests for arg in ("imageDigest=" + d,)]
        delete = subprocess.run(
            ["aws", "ecr-public", "batch-delete-image", "--region", "us-east-1",
             "--repository-name", service, "--image-ids", *image_ids],
            capture_output=True, text=True,
        )
        if delete.returncode != 0:
            log(f"{service}: failed to delete images: {delete.stderr.strip()}")
        else:
            log(f"{service}: deleted {len(digests)} image(s)")


def phase_destroy(env: dict[str, str], auto_approve: bool, include_bucket: bool) -> None:
    step("DESTROY: tear down all paid AWS resources (EC2, EIP, ECR) + DNS A-records")
    require(env, "AWS_BUCKET_NAME", "CLOUDFLARE_API_TOKEN")
    validate_s3_bucket_name(env["AWS_BUCKET_NAME"])
    region = env.get("AWS_REGION", "us-east-1")
    tf_env = {
        "TF_VAR_cloudflare_api_token": env["CLOUDFLARE_API_TOKEN"],
        "TF_VAR_aws_region": region,
    }

    if not auto_approve:
        ans = input("[deploy] This DESTROYS the EC2 instance, Elastic IP, ECR repos and site "
                    "A-records. Type 'destroy' to confirm: ").strip().lower()
        if ans != "destroy":
            die("aborted by user before destroy")

    empty_ecr_public_repos()

    tdir = REPO_ROOT / "terraform"
    terraform_init(env, tdir)
    run(["terraform", "destroy", "-auto-approve", "-input=false"], cwd=tdir, extra_env=tf_env)
    log("main infrastructure destroyed")

    if include_bucket:
        bdir = REPO_ROOT / "terraform" / "bootstrap"
        run(["terraform", "init", "-input=false"], cwd=bdir)
        run(
            ["terraform", "destroy", "-auto-approve", "-input=false",
             f"-var=bucket_name={env['AWS_BUCKET_NAME']}",
             f"-var=aws_region={region}"],
            cwd=bdir,
        )
        log("state bucket destroyed")
    else:
        log("kept the S3 state bucket; re-run with --include-bucket to remove it too")


def _http_status(url: str) -> int:
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):  # noqa: D401
            return None

    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(url, timeout=15) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except Exception:  # noqa: BLE001
        return 0


def _wait_https(domain: str, wait: int) -> bool:
    ctx = ssl.create_default_context()
    deadline = time.time() + max(wait, 1)
    while True:
        try:
            req = urllib.request.Request(f"https://{domain}", method="GET")
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                if 200 <= resp.status < 400:
                    return True
        except Exception:  # noqa: BLE001
            pass
        if time.time() >= deadline:
            return False
        time.sleep(5)


# --------------------------------------------------------------------------- main
def main() -> None:
    parser = argparse.ArgumentParser(description="Phased deploy orchestrator")
    parser.add_argument("--phase", default="all", choices=["all", *PHASES, *EXTRA_PHASES],
                        help="run a single phase, 'all', 'destroy', 'secrets', or 'github' "
                             "(github: sync secrets + push HEAD to main to trigger deploy)")
    parser.add_argument("--yes", action="store_true", help="non-interactive: auto-approve apply/destroy")
    parser.add_argument("--dns-dry-run", action="store_true", help="preflight: only list apex A-records")
    parser.add_argument("--https-wait", type=int, default=120,
                        help="seconds to wait for HTTPS/ACME per domain during validate")
    parser.add_argument("--include-bucket", action="store_true",
                        help="destroy: also remove the S3 Terraform state bucket")
    args = parser.parse_args()

    env = load_env(ENV_FILE)

    if args.phase == "destroy":
        phase_destroy(env, args.yes, args.include_bucket)
        log("done")
        return

    if args.phase == "secrets":
        phase_secrets(env)
        log("done")
        return

    if args.phase == "github":
        phase_github(env)
        log("done")
        return

    selected = PHASES if args.phase == "all" else [args.phase]

    for name in selected:
        if name == "preflight":
            phase_preflight(env, args.dns_dry_run)
        elif name == "bootstrap":
            phase_bootstrap(env)
        elif name == "apply":
            phase_apply(env, args.yes)
        elif name == "outputs":
            env = phase_outputs(env)
        elif name == "seed":
            phase_seed(env)
        elif name == "ship":
            phase_ship(env)
        elif name == "up":
            phase_up(env)
        elif name == "validate":
            phase_validate(env, args.https_wait)

    log("done")


if __name__ == "__main__":
    main()
