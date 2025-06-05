# Savant Smart Contract Change Analyzer

This GitHub composite Action sends two commit SHAs to Savant.Chat for full diff analysis of Solidity contracts.

## Usage

### 1. Set Up API Credentials

1. Go to [Savant.chat](https://savant.chat) and create an account.
2. Navigate to Dashboard → CI/CD → API Keys.
3. Create a new API key
4. Add the API key as a secret in your GitHub repository:
   - Go to repository Settings → Secrets and variables → Actions
   - Add a new secret named `SAVANT_API_TOKEN` containing your Savant API key.

### 2. Manual Trigger (GitHub UI)

1. Create (or update) .github/workflows/savant-smart-contract-analyzer.yml following the example-workflow.yml
2. Go to **Actions → Savant Smart Contract Analyzer → Run workflow**.  
3. Fill in:
   - **base_commit**: SHA to compare from
   - **head_commit**: SHA to compare to (defaults to `HEAD`)
   - **dry_run**: `true` or `false`
   - **tier**: `pro`, `advanced` or `lite`
4. Click **Run workflow**.

### 3. Automatic Triggers

Uncomment or add in `.github/workflows/savant-smart-contract-analyzer.yml`:

```yaml
on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]
```

Then pushes or PRs to these branches will trigger the analyzer.

### 4. GitHub CLI

```bash
# Trigger workflow_dispatch
gh workflow run savant-smart-contract-analyzer.yml \
  --ref main \
  -f base_commit=<OLD_SHA> \
  -f head_commit=<NEW_SHA> \
  -f dry_run=false \
  -f tier=lite

# List recent runs
gh run list --workflow savant-smart-contract-analyzer.yml

# View logs of the latest run
gh run view <run-id> --log
```

### 5. REST API (curl)

```bash
PAT=<your-PAT>
curl -X POST \
  -H "Authorization: Bearer $PAT" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/<owner>/<repo>/actions/workflows/savant-smart-contract-analyzer.yml/dispatches \
  -d '{
    "ref": "main",
    "inputs": {
      "base_commit": "<OLD_SHA>",
      "head_commit": "<NEW_SHA>",
      "dry_run": "false",
      "tier": "advanced"
    }
  }'
```

## .savantscope

Defines which files to include/exclude when scanning Solidity contracts. Uses .gitignore-style syntax.

```text
# Default scan scope:
contracts/**/*.sol
src/**/*.sol

# Default exclusions (ignore tests, mocks, interfaces, traits):
!**/test/**/*.sol
!**/tests/**/*.sol
!**/mock/**/*.sol
!**/mocks/**/*.sol
!**/interface/**/*.sol
!**/interfaces/**/*.sol
!**/trait/**/*.sol
!**/traits/**/*.sol
```

Place custom overrides below defaults, for example:

```text
# Ignore a specific folder:
!examples/**

# Scan only a subfolder:
src/utils/**/*.sol
```

## .savantdocs

Defines which documentation files or external links to include/exclude as part of the audit. Supports `.md`, `.txt`, `.pdf`, `.html`, and Solidity files, as well as HTTP(S) URLs.

```text
# Default documentation patterns:
docs/**/*.md
docs/**/*.mdx
docs/**/*.txt
docs/**/*.pdf
docs/**/*.html

# Default exclusions (ignore vendor or generated docs):
!node_modules/**/*
!lib/**/*
!remappings.txt
!LICENSE.md

# Example: add external link
https://example.com/docs/overview.html

# Example: exclude temporary docs
!docs/tmp/**
```

---

## Action Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `base_commit` | Base commit SHA for comparison | Yes | - |
| `head_commit` | Head commit SHA for comparison | Yes | - |
| `github_token`| GitHub token for repository access | No | `${{ github.token }}` |
| `api_token` | API token for the audit service | Yes | - |
| `api_url` | URL for the audit service API | No | `https://savant.chat/api/v1/ci-cd/requests` |
| `dry_run` | Return estimates without creating request | No | `false` |
| `tier` | Tier | No | `advanced` |

## License

MIT 
