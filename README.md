# Smart Contract Change Analyzer

This GitHub Action analyzes Solidity smart contract changes between commits to identify which contracts and methods have been modified. It helps in tracking the scope of changes for security reviews and audits.

## Features

- Identifies changed Solidity files between two commits
- Detects specific contracts and methods that have been modified
- Supports custom ignore patterns via `.scopeignore` file
- Integration with Savant.chat audit service to submit changes for professional review

## Usage

Add this GitHub Action to your workflow to analyze changes in Solidity files. You can trigger it manually or automatically with pull requests.

### Manual Trigger Example

```yaml
name: Smart Contract Change Analyzer
on:
  # Manual trigger with inputs
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
        uses: samartsevigor/change-analyzer@v2
        with:
          base_commit: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.base_commit || github.event_name == 'push' && github.event.before || github.event.pull_request.base.sha }}
          head_commit: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.head_commit || github.event_name == 'push' && github.sha || github.event.pull_request.head.sha }}
          scopeignore_path: '.scopeignore'  # Optional, defaults to '.scopeignore'
          api_token: ${{ secrets.SAVANT_API_TOKEN }}  # API token for the audit service
          api_url: 'https://savant.chat/api/v1/requests/create'
          dry_run: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.dry_run || 'false' }}
          tier: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.tier || 'advanced' }}
          project_id: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.project_id || '' }}
```

## How to Trigger Manually

To run the analysis manually:

1. Go to your repository on GitHub
2. Navigate to the "Actions" tab
3. Select the "Smart Contract Change Analyzer" workflow from the left sidebar
4. Click the "Run workflow" button
5. Enter the base commit SHA and head commit SHA
6. Optionally, enable "Dry Run"
7. Select audit tier.
8. Optionally, add documentation project ID.
9. Click "Run workflow"

## Savant.Chat AI Audit Service Integration

1. Go to [Savant.chat](https://savant.chat) and create an account
2. Navigate to Dashboard → Settings → API Keys
3. Create a new API key
4. Add the API key as a secret in your GitHub repository:
   - Go to repository Settings → Secrets and variables → Actions
   - Create a new secret named `SAVANT_API_TOKEN` with your API key
5. Optionally, add documentation project ID from CI/CD.

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `base_commit` | Base commit SHA for comparison | Yes | - |
| `head_commit` | Head commit SHA for comparison | Yes | - |
| `scopeignore_path` | Path to `.scopeignore` file | No | `.scopeignore` |
| `api_token` | API token for the audit service | No | - |
| `api_url` | URL for the audit service API | No | `https://savant.chat/api/v1/requests/create` |
| `dry_run` | Return estimates without creating request | No | `false` |
| `tier` | Tier | No | `advanced` |
| `project_id` | Documentation project ID | No | - |

## Customizing Ignored Files

Create a `.scopeignore` file in your repository to customize which files are ignored during analysis. The file follows a gitignore-like pattern format:

```
# Example .scopeignore
node_modules/
[Tt]ests/
[Mm]ocks/
```

If no `.scopeignore` file is present, the default patterns will be used:

- `node_modules/`
- `[Tt]ests/`, `[Tt]est/`, `*[Tt]est.sol`
- `[Mm]ocks/`, `[Mm]ock/`, `*[Mm]ock.sol`
- `[Ii]nterfaces/`, `[Ii]nterface/`, `*[Ii]nterface.sol`

## License

This project is licensed under the MIT License. 