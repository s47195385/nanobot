---
name: memory-github
description: "Back up and restore nanobot workspace memory (MEMORY.md, HISTORY.md, HEARTBEAT.md) to/from a private GitHub repository."
metadata: {"nanobot":{"emoji":"🧠","requires":{"bins":["gh","git"]},"install":[{"id":"brew-gh","kind":"brew","formula":"gh","bins":["gh"],"label":"Install GitHub CLI (brew)"},{"id":"apt-gh","kind":"apt","package":"gh","bins":["gh"],"label":"Install GitHub CLI (apt)"}]}}
---

# Memory ↔ GitHub Skill

Keep your agent's memory safe and portable by pushing it to a private GitHub
repository.  All operations use the `gh` and `git` CLI tools already available
on most macOS / Linux systems.

## One-time setup

```bash
# Authenticate GitHub CLI (if not done yet)
gh auth login

# Create a private backup repo (run once)
gh repo create <your-github-username>/nanobot-memory --private --confirm
```

## Push memory to GitHub

```bash
cd ~/.nanobot

# Initialise the workspace as a git repo (first time only)
git -C workspace init
git -C workspace remote add origin https://github.com/<username>/nanobot-memory.git 2>/dev/null || true

# Stage memory files and commit
git -C workspace add memory/MEMORY.md memory/HISTORY.md HEARTBEAT.md
git -C workspace commit -m "chore: memory snapshot $(date '+%Y-%m-%d %H:%M')"
git -C workspace push -u origin main
```

## Pull memory from GitHub (restore on a new machine)

```bash
# Clone the backup repo into the nanobot workspace
git clone https://github.com/<username>/nanobot-memory.git ~/.nanobot/workspace

# Point nanobot at the restored workspace
# (or let the default ~/.nanobot/workspace path take effect automatically)
```

## Automate via HEARTBEAT.md

Add a task to `HEARTBEAT.md` to push memory automatically:

```markdown
## Active Tasks

- [ ] Push workspace memory snapshot to GitHub (memory-github skill)
```

The agent will use the steps above to commit and push memory on the next
heartbeat tick.

## Exclude sensitive files

Create a `.gitignore` inside the workspace to skip files you don't want backed
up:

```
# ~/.nanobot/workspace/.gitignore
*.log
*.tmp
```

## Tips

- Use a **private** repository so your memory is not publicly accessible.
- Commit messages include the timestamp so you can audit the history.
- On a new machine: clone the repo, run `nanobot gateway`, and your agent
  will have full memory from day one.
