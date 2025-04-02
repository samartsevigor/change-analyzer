# Solidity Change Analyzer

This GitHub Action analyzes Solidity smart contract changes between commits to identify which contracts and methods have been modified. It helps in tracking the scope of changes for security reviews and audits.

## Features

- Identifies changed Solidity files between two commits
- Detects specific contracts and methods that have been modified
- Supports custom ignore patterns via `.scopeignore` file
- Outputs a structured JSON file with changed declarations

## Usage

Add this GitHub Action to your workflow to analyze changes in Solidity files:

```yaml
name: Analyze Smart Contract Changes
on:
  pull_request:
    branches:
      - main
      - master

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
          base_commit: ${{ github.event.pull_request.base.sha }}
          head_commit: ${{ github.event.pull_request.head.sha }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          scopeignore_path: '.scopeignore'  # Optional, defaults to '.scopeignore'
          
      - name: Upload Analysis Results
        uses: actions/upload-artifact@v4
        with:
          name: changed-declarations
          path: changed_declarations.json
```

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