# Smart Contract Change Analyzer

This GitHub Action analyzes Solidity smart contract changes between commits to identify which contracts and methods have been modified. It helps in tracking the scope of changes for security reviews and audits.

## Features

- Identifies changed Solidity files between two commits
- Detects specific contracts and methods that have been modified
- Supports custom ignore patterns via `.scopeignore` file
- Outputs a structured JSON file with changed declarations
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
      send_to_audit:
        description: 'Send changes to audit service'
        required: false
        default: 'true'
        type: boolean

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
        with:
          fetch-depth: 0
          
      - name: Analyze Solidity Changes
        uses: samartsevigor/change-analyzer@v1.1.1
        with:
          base_commit: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.base_commit || github.event_name == 'push' && github.event.before || github.event.pull_request.base.sha }}
          head_commit: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.head_commit || github.event_name == 'push' && github.sha || github.event.pull_request.head.sha }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          scopeignore_path: '.scopeignore'  # Optional, defaults to '.scopeignore'
          api_token: ${{ secrets.AUDIT_API_TOKEN }}  # API token for the audit service
          api_url: 'https://savant.chat/api/v1/requests/create'
          send_to_audit: ${{ github.event.inputs.send_to_audit || 'true' }}
          
      - name: Upload Analysis Results
        uses: actions/upload-artifact@v4
        with:
          name: changed-declarations
          path: changed_declarations.json
          
      - name: Upload Audit Response
        if: ${{ github.event.inputs.send_to_audit == 'true' }}
        uses: actions/upload-artifact@v4
        with:
          name: audit-response
          path: audit_response.json
```

## How to Trigger Manually

To run the analysis manually:

1. Go to your repository on GitHub
2. Navigate to the "Actions" tab
3. Select the "Smart Contract Change Analyzer" workflow from the left sidebar
4. Click the "Run workflow" button
5. Enter the base commit SHA and head commit SHA
6. Optionally, enable "Send to audit service"
7. Click "Run workflow"

## AI Audit Service Integration

1. Go to [Savant.chat](https://savant.chat) and create an account
2. Navigate to Dashboard → Settings → API Keys
3. Create a new API key
4. Add the API key as a secret in your GitHub repository:
   - Go to repository Settings → Secrets and variables → Actions
   - Create a new secret named `AUDIT_API_TOKEN` with your API key
5. Enable the `send_to_audit` option when running the workflow

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `base_commit` | Base commit SHA for comparison | Yes | - |
| `head_commit` | Head commit SHA for comparison | Yes | - |
| `github_token` | GitHub token for repository access | No | `${{ github.token }}` |
| `scopeignore_path` | Path to `.scopeignore` file | No | `.scopeignore` |
| `api_token` | API token for the audit service | No* | - |
| `api_url` | URL for the audit service API | No | `https://savant.chat/api/v1/requests/create` |
| `send_to_audit` | Whether to send changes to the audit service | No | `true` |

\* Required if `send_to_audit` is set to `true`

## Outputs

### Analysis Results

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

### Audit Response

If `send_to_audit` is enabled, an additional JSON file (`audit_response.json`) will be generated with the audit service response:

```json
{
  "requestId": "generated_request_id",
  "estimates": [
    {
      "cost": "10.00",
      "filePath": "contracts/Token.sol",
      "complexity": "medium",
      "estimatedTime": "2 hours"
    }
  ],
  "status": "delayed"
}
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