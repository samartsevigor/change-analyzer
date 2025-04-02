# Solidity Change Analyzer

This GitHub Action analyzes Solidity smart contract changes between commits to identify which contracts and methods have been modified. It helps in tracking the scope of changes for security reviews and audits.

## Features

- Identifies changed Solidity files between two commits
- Detects specific contracts and methods that have been modified
- Supports custom ignore patterns via `.scopeignore` file
- Outputs a structured JSON file with changed declarations

## Usage

Add this GitHub Action to your workflow to analyze changes in Solidity files. You can trigger it manually or automatically with pull requests.

### Manual Trigger Example

```yaml
name: Solidity Change Analyzer
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

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
        with:
          fetch-depth: 0
          
      - name: Analyze Solidity Changes
        uses: samartsevigor/change-analyzer@v1.0.4
        with:
          # For manual trigger, use the provided inputs
          base_commit: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.base_commit || github.event.pull_request.base.sha }}
          head_commit: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.head_commit || github.event.pull_request.head.sha }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          scopeignore_path: '.scopeignore'  # Optional, defaults to '.scopeignore'
          
      - name: Upload Analysis Results
        uses: actions/upload-artifact@v4
        with:
          name: changed-declarations
          path: changed_declarations.json
```

## How to Trigger Manually

To run the analysis manually:

1. Go to your repository on GitHub
2. Navigate to the "Actions" tab
3. Select the "Solidity Change Analyzer" workflow from the left sidebar
4. Click the "Run workflow" button
5. Enter the base commit SHA and head commit SHA
6. Click "Run workflow"

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `base_commit` | Base commit SHA for comparison | Yes | - |
| `head_commit` | Head commit SHA for comparison | Yes | - |
| `github_token` | GitHub token for repository access | No | `${{ github.token }}` |
| `scopeignore_path` | Path to `.scopeignore` file | No | `.scopeignore` |

## Outputs

A JSON file (`changed_declarations.json`) containing the analysis results with the following structure:

```json
[
  {
    "file": "contracts/Token.sol",
    "status": "M",
    "contracts": [
      {
        "name": "Token",
        "type": "contract",
        "methods": ["transfer", "approve"]
      }
    ]
  }
]
```

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