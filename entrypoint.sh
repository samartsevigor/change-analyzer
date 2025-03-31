#!/bin/sh -l

# Get values from GitHub Actions environment variables
BASE_COMMIT=${INPUT_BASE_COMMIT}
HEAD_COMMIT=${INPUT_HEAD_COMMIT}
GITHUB_REPO=${GITHUB_REPOSITORY}
GITHUB_TOKEN=${INPUT_GITHUB_TOKEN}

# Debug output
echo "Base commit: $BASE_COMMIT"
echo "Head commit: $HEAD_COMMIT"
echo "Working directory: $(pwd)"
echo "GitHub repository: $GITHUB_REPO"

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

# Run analyzer with proper workspace path
python /change_analyzer.py "$BASE_COMMIT" "$HEAD_COMMIT" "/github/workspace"

# Check execution status
if [ $? -eq 0 ]; then
  echo "Analysis completed successfully!"
else
  echo "Error during analysis execution!"
  exit 1
fi 