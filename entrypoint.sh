#!/bin/sh -l

# Get values from GitHub Actions environment variables
BASE_COMMIT=${INPUT_BASE_COMMIT}
HEAD_COMMIT=${INPUT_HEAD_COMMIT}

# Debug output
echo "Base commit: $BASE_COMMIT"
echo "Head commit: $HEAD_COMMIT"
echo "Working directory: $(pwd)"

# Run analyzer
python /change_analyzer.py "$BASE_COMMIT" "$HEAD_COMMIT"

# Check execution status
if [ $? -eq 0 ]; then
  echo "Analysis completed successfully!"
else
  echo "Error during analysis execution!"
  exit 1
fi 