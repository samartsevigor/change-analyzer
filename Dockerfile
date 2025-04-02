FROM python:3.9-slim

# Install Git and other dependencies
RUN apt-get update && \
    apt-get install -y git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pathspec tree-sitter==0.21.3 tree-sitter-solidity

COPY entrypoint.sh /entrypoint.sh
COPY change_analyzer.py /change_analyzer.py

RUN chmod +x /entrypoint.sh
RUN git config --global --add safe.directory /github/workspace

ENTRYPOINT ["/entrypoint.sh"] 