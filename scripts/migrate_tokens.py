import json
import os
import sys

# Add agychat/scripts to path to import from agy-oauth-manager if needed, or just copy the logic
sys.path.append(os.path.expanduser("~/agychat/scripts"))

def synthesize_cli_from_ide(ide_cred: dict) -> dict:
    t = ide_cred.get("token", {})
    return {
        "token": {
            "access_token": t.get("access_token", ""),
            "token_type": t.get("token_type", "Bearer"),
            "refresh_token": t.get("refresh_token", ""),
            "expiry": t.get("expiry", "0001-01-01T00:00:00Z")
        },
        "auth_method": "consumer",
        "id_token": ide_cred.get("id_token", "")
    }

token_file = os.path.expanduser("~/.gemini/oauth_tokens.json")

if not os.path.exists(token_file):
    print("No token file found.")
    sys.exit(0)

with open(token_file, 'r') as f:
    tokens = json.load(f)

migrated = False
new_tokens = {}

for email, value in tokens.items():
    if isinstance(value, str):
        # Old format
        migrated = True
        try:
            ide_cred = json.loads(value)
        except json.JSONDecodeError:
            print(f"Skipping {email}, invalid JSON")
            continue
            
        new_tokens[email] = {
            "email": email,
            "credentials": ide_cred.get("credentials", {}),
            "ide_format": ide_cred,
            "cli_format": synthesize_cli_from_ide(ide_cred)
        }
    else:
        new_tokens[email] = value

if migrated:
    # backup old
    os.system(f'cp "{token_file}" "{token_file}.bak"')
    with open(token_file, 'w') as f:
        json.dump(new_tokens, f, indent=4)
    print("Successfully migrated tokens to new format.")
else:
    print("Tokens are already in the new format or no old tokens found.")
