# NEXUS - GitHub Push Instructions

Git installation is in progress. Follow these steps once it completes.

## Step 1: Restart PowerShell

After Git installation finishes, **close and restart PowerShell** to apply the changes.

## Step 2: Navigate to Project

```powershell
cd "c:\Users\Z0056WJR\.vscode\VELORA"
```

## Step 3: Configure Git User (One-time)

```powershell
git config --global user.name "Surya Teja"
git config --global user.email "bsuryateja777@gmail.com"
```

## Step 4: Initialize Repository

```powershell
git init
```

## Step 5: Add All Files

```powershell
git add .
```

## Step 6: Create Initial Commit

```powershell
git commit -m "Initial commit: NEXUS Multi-Agent AI Intelligence Platform

- Full-stack application with React 19 frontend and FastAPI backend
- Multi-agent system with intelligent message routing
- Claude AI integration via Anthropic API
- Azure cloud services integration
- Professional system architecture diagrams
- Production-ready code with security best practices"
```

## Step 7: Rename Branch to Main

```powershell
git branch -M main
```

## Step 8: Add Remote Origin

```powershell
git remote add origin https://github.com/bsuryateja777/Nexus.git
```

## Step 9: Push to GitHub

```powershell
git push -u origin main
```

This will prompt you to authenticate. Use one of these methods:

### Option A: GitHub CLI (RECOMMENDED)

```powershell
# Install GitHub CLI
winget install GitHub.cli

# Authenticate with your Google account
gh auth login
# Select: GitHub.com
# Select: HTTPS
# Authenticate in browser with your Google account

# Then push
git push -u origin main
```

### Option B: Personal Access Token

1. Go to: https://github.com/settings/tokens/new
2. Create a new token (classic) with `repo` scope
3. When `git push` asks for password, paste the token (not your actual password)

### Option C: SSH Key

```powershell
# Generate SSH key
ssh-keygen -t ed25519 -C "bsuryateja777@gmail.com"

# Add public key to GitHub: https://github.com/settings/keys
# Copy contents of: %USERPROFILE%\.ssh\id_ed25519.pub

# Change remote to SSH
git remote set-url origin git@github.com:bsuryateja777/Nexus.git

# Push
git push -u origin main
```

## Verify Push

Once complete, verify at: https://github.com/bsuryateja777/Nexus

---

**Questions?** All commands are ready to copy-paste. Git installation should complete within 2-3 minutes.
