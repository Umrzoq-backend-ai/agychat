---
name: cli-permissions
description: Agent permissions for autonomous CLI tool usage and executing routine commands without confirmation
trigger: always_on
---

# CLI Tool Permissions & Autonomous Execution Protocol

The user has explicitly granted you full permission to execute CLI commands autonomously without asking for confirmation first. You operate with maximum autonomy to solve problems, inspect code, run builds, and verify your work.

## 1. Zero Permission Friction for Routine Commands
NEVER interrupt the user with confirmation prompts like *"May I run this command?"*, *"Should I check the git status?"*, or *"Can I run tests?"*. Execute all routine, safe, and standard developer commands directly and proactively.

### Fully Pre-Approved Commands & Tools:
- **Everyday Shell & File Inspection**: `ls`, `cat`, `head`, `tail`, `grep`, `find`, `diff`, `stat`, `wc`, `du`, `pwd`, `tree`, `jq`, `sed`, `awk`, `mkdir`, `cp`, `mv`.
- **Git Operations**: `git status`, `git diff`, `git log`, `git add`, `git commit`, `git checkout`, `git switch`, `git branch`, `git fetch`, `git pull`, `git push`, `git stash`.
- **Developer CLI Platforms**: `gh` (GitHub CLI), `vercel`, `render`, `flyctl`, `netlify`, `docker` (build, inspect, test).
- **Package Managers & Environments**: `uv`, `pip`, `pipx`, `npm`, `pnpm`, `yarn`, `bun`, `cargo`, `go`, `make`, `composer`.
- **Testing, Linting & Type Checking**: `pytest`, `unittest`, `cargo test`, `go test`, `npm test`, `ruff`, `mypy`, `flake8`, `eslint`, `prettier`, `tsc`.
- **System & Network Diagnostics**: `which`, `uname`, `whoami`, `env`, `curl`, `wget`, `netstat`, `ps`.

## 2. Proactive "Just Do It" Principle
- **Act First, Verify Autonomously**: If you need to know what files exist, run `ls`. If you need to verify tests pass, run the test runner. If you need to check git changes, run `git status`. Do not propose or ask—execute.
- **Self-Healing on Errors**: If a command fails or returns an error, do not immediately ask the user what to do. Inspect the error output, diagnose the issue, self-correct, and re-execute.
- **Background Processes**: For persistent dev servers or watchers, launch them cleanly without blocking or asking redundant questions.

## 3. Strict Safety Boundaries (Only Ask for Destructive Operations)
Prompt the user for explicit confirmation ONLY if an action is non-recoverable, irreversible, and destructive:
- Destroying production databases (`DROP DATABASE`, `TRUNCATE`, bulk deletions without WHERE).
- Deleting live cloud projects or cloud accounts (`gcloud projects delete`, destroying KMS keys).
- Irrevocable repository destruction (`gh repo delete`).
- System-wide destructive deletion (e.g. `rm -rf /` or untargeted recursive deletion outside the project scope).

For all other everyday coding, building, testing, linting, git, and deployment operations: **EXECUTE IMMEDIATELY AND AUTONOMOUSLY.**
