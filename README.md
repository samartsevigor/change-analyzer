# Savant Smart Contract Change Analyzer

This workflow helps you spot and audit Solidity changes by comparing two commit SHAs and sending the diff to Savant.Chat.

## Features

- Identifies changed Solidity files between two commits
- Detects specific contracts and methods that have been modified
- Supports custom ignore patterns via `.savantignore` file
- Integration with Savant.chat

## Usage

### 1. Add the Workflow file

Create (or update) `.github/workflows/savant-smart-contract-analyzer.yml`

```yaml
name: Savant Smart Contract Analyzer
on:
  workflow_dispatch:
    inputs:
      base_commit:
        description: 'Base commit SHA for comparison'
        required: true
      head_commit:
        description: 'Head commit SHA for comparison'
        required: true
        default: 'HEAD'
      dry_run:
        description: 'Dry Run (only return estimates without creating request)'
        required: false
        default: 'false'
        type: boolean
      tier:
        description: 'Audit tier'
        required: false
        default: 'advanced'
        type: choice
        options:
          - advanced
          - lite
      project_id:
        description: 'Documentation project ID'
        required: false
        default: ''

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
        with:
          fetch-depth: 0
      
      - name: Analyze Solidity Changes & Send to Savant.Chat
        uses: auditdbio/savant-smart-contract-analyzer@v1.1
        with:
          base_commit: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.base_commit || github.event_name == 'push' && github.event.before || github.event.pull_request.base.sha }}
          head_commit: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.head_commit || github.event_name == 'push' && github.sha || github.event.pull_request.head.sha }}
          scopeignore_path: '.savantignore'
          api_token: ${{ secrets.SAVANT_API_TOKEN }}
          api_url: 'https://savant.chat/api/v1'
          dry_run: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.dry_run || 'false' }}
          tier: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.tier || 'advanced' }}
          project_id: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.project_id || '' }}

      - name: Upload Results
        uses: actions/upload-artifact@v4
        with:
          name: workflow-results
          path: workflow_results.json 
```

### 2. Set Up API Credentials

1. Go to [Savant.chat](https://savant.chat) and create an account.
2. Navigate to Dashboard → CI/CD → API Keys.
3. Create a new API key
4. Add the API key as a secret in your GitHub repository:
   - Go to repository Settings → Secrets and variables → Actions
   - Add a new secret named `SAVANT_API_TOKEN` containing your Savant API key.

### 3. Configure Triggers

- **Manual Run**  
  Use the _Actions_ tab → select **Savant Smart Contract Analyzer** → **Run workflow**, then fill in:
  - **base_commit**: SHA to compare from
  - **head_commit**: SHA to compare to (defaults to `HEAD`)
  - **dry_run**: `true`/`false` (skips request creation if true)
  - **tier**: `advanced` or `lite`
  - **project_id**: your documentation project identifier (optional)

- **Automatic Run**  
  Uncomment one of the trigger blocks in the YAML:
  ```yaml
  # pull_request:
  #   branches: [ master, main ]
  # push:
  #   branches: [ master, main ]
  ```
  Then commits or PRs on those branches will invoke the analyzer.

### 4. Customizing Ignored Files (Optional)

Create a `.savantignore` file in your repository to customize which files are ignored during analysis. The file follows a gitignore-like pattern format:

```
# Example .savantignore
node_modules/
[Tt]ests/
[Mm]ocks/
```

If no `.savantignore` file is present, the default patterns will be used:

- `node_modules/`
- `[Tt]ests/`, `[Tt]est/`, `*[Tt]est.sol`
- `[Mm]ocks/`, `[Mm]ock/`, `*[Mm]ock.sol`
- `[Ii]nterfaces/`, `[Ii]nterface/`, `*[Ii]nterface.sol`

---

## Action Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `base_commit` | Base commit SHA for comparison | Yes | - |
| `head_commit` | Head commit SHA for comparison | Yes | - |
| `scopeignore_path` | Path to `.savantignore` file | No | `.savantignore` |
| `api_token` | API token for the audit service | No | - |
| `api_url` | URL for the audit service API | No | `https://savant.chat/api/v1` |
| `dry_run` | Return estimates without creating request | No | `false` |
| `tier` | Tier | No | `advanced` |
| `project_id` | Documentation project ID | No | - |

## License

This project is licensed under the MIT License. 