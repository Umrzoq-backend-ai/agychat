import argparse
import base64
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional

# ─── Constants ────────────────────────────────────────────────────────────────
GEMINI_DIR       = os.path.expanduser("~/.gemini")
TOKEN_STORE      = os.path.join(GEMINI_DIR, "oauth_tokens.json")
IDE_CRED_FILE    = os.path.expanduser("~/.cache/google-vscode-extension/auth/credentials.json")
CLI_CRED_FILE    = os.path.expanduser("~/.gemini/antigravity-cli/antigravity-oauth-token")
VSCODE_DB_PATH   = os.path.expanduser("~/.config/Antigravity IDE/User/globalStorage/state.vscdb")
KEYRING_SERVICE  = "gemini"
KEYRING_USERNAME = "antigravity"
# ──────────────────────────────────────────────────────────────────────────────


def setup_environment() -> None:
    os.makedirs(GEMINI_DIR, mode=0o700, exist_ok=True)
    if os.path.exists(TOKEN_STORE):
        try:
            os.chmod(TOKEN_STORE, 0o600)
        except Exception:
            pass


def extract_email_from_jwt(id_token: str) -> str:
    if not id_token:
        return ""
    try:
        parts = id_token.split(".")
        if len(parts) < 2:
            return ""
        payload = parts[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.b64decode(payload))
        return data.get("email", "")
    except Exception:
        return ""


def get_ide_email(cred: dict) -> str:
    if not cred or not isinstance(cred, dict):
        return ""
    return cred.get("email") or extract_email_from_jwt(cred.get("credentials", {}).get("id_token", ""))


def get_cli_email(cred: dict) -> str:
    if not cred or not isinstance(cred, dict):
        return ""
    return extract_email_from_jwt(cred.get("id_token", ""))


