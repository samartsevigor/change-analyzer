import subprocess
import json
from pathlib import Path
from typing import List, Set, Tuple, Dict
import pathspec
import tree_sitter
import tree_sitter_solidity

# Initialize language and parser
SOLIDITY_LANGUAGE = tree_sitter.Language(tree_sitter_solidity.language(), "solidity")
PARSER = tree_sitter.Parser()
PARSER.set_language(SOLIDITY_LANGUAGE)

def read_ignore_patterns(project_root: Path) -> pathspec.PathSpec:
    """Reads ignore patterns from .scopeignore and adds default ones."""
    default_patterns = ["node_modules/", "[Tt]ests/", "[Tt]est/", "[Mm]ocks/", "[Mm]ock/", "[Ii]nterfaces/", "[Ii]nterface/", "*[Ii]nterface.sol"]
    ignore_file = project_root / ".scopeignore"
    patterns = []
    
    if ignore_file.exists():
        patterns.extend(["node_modules/"])
        with ignore_file.open("r") as f:
            patterns.extend(line.strip() for line in f if line.strip() and not line.startswith("#"))
    else:
        patterns = default_patterns.copy()
    
    print(f"Ignore patterns: {patterns}")
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)

def get_changed_files(base_commit: str, head_commit: str, project_root: Path) -> List[Tuple[str, str]]:
    """Gets a list of changed .sol files with their status."""
    cmd = ["git", "diff", "--name-status", base_commit, head_commit]
    output = subprocess.check_output(cmd, cwd=project_root).decode("utf-8")
    changed_files = []
    
    print(f"git diff output:\n{output}")
    for line in output.strip().split("\n"):
        if line:
            status, file_path = line.split(maxsplit=1)
            if file_path.endswith(".sol") and status in ("A", "M"):
                changed_files.append((status, file_path))
    
    print(f"Changed files: {changed_files}")
    return changed_files

def get_file_content_at_head(head_commit: str, file_path: str, project_root: Path) -> bytes:
    """Gets file content at the target commit."""
    cmd = ["git", "show", f"{head_commit}:{file_path}"]
    content = subprocess.check_output(cmd, cwd=project_root)
    print(f"Content of {file_path} at {head_commit[:8]}: {content[:100]}...")
    return content

def get_changed_lines(base_commit: str, head_commit: str, file_path: str, project_root: Path) -> Set[int]:
    """Finds line numbers that were changed in the new file."""
    cmd = ["git", "diff", base_commit, head_commit, "--", file_path]
    diff_output = subprocess.check_output(cmd, cwd=project_root).decode("utf-8")
    changed_lines = set()
    current_line = None
    
    print(f"Diff for {file_path}:\n{diff_output}")
    for line in diff_output.splitlines():
        if line.startswith("@@"):
            parts = line.split()
            new_range = parts[2]  # example: +12,4
            start = int(new_range.split(",")[0][1:])
            current_line = start
        elif line.startswith("+") and current_line is not None and not line.startswith("+++"):
            changed_lines.add(current_line)
            current_line += 1
        elif line.startswith(" ") and current_line is not None:
            current_line += 1
    
    print(f"Changed lines for {file_path}: {changed_lines}")
    return changed_lines

def get_line_starts(source_bytes: bytes) -> List[int]:
    """Calculates byte offsets for the start of each line."""
    line_starts = [0]
    for i, b in enumerate(source_bytes):
        if b == ord("\n"):
            line_starts.append(i + 1)
    return line_starts

def byte_to_line(line_starts: List[int], byte_offset: int) -> int:
    """Converts byte offset to line number (1-based)."""
    import bisect
    line = bisect.bisect_right(line_starts, byte_offset)
    return line

def get_line_range(line_starts: List[int], start_byte: int, end_byte: int) -> Tuple[int, int]:
    """Converts byte range to line range."""
    start_line = byte_to_line(line_starts, start_byte)
    end_line = byte_to_line(line_starts, end_byte - 1) if end_byte > start_byte else start_line
    print(f"Line range for bytes {start_byte}-{end_byte}: {start_line}-{end_line}")
    return start_line, end_line

def overlaps(changed_lines: Set[int], start_line: int, end_line: int) -> bool:
    """Checks if changed lines overlap with the range."""
    result = any(line >= start_line and line <= end_line for line in changed_lines)
    print(f"Overlap check: changed_lines={changed_lines}, range={start_line}-{end_line}, result={result}")
    return result

def extract_declarations(source_bytes: bytes) -> List[Dict]:
    """Extracts declarations from Solidity file with types for top-level"""
    tree = PARSER.parse(source_bytes)
    root = tree.root_node
    declarations = []
    
    for child in root.children:
        decl_type = child.type
        if decl_type in ("contract_declaration", "library_declaration", "interface_declaration"):
            name_node = next((c for c in child.children if c.type == "identifier"), None)
            if name_node:
                name = source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8")
                start_byte = child.start_byte
                end_byte = child.end_byte
                sub_declarations = []
                
                body = next((c for c in child.children if c.type == "contract_body"), None)
                if body:
                    for sub_child in body.children:
                        if sub_child.type in ("function_definition", "modifier_definition"):
                            sub_name_node = next((c for c in sub_child.children if c.type == "identifier"), None)
                            if sub_name_node:
                                sub_name = source_bytes[sub_name_node.start_byte:sub_name_node.end_byte].decode("utf-8")
                            elif sub_child.type == "function_definition" and "constructor" in [c.type for c in sub_child.children]:
                                sub_name = "$constructor"
                            else:
                                continue
                            sub_declarations.append({
                                "name": sub_name,
                                "start_byte": sub_child.start_byte,
                                "end_byte": sub_child.end_byte
                            })
                
                declarations.append({
                    "name": name,
                    "type": {
                        "contract_declaration": "contract",
                        "library_declaration": "library",
                        "interface_declaration": "interface"
                    }[decl_type],
                    "start_byte": start_byte,
                    "end_byte": end_byte,
                    "sub_declarations": sub_declarations
                })
    
    print(f"Extracted declarations: {declarations}")
    return declarations

def analyze_changes(base_commit: str, head_commit: str, project_root: str = ".") -> List[Dict]:
    """Analyzes changes between commits and returns a list of change objects."""
    project_root = Path(project_root).resolve()
    ignore_spec = read_ignore_patterns(project_root)
    changed_files = get_changed_files(base_commit, head_commit, project_root)
    
    result = []
    
    for status, file_path in changed_files:
        match = ignore_spec.match_file(file_path)
        print(f"Checking {file_path}: ignored={match}")
        if match:
            print(f"Ignored file: {file_path}")
            continue
        
        print(f"Processing file: {file_path} (status: {status})")
        source_bytes = get_file_content_at_head(head_commit, file_path, project_root)
        declarations = extract_declarations(source_bytes)
        
        file_entry = {
            "file": file_path,
            "status": status,
            "contracts": []
        }
        
        for decl in declarations:
            contract_entry = {
                "name": decl["name"],
                "type": decl["type"],
                "methods": []
            }
            
            if status == "A":
                contract_entry["methods"] = [
                    sub_decl["name"]
                    for sub_decl in decl["sub_declarations"]
                ]
            elif status == "M":
                changed_lines = get_changed_lines(base_commit, head_commit, file_path, project_root)
                line_starts = get_line_starts(source_bytes)
                
                for sub_decl in decl["sub_declarations"]:
                    sub_start, sub_end = get_line_range(line_starts, sub_decl["start_byte"], sub_decl["end_byte"])
                    if overlaps(changed_lines, sub_start, sub_end):
                        contract_entry["methods"].append(sub_decl["name"])

            if contract_entry["methods"] or status == "A":
                file_entry["contracts"].append(contract_entry)
        
        if file_entry["contracts"]:
            result.append(file_entry)
    
    print(f"Final result: {json.dumps(result, indent=2)}")
    return result

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python change_analyzer.py <base_commit> <head_commit>")
        sys.exit(1)
    
    base_commit, head_commit = sys.argv[1], sys.argv[2]
    result = analyze_changes(base_commit, head_commit)
    
    with open("changed_declarations.json", "w") as f:
        json.dump(result, f, indent=2)
    print("Analysis completed. Results written to changed_declarations.json")