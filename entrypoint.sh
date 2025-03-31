#!/bin/sh -l

# Get values from GitHub Actions environment variables
BASE_COMMIT=${INPUT_BASE_COMMIT}
HEAD_COMMIT=${INPUT_HEAD_COMMIT}
GITHUB_REPO=${GITHUB_REPOSITORY}
GITHUB_TOKEN=${INPUT_GITHUB_TOKEN}
SCOPEIGNORE_PATH=${INPUT_SCOPEIGNORE_PATH:-".scopeignore"}

# Debug output
echo "Base commit: $BASE_COMMIT"
echo "Head commit: $HEAD_COMMIT"
echo "Working directory: $(pwd)"
echo "GitHub repository: $GITHUB_REPO"
echo "Scopeignore path: $SCOPEIGNORE_PATH"

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

# Check if .scopeignore exists
if [ -f "$SCOPEIGNORE_PATH" ]; then
  echo "Found .scopeignore file at $SCOPEIGNORE_PATH:"
  cat "$SCOPEIGNORE_PATH"
else
  echo "No .scopeignore file found at $SCOPEIGNORE_PATH, will use default patterns"
fi

# Run analyzer with proper workspace path and scopeignore path
python /change_analyzer.py "$BASE_COMMIT" "$HEAD_COMMIT" "/github/workspace" "$SCOPEIGNORE_PATH"

# Check execution status
if [ $? -eq 0 ]; then
  echo "Analysis completed successfully!"
else
  echo "Error during analysis execution!"
  exit 1
fi 