#!/bin/sh -l

# Get values from GitHub Actions environment variables
BASE_COMMIT=${INPUT_BASE_COMMIT}
HEAD_COMMIT=${INPUT_HEAD_COMMIT}
GITHUB_REPO=${GITHUB_REPOSITORY}
GITHUB_TOKEN=${INPUT_GITHUB_TOKEN}
SCOPEIGNORE_PATH=${INPUT_SCOPEIGNORE_PATH:-".savantignore"}
API_TOKEN=${INPUT_API_TOKEN}
API_URL=${INPUT_API_URL:-"https://savant.chat/api/v1"}
DRY_RUN=${INPUT_DRY_RUN:-"false"}
TIER=${INPUT_TIER:-"advanced"}
PROJECT_ID=${INPUT_PROJECT_ID:-""}

# Debug output
echo "Base commit: $BASE_COMMIT"
echo "Head commit: $HEAD_COMMIT"
echo "Working directory: $(pwd)"
echo "GitHub repository: $GITHUB_REPO"
echo "Scopeignore path: $SCOPEIGNORE_PATH"
echo "Dry run: $DRY_RUN"
echo "Tier: $TIER"
echo "Project ID: $PROJECT_ID"
echo "API URL: $API_URL"

# Ensure we're in the workspace
cd /github/workspace

# Display repository info
echo "Repository contents:"
ls -la
git status || echo "Git repository not initialized properly"

# Display git config
git config --list || echo "Git not configured"

# Configure git if working with remote
git config --global --add safe.directory /github/workspace

# Check if .savantignore exists
if [ -f "$SCOPEIGNORE_PATH" ]; then
  echo "Found .savantignore file at $SCOPEIGNORE_PATH:"
  cat "$SCOPEIGNORE_PATH"
else
  echo "No .savantignore file found at $SCOPEIGNORE_PATH, will use default patterns"
fi

# Run analyzer with proper workspace path and .savantignore path
python /change_analyzer.py "$BASE_COMMIT" "$HEAD_COMMIT" "/github/workspace" "$SCOPEIGNORE_PATH" "$API_TOKEN" "$API_URL" "$DRY_RUN" "$TIER" "$PROJECT_ID"

# Check execution status
if [ $? -eq 0 ]; then
  echo "Analysis completed successfully!"
else
  echo "Error during analysis execution!"
  exit 1
fi 