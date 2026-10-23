import os
import re
import urllib.request
import urllib.error
from typing import List, Dict, Tuple

RULES_CONFIG_DIR = os.path.expanduser("~/.gemini/config/rules")
BUNDLED_RULES_DIR = os.path.join(os.path.dirname(__file__), "..", "rules")

GITHUB_RULES_REPO_RAW = "https://raw.githubusercontent.com/Umrzoq-backend-ai/agychat/master/agychat/rules"
KNOWN_RULES = [
    "senior-developer.md",
    "cli-permissions.md",
    "security-and-secrets.md",
]


def _parse_rule_metadata(filepath: str) -> Dict[str, str]:
    """Parse frontmatter or first header from a rule markdown file."""
    meta = {
        "name": os.path.splitext(os.path.basename(filepath))[0],
        "description": "Custom rule",
    }
    
    if not os.path.exists(filepath):
        return meta

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read(4096)

        # Check for YAML frontmatter
        fm_match = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if fm_match:
            fm_text = fm_match.group(1)
            for line in fm_text.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    k = k.strip().lower()
                    v = v.strip().strip('"').strip("'")
                    if k in ("name", "description"):
                        meta[k] = v
        else:
            # Fallback: check first markdown header
            header_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            if header_match:
                meta["name"] = header_match.group(1).strip()
    except Exception:
        pass

    return meta


def get_available_rules() -> List[Dict]:
    """
    Get all available rules (bundled in agychat and/or present in ~/.gemini/config/rules).
    """
    rules_dict = {}

    # 1. Discover bundled rules
    if os.path.exists(BUNDLED_RULES_DIR):
        for fname in os.listdir(BUNDLED_RULES_DIR):
            if fname.endswith(".md"):
                b_path = os.path.join(BUNDLED_RULES_DIR, fname)
                meta = _parse_rule_metadata(b_path)
                rules_dict[fname] = {
                    "filename": fname,
                    "name": meta.get("name", fname),
                    "description": meta.get("description", ""),
                    "bundled_path": b_path,
                    "is_installed": False,
                    "installed_path": os.path.join(RULES_CONFIG_DIR, fname),
                }

    # Also make sure KNOWN_RULES are considered if bundled dir is missing for some reason
    for fname in KNOWN_RULES:
        if fname not in rules_dict:
            b_path = os.path.join(BUNDLED_RULES_DIR, fname)
            rules_dict[fname] = {
                "filename": fname,
                "name": os.path.splitext(fname)[0],
                "description": "",
                "bundled_path": b_path,
                "is_installed": False,
                "installed_path": os.path.join(RULES_CONFIG_DIR, fname),
            }

    # 2. Check installed status and discover extra user rules in ~/.gemini/config/rules
    if os.path.exists(RULES_CONFIG_DIR):
        for fname in os.listdir(RULES_CONFIG_DIR):
            if not fname.endswith(".md"):
                continue
            inst_path = os.path.join(RULES_CONFIG_DIR, fname)
            if fname in rules_dict:
                rules_dict[fname]["is_installed"] = os.path.exists(inst_path)
            else:
                meta = _parse_rule_metadata(inst_path)
                rules_dict[fname] = {
                    "filename": fname,
                    "name": meta.get("name", fname),
                    "description": meta.get("description", "User custom rule"),
                    "bundled_path": None,
                    "is_installed": True,
                    "installed_path": inst_path,
                }

    # Sort rules: senior-developer, cli-permissions, security-and-secrets, then others
    order = {"senior-developer.md": 1, "cli-permissions.md": 2, "security-and-secrets.md": 3}
    return sorted(rules_dict.values(), key=lambda r: (order.get(r["filename"], 99), r["filename"]))


def install_rule(filename: str) -> Tuple[bool, str]:
    """Install/enable a specific rule to ~/.gemini/config/rules/ via symlink or copy."""
    os.makedirs(RULES_CONFIG_DIR, exist_ok=True)
    target = os.path.join(RULES_CONFIG_DIR, filename)

    bundled = os.path.join(BUNDLED_RULES_DIR, filename)
    if not os.path.exists(bundled):
        # Try fetching from GitHub
        ok, msg = download_rule_from_github(filename)
        if not ok or not os.path.exists(bundled):
            return False, f"Rule source not found for {filename}"

    try:
        if os.path.islink(target) or os.path.exists(target):
            os.remove(target)
        try:
            os.symlink(os.path.abspath(bundled), target)
        except OSError:
            # Fallback to copy if symlink fails
            import shutil
            shutil.copy2(bundled, target)
        return True, f"Rule '{filename}' activated successfully."
    except Exception as e:
        return False, str(e)


def uninstall_rule(filename: str) -> Tuple[bool, str]:
    """Disable/uninstall a specific rule from ~/.gemini/config/rules/."""
    target = os.path.join(RULES_CONFIG_DIR, filename)
    if not os.path.exists(target) and not os.path.islink(target):
        return True, f"Rule '{filename}' is already inactive."

    try:
        os.remove(target)
        return True, f"Rule '{filename}' deactivated."
    except Exception as e:
        return False, str(e)


def toggle_rule(filename: str) -> Tuple[bool, str]:
    """Toggle a rule between active and inactive."""
    target = os.path.join(RULES_CONFIG_DIR, filename)
    if os.path.exists(target) or os.path.islink(target):
        return uninstall_rule(filename)
    else:
        return install_rule(filename)


def install_all_rules() -> Tuple[int, int]:
    """Activate all available bundled rules."""
    rules = get_available_rules()
    success_count = 0
    total_count = 0
    for r in rules:
        if r.get("bundled_path") and os.path.exists(r["bundled_path"]):
            total_count += 1
            ok, _ = install_rule(r["filename"])
            if ok:
                success_count += 1
    return success_count, total_count


def uninstall_all_rules() -> Tuple[int, int]:
    """Deactivate all rules."""
    rules = get_available_rules()
    removed_count = 0
    total_count = 0
    for r in rules:
        if r.get("is_installed"):
            total_count += 1
            ok, _ = uninstall_rule(r["filename"])
            if ok:
                removed_count += 1
    return removed_count, total_count


def download_rule_from_github(filename: str) -> Tuple[bool, str]:
    """Download a single rule file from the official gemini-ai-rules GitHub repository."""
    os.makedirs(BUNDLED_RULES_DIR, exist_ok=True)
    url = f"{GITHUB_RULES_REPO_RAW}/{filename}"
    target = os.path.join(BUNDLED_RULES_DIR, filename)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AgyChat-Rules-Manager"})
        with urllib.request.urlopen(req, timeout=5) as response:
            content = response.read()
            with open(target, "wb") as f:
                f.write(content)
        return True, f"Downloaded {filename}"
    except Exception as e:
        return False, f"Failed to download {filename}: {e}"


def sync_rules_from_github() -> Tuple[int, List[str]]:
    """
    Sync and update all standard rules from the GitHub repository:
    Umrzoq-backend-ai/agychat
    """
    synced = []
    for fname in KNOWN_RULES:
        ok, _ = download_rule_from_github(fname)
        if ok:
            synced.append(fname)
            # If it was already installed, re-link to update content
            target = os.path.join(RULES_CONFIG_DIR, fname)
            if os.path.exists(target) or os.path.islink(target):
                install_rule(fname)
    return len(synced), synced