def load_saved_tokens() -> dict:
    if os.path.exists(TOKEN_STORE):
        try:
            with open(TOKEN_STORE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_tokens(tokens: dict) -> None:
    setup_environment()
    tmp = f"{TOKEN_STORE}.tmp"
    open(tmp, "a").close()
    try:
        os.chmod(tmp, 0o600)
    except Exception:
        pass
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(tokens, f, indent=4)
    os.replace(tmp, TOKEN_STORE)


def read_json_file(path: str) -> Optional[dict]:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def write_json_file(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    tmp = f"{path}.tmp"
    open(tmp, "a").close()
    try:
        os.chmod(tmp, 0o600)
    except Exception:
        pass
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    os.replace(tmp, path)


def clear_ide_cache() -> None:
    if os.path.exists(VSCODE_DB_PATH):
        try:
            os.remove(VSCODE_DB_PATH)
        except Exception:
            pass


# ─── Keyring Helpers ──────────────────────────────────────────────────────────

def get_keyring_token() -> Optional[dict]:
    try:
        import secretstorage
        bus = secretstorage.dbus_init()
        collection = secretstorage.get_default_collection(bus)
        for item in collection.search_items({"service": KEYRING_SERVICE, "username": KEYRING_USERNAME}):
            raw = item.get_secret().decode("utf-8")
            return json.loads(raw)
    except Exception:
        pass

    try:
        import keyring
        raw = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
        if raw:
            return json.loads(raw)
    except Exception:
        pass

    return None


def set_keyring_token(token_data: dict) -> bool:
    token_str = json.dumps(token_data)
    try:
        import secretstorage
        bus = secretstorage.dbus_init()
        collection = secretstorage.get_default_collection(bus)
        for item in list(collection.search_items({"service": KEYRING_SERVICE, "username": KEYRING_USERNAME})):
            try:
                item.delete()
            except Exception:
                pass
        attributes = {"service": KEYRING_SERVICE, "username": KEYRING_USERNAME}
        collection.create_item(
            "Password for 'antigravity' on 'gemini'",
            attributes,
            token_str.encode("utf-8"),
            replace=True,
        )
        return True
    except Exception:
        pass

    try:
        import keyring
        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, token_str)
        return True
    except Exception:
        pass

    return False


def delete_keyring_token() -> None:
    try:
        import secretstorage
        bus = secretstorage.dbus_init()
        collection = secretstorage.get_default_collection(bus)
        for item in list(collection.search_items({"service": KEYRING_SERVICE, "username": KEYRING_USERNAME})):
            try:
                item.delete()
            except Exception:
                pass
    except Exception:
        pass

    try:
        import keyring
        keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
    except Exception:
        pass


# ─── Synthesis Helpers ────────────────────────────────────────────────────────

def synthesize_ide_from_cli(email: str, cli: dict) -> dict:
    try:
        t = cli.get("token", {})
        expiry_str = t.get("expiry", "")
        try:
            dt = datetime.fromisoformat(expiry_str.split(".")[0] + "+00:00")
            exp_ms = int(dt.timestamp() * 1000)
        except Exception:
            exp_ms = 0

        return {
            "email": email,
            "credentials": {
                "access_token": t.get("access_token", ""),
                "token_type": t.get("token_type", "Bearer"),
                "refresh_token": t.get("refresh_token", ""),
                "id_token": cli.get("id_token", ""),
                "expiry_date": exp_ms,
            },
        }
    except Exception:
        return {}


def synthesize_cli_from_ide(ide: dict) -> dict:
    try:
        c = ide.get("credentials", {})
        if not c and "token" in ide:
            t = ide.get("token", {})
            return {
                "token": {
                    "access_token": t.get("access_token", ""),
                    "token_type": t.get("token_type", "Bearer"),
                    "refresh_token": t.get("refresh_token", ""),
                    "expiry": t.get("expiry", ""),
                },
                "auth_method": "consumer",
                "id_token": ide.get("id_token", ""),
            }
        exp_ms = c.get("expiry_date", 0)
        if exp_ms:
            dt = datetime.fromtimestamp(exp_ms / 1000.0, tz=timezone.utc)
            expiry_str = dt.isoformat()
        else:
            expiry_str = ""

        return {
            "token": {
                "access_token": c.get("access_token", ""),
                "token_type": c.get("token_type", "Bearer"),
                "refresh_token": c.get("refresh_token", ""),
                "expiry": expiry_str,
            },
            "auth_method": "consumer",
            "id_token": c.get("id_token", ""),
        }
    except Exception:
        return {}


# ─── Core Account API ─────────────────────────────────────────────────────────

def get_current_email() -> str:
    """Detect active email from Keyring, CLI token file, or IDE."""
    keyring_tok = get_keyring_token()
    if keyring_tok:
        email = get_cli_email(keyring_tok)
        if email:
            return email

    cli_cred = read_json_file(CLI_CRED_FILE)
    if cli_cred:
        email = get_cli_email(cli_cred)
        if email:
            return email

    ide_cred = read_json_file(IDE_CRED_FILE)
    if ide_cred:
        email = get_ide_email(ide_cred)
        if email:
            return email

    return ""


def get_current_account() -> Optional[str]:
    email = get_current_email()
    return email if email else None


def get_saved_accounts() -> List[str]:
    tokens = load_saved_tokens()
    return list(tokens.keys())


def set_active_email(email: str) -> None:
    tokens = load_saved_tokens()
    if email not in tokens:
        raise ValueError(f"Account '{email}' not found.")

    acct = tokens[email]
    cli_format = acct.get("cli_format")
    if not cli_format or not isinstance(cli_format, dict):
        cli_format = synthesize_cli_from_ide(acct.get("ide_format") or acct)

    if isinstance(cli_format, dict):
        if not cli_format.get("auth_method"):
            cli_format["auth_method"] = "consumer"

    ide_format = acct.get("ide_format")
    if not ide_format or not isinstance(ide_format, dict) or "credentials" not in ide_format:
        ide_format = synthesize_ide_from_cli(email, cli_format)

    if cli_format:
        set_keyring_token(cli_format)
        write_json_file(CLI_CRED_FILE, cli_format)

    if ide_format:
        write_json_file(IDE_CRED_FILE, ide_format)

    clear_ide_cache()


def switch_account(email: str) -> Tuple[bool, str]:
    try:
        set_active_email(email)
        return True, f"Switched to {email}"
    except Exception as e:
        return False, str(e)


def save_current_account() -> Tuple[bool, str]:
    """Capture active login from Keyring, CLI, or IDE and store in oauth_tokens.json."""
    tokens = load_saved_tokens()
    keyring_cred = get_keyring_token()
    cli_cred = read_json_file(CLI_CRED_FILE)
    ide_cred = read_json_file(IDE_CRED_FILE)

    keyring_email = get_cli_email(keyring_cred)
    cli_email = get_cli_email(cli_cred)
    ide_email = get_ide_email(ide_cred)

    saved_any = False
    source_cli = keyring_cred if keyring_email else cli_cred
    source_email = keyring_email or cli_email

    if source_email and source_cli:
        if source_email not in tokens:
            tokens[source_email] = {}
        if not source_cli.get("auth_method"):
            source_cli["auth_method"] = "consumer"
        tokens[source_email]["email"] = source_email
        tokens[source_email]["cli_format"] = source_cli
        ide_syn = synthesize_ide_from_cli(source_email, source_cli)
        tokens[source_email]["ide_format"] = ide_syn
        tokens[source_email]["credentials"] = ide_syn.get("credentials", {})
        saved_any = True

    if ide_email and ide_cred:
        if ide_email not in tokens:
            tokens[ide_email] = {}
        tokens[ide_email]["email"] = ide_email
        tokens[ide_email]["credentials"] = ide_cred.get("credentials", {})
        tokens[ide_email]["ide_format"] = ide_cred
        if not tokens[ide_email].get("cli_format"):
            tokens[ide_email]["cli_format"] = synthesize_cli_from_ide(ide_cred)
        saved_any = True

    if saved_any:
        save_tokens(tokens)
        emails = list(set(filter(None, [keyring_email, cli_email, ide_email])))
        return True, f"Saved account(s): {', '.join(emails)}"
    return False, "No active accounts found in Keyring, CLI, or IDE. Please log in first."


def add_account_from_raw_token(token_str: str) -> Tuple[bool, str]:
    """Allows adding an account by pasting raw JSON credentials or token."""
    try:
        data = json.loads(token_str.strip())
        email = get_cli_email(data) or get_ide_email(data) or data.get("email", "")
        if not email:
            return False, "Could not extract email from token JSON."
        tokens = load_saved_tokens()
        tokens[email] = {
            "email": email,
            "credentials": data.get("credentials", {}),
            "ide_format": data if "credentials" in data else synthesize_ide_from_cli(email, data),
            "cli_format": data if "token" in data else synthesize_cli_from_ide(data),
        }
        save_tokens(tokens)
        return True, f"Account {email} added successfully."
    except Exception as e:
        return False, f"Invalid JSON format: {e}"


def delete_account(email: str) -> Tuple[bool, str]:
    tokens = load_saved_tokens()
    if email not in tokens:
        return False, f"Account '{email}' not found."

    del tokens[email]
    save_tokens(tokens)

    current_email = get_current_email()
    if current_email == email:
        if tokens:
            next_email = list(tokens.keys())[0]
            try:
                set_active_email(next_email)
                return True, f"Deleted {email}. Switched active to {next_email}."
            except Exception:
                pass
        else:
            delete_keyring_token()
            if os.path.exists(CLI_CRED_FILE):
                try: os.remove(CLI_CRED_FILE)
                except Exception: pass
            if os.path.exists(IDE_CRED_FILE):
                try: os.remove(IDE_CRED_FILE)
                except Exception: pass
            clear_ide_cache()
            return True, f"Deleted {email}. No accounts remaining."

    return True, f"Deleted account: {email}"


def rotate_account() -> Tuple[bool, str]:
    tokens = load_saved_tokens()
    if not tokens:
        return False, "No accounts saved."

    emails = list(tokens.keys())
    current_email = get_current_email()

    try:
        idx = emails.index(current_email)
        next_idx = (idx + 1) % len(emails)
    except ValueError:
        next_idx = 0

    next_email = emails[next_idx]
    ok, msg = switch_account(next_email)
    if ok:
        return True, next_email
    return False, msg


# ─── Status & Limits ──────────────────────────────────────────────────────────

BOLD    = "\033[1m"
DIM     = "\033[2m"
RESET   = "\033[0m"
GREEN   = "\033[32m"
YELLOW  = "\033[33m"
RED     = "\033[31m"
CYAN    = "\033[36m"
WHITE   = "\033[97m"

def _pct_color(pct: float) -> str:
    if pct >= 60: return GREEN
    elif pct >= 25: return YELLOW
    return RED

def _format_refresh(iso_ts: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = dt - now
        if diff.total_seconds() <= 0: return "refreshes soon"
        total_min = int(diff.total_seconds() / 60)
        h, m = divmod(total_min, 60)
        return f"Refreshes in {h}h {m}m" if h > 0 else f"Refreshes in {m}m"
    except Exception:
        return ""

def _parse_usage_tsv(output: str) -> dict:
    groups = {}
    for line in output.strip().split("\n"):
        parts = line.split("\t")
        if len(parts) < 3: continue
        group, ltype, pct_str = parts[0].strip(), parts[1].strip(), parts[2].strip().replace("%", "")
        iso_ts = parts[3].strip() if len(parts) > 3 else ""
        try: pct = float(pct_str)
        except Exception: continue
        if group not in groups: groups[group] = []
        groups[group].append({"type": ltype, "pct": pct, "refresh": _format_refresh(iso_ts)})
    return groups


def print_account_status() -> None:
    tokens = load_saved_tokens()
    if not tokens:
        print("No accounts saved.")
        return

    orig_keyring = get_keyring_token()
    orig_cli = read_json_file(CLI_CRED_FILE)
    orig_ide = read_json_file(IDE_CRED_FILE)
    orig_email = get_current_email()

    W = 60
    print(f"\n{BOLD}{CYAN}{'═' * W}{RESET}")
    print(f"{BOLD}{CYAN}  🤖  ANTIGRAVITY ACCOUNTS & RATE LIMITS{RESET}")
    print(f"{BOLD}{CYAN}{'═' * W}{RESET}")

    for email in tokens.keys():
        is_active = (email == orig_email)
        badge = f"{GREEN}● ACTIVE{RESET}" if is_active else f"{DIM}○ saved {RESET}"

        print(f"\n  {BOLD}{WHITE}{email}{RESET}  {badge}")
        print(f"  {DIM}{'─' * (W - 2)}{RESET}")
        print(f"  {DIM}Fetching limits...{RESET}", end="\r")
        sys.stdout.flush()

        try:
            set_active_email(email)
        except Exception:
            print(" " * 40, end="\r")
            print(f"  {RED}❌  Could not activate account{RESET}")
            continue

        env = os.environ.copy()
        env["BROWSER"] = "/bin/false"
        env.pop("DISPLAY", None)
        env.pop("WAYLAND_DISPLAY", None)
        try:
            res = subprocess.run(["agy", "-p", "/usage"], capture_output=True, text=True, timeout=12, stdin=subprocess.DEVNULL, env=env)
            combined = res.stderr + res.stdout
            if "accounts.google.com" in combined or "login" in combined.lower() or "authorization" in combined.lower():
                print(" " * 40, end="\r")
                print(f"  {RED}❌  Token expired (Login required){RESET}")
                continue
        except subprocess.TimeoutExpired:
            print(" " * 40, end="\r")
            print(f"  {RED}❌  Timeout (Waiting for auth){RESET}")
            subprocess.run(["pkill", "-f", "agy -p /usage"], capture_output=True)
            continue

        print(" " * 40, end="\r")
        if res.returncode != 0 or not res.stdout.strip():
            print(f"  {RED}❌  Could not fetch limits{RESET}")
            tokens[email]["last_limit"] = -1
            continue

        groups = _parse_usage_tsv(res.stdout)
        overall_limit = 0.0
        for group_name, limits in groups.items():
            upper_g = group_name.upper()
            g_name = "Gemini" if "GEMINI" in upper_g else "Claude/GPT" if "CLAUDE" in upper_g else group_name[:10]
            lim_strs = []
            for lim in limits:
                pct, ltype, refresh = lim["pct"], lim["type"], lim["refresh"]
                ref = refresh.replace("Refreshes in ", "").strip()
                if "h" in ref: ref = ref.split("h")[0] + "h"
                elif "m" in ref: ref = ref.split("m")[0] + "m"
                else: ref = "-"
                label = "W" if "Weekly" in ltype else "5H" if "Five" in ltype else "L"

                if "gemini" in group_name.lower():
                    if "five" in ltype.lower() or overall_limit == 0.0:
                        overall_limit = pct

                filled = round(pct / 100 * 10)
                bar = "█" * filled + "░" * (10 - filled)
                c_bar = f"{DIM}[{RESET}{_pct_color(pct)}{bar}{RESET}{DIM}]{RESET}"
                lim_strs.append(f"{DIM}{label}:{RESET} {c_bar} {_pct_color(pct)}{pct:>3.0f}%{RESET} {DIM}({ref}){RESET}")

            print(f"    {BOLD}{g_name:<10}{RESET} " + f" {DIM}│{RESET} ".join(lim_strs))

        tokens[email]["last_limit"] = overall_limit

    # Sort & persist
    sorted_emails = sorted(tokens.keys(), key=lambda e: tokens[e].get("last_limit", -1), reverse=True)
    sorted_tokens = {e: tokens[e] for e in sorted_emails}
    save_tokens(sorted_tokens)

    # Restore initial state
    if orig_keyring:
        set_keyring_token(orig_keyring)
    else:
        delete_keyring_token()

    if orig_ide: write_json_file(IDE_CRED_FILE, orig_ide)
    elif os.path.exists(IDE_CRED_FILE):
        try: os.remove(IDE_CRED_FILE)
        except Exception: pass

    if orig_cli: write_json_file(CLI_CRED_FILE, orig_cli)
    elif os.path.exists(CLI_CRED_FILE):
        try: os.remove(CLI_CRED_FILE)
        except Exception: pass

    clear_ide_cache()
    print(f"\n{BOLD}{CYAN}{'═' * W}{RESET}\n")


# ─── CLI Entrypoint for agy-oauth-manager compatibility ───────────────────────

def cli_main() -> None:
    parser = argparse.ArgumentParser(description="Antigravity Account & OAuth Manager")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--save", action="store_true", help="Save active account")
    group.add_argument("--rotate", action="store_true", help="Rotate to next account")
    group.add_argument("--current", action="store_true", help="Show current account")
    group.add_argument("--status", action="store_true", help="Check limits across accounts")
    group.add_argument("--switch", type=str, metavar="EMAIL", help="Switch to account")
    group.add_argument("--delete", type=str, metavar="EMAIL", help="Delete account")
    args = parser.parse_args()

    if args.save:
        ok, msg = save_current_account()
        print(f"✅ {msg}" if ok else f"❌ {msg}", file=sys.stdout if ok else sys.stderr)
        sys.exit(0 if ok else 1)
    elif args.rotate:
        ok, msg = rotate_account()
        if ok:
            print(f"ECHO_EMAIL:{msg}")
            sys.exit(0)
        else:
            print(msg, file=sys.stderr)
            sys.exit(1)
    elif args.current:
        email = get_current_email()
        if email:
            print(f"ECHO_EMAIL:{email}")
        else:
            print("No active account.", file=sys.stderr)
            sys.exit(1)
    elif args.status:
        print_account_status()
    elif args.switch:
        ok, msg = switch_account(args.switch)
        print(f"✅ {msg}" if ok else f"❌ {msg}", file=sys.stdout if ok else sys.stderr)
        sys.exit(0 if ok else 1)
    elif args.delete:
        ok, msg = delete_account(args.delete)
        print(f"✅ {msg}" if ok else f"❌ {msg}", file=sys.stdout if ok else sys.stderr)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    cli_main()
