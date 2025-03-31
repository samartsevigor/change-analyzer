FROM python:3.9-slim

RUN pip install --no-cache-dir pathspec tree-sitter==0.21.3 tree-sitter-solidity

COPY entrypoint.sh /entrypoint.sh
COPY change_analyzer.py /change_analyzer.py

RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"] 