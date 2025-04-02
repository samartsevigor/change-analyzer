import subprocess
import json
from pathlib import Path
from typing import List, Set, Tuple, Dict, Optional
import pathspec
import tree_sitter
import tree_sitter_solidity
import difflib

# Initialize language and parser
SOLIDITY_LANGUAGE = tree_sitter.Language(tree_sitter_solidity.language(), "solidity")
PARSER = tree_sitter.Parser()
PARSER.set_language(SOLIDITY_LANGUAGE)

def read_ignore_patterns(project_root: Path, scopeignore_path: str = ".scopeignore") -> pathspec.PathSpec:
    """Reads ignore patterns from .scopeignore and adds default ones."""
    default_patterns = ["node_modules/", "[Tt]ests/", "[Tt]est/", "[Mm]ocks/", "[Mm]ock/", "[Ii]nterfaces/", "[Ii]nterface/", "*[Ii]nterface.sol", "*[Tt]est.sol", "*[Mm]ock.sol"]
    ignore_file = project_root / scopeignore_path
    patterns = []
    
    if ignore_file.exists():
        patterns.extend(["node_modules/"])
        with ignore_file.open("r") as f:
            patterns.extend(line.strip() for line in f if line.strip() and not line.startswith("#"))
        print(f"Using custom ignore patterns from {scopeignore_path}")
    else:
        patterns = default_patterns.copy()
        print(f"Using default ignore patterns (no {scopeignore_path} found)")
    
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

def get_file_content_at_commit(commit: str, file_path: str, project_root: Path) -> bytes:
    """Gets file content at the specified commit."""
    cmd = ["git", "show", f"{commit}:{file_path}"]
    try:
        content = subprocess.check_output(cmd, cwd=project_root)
        print(f"Content of {file_path} at {commit[:8]}: {content[:100]}...")
        return content
    except subprocess.CalledProcessError:
        print(f"File {file_path} not found at commit {commit}")
        return b""

def get_file_content_at_head(head_commit: str, file_path: str, project_root: Path) -> bytes:
    """Gets file content at the target commit."""
    return get_file_content_at_commit(head_commit, file_path, project_root)

def get_file_content_at_base(base_commit: str, file_path: str, project_root: Path) -> bytes:
    """Gets file content at the base commit."""
    return get_file_content_at_commit(base_commit, file_path, project_root)

def parse_solidity_file(content: bytes) -> tree_sitter.Tree:
    """Parses Solidity file content into an AST."""
    return PARSER.parse(content)

def find_node_by_type(node: tree_sitter.Node, node_type: str) -> Optional[tree_sitter.Node]:
    """Finds the first child node of the specified type."""
    for child in node.children:
        if child.type == node_type:
            return child
    return None

def find_nodes_by_type(node: tree_sitter.Node, node_type: str) -> List[tree_sitter.Node]:
    """Finds all child nodes of the specified type."""
    result = []
    for child in node.children:
        if child.type == node_type:
            result.append(child)
    return result

def get_node_text(node: tree_sitter.Node, source_bytes: bytes) -> str:
    """Gets the text content of a node."""
    return source_bytes[node.start_byte:node.end_byte].decode("utf-8")

def get_node_name(node: tree_sitter.Node, source_bytes: bytes) -> Optional[str]:
    """Gets the name of a node (for contracts, functions, etc.)."""
    identifier = find_node_by_type(node, "identifier")
    if identifier:
        return get_node_text(identifier, source_bytes)
    
    # Special case for constructor
    if node.type == "function_definition":
        for child in node.children:
            if child.type == "constructor":
                return "$constructor"
    
    return None

def extract_contracts(tree: tree_sitter.Tree, source_bytes: bytes) -> List[Dict]:
    """Extracts all contracts, libraries, and interfaces from the AST."""
    root = tree.root_node
    declarations = []
    
    for child in root.children:
        decl_type = child.type
        if decl_type in ("contract_declaration", "library_declaration", "interface_declaration"):
            name = get_node_name(child, source_bytes)
            if name:
                contract_type = {
                    "contract_declaration": "contract",
                    "library_declaration": "library",
                    "interface_declaration": "interface"
                }[decl_type]
                
                # Extract methods
                methods = []
                body = find_node_by_type(child, "contract_body")
                if body:
                    for sub_child in body.children:
                        if sub_child.type in ("function_definition", "modifier_definition"):
                            method_name = get_node_name(sub_child, source_bytes)
                            if method_name:
                                methods.append({
                                    "name": method_name,
                                    "node": sub_child,
                                    "text": get_node_text(sub_child, source_bytes)
                                })
                
                declarations.append({
                    "name": name,
                    "type": contract_type,
                    "node": child,
                    "methods": methods
                })
    
    return declarations

def remove_comments_and_normalize(text: str) -> str:
    """Removes comments and normalizes whitespace in Solidity code."""
    lines = text.split("\n")
    result = []
    in_multiline_comment = False
    
    for line in lines:
        processed_line = ""
        i = 0
        while i < len(line):
            # If we're inside a multiline comment, look for its end
            if in_multiline_comment:
                end_index = line.find("*/", i)
                if end_index != -1:
                    # Found end of comment
                    in_multiline_comment = False
                    i = end_index + 2  # Skip */
                else:
                    # Comment continues to end of line
                    i = len(line)
            else:
                # Check for start of single-line comment
                single_comment_index = line.find("//", i)
                # Check for start of multi-line comment
                multi_comment_index = line.find("/*", i)
                
                # Determine which comes first
                if single_comment_index != -1 and (multi_comment_index == -1 or single_comment_index < multi_comment_index):
                    # Single-line comment
                    processed_line += line[i:single_comment_index]
                    break  # Rest of line is comment
                elif multi_comment_index != -1:
                    # Multi-line comment
                    processed_line += line[i:multi_comment_index]
                    in_multiline_comment = True
                    i = multi_comment_index + 2  # Skip /*
                    
                    # Check if the multi-line comment ends on the same line
                    end_index = line.find("*/", i)
                    if end_index != -1:
                        in_multiline_comment = False
                        i = end_index + 2  # Skip */
                    else:
                        # Comment continues to end of line
                        i = len(line)
                else:
                    # No comments in the rest of the line
                    processed_line += line[i:]
                    break
        
        # Add the processed line if it's not empty
        if processed_line.strip():
            result.append(processed_line.strip())
    
    return " ".join(result)

def compare_methods(old_method: Dict, new_method: Dict) -> bool:
    """Compares two methods to determine if they are functionally different."""
    # Normalize whitespace and comments
    old_text = old_method["text"].strip()
    new_text = new_method["text"].strip()
    
    # Remove comments and normalize whitespace
    old_text = remove_comments_and_normalize(old_text)
    new_text = remove_comments_and_normalize(new_text)
    
    # Compare normalized texts
    return old_text != new_text

def find_changed_methods(base_tree: tree_sitter.Tree, head_tree: tree_sitter.Tree, 
                         base_content: bytes, head_content: bytes) -> List[Dict]:
    """Finds methods that have been changed between the base and head commits."""
    base_contracts = extract_contracts(base_tree, base_content)
    head_contracts = extract_contracts(head_tree, head_content)
    
    changed_methods = []
    
    # Create maps for easy lookup
    base_contract_map = {contract["name"]: contract for contract in base_contracts}
    head_contract_map = {contract["name"]: contract for contract in head_contracts}
    
    # Check for modified contracts
    for contract_name, head_contract in head_contract_map.items():
        if contract_name in base_contract_map:
            base_contract = base_contract_map[contract_name]
            
            # Create maps for methods
            base_method_map = {method["name"]: method for method in base_contract["methods"]}
            head_method_map = {method["name"]: method for method in head_contract["methods"]}
            
            # Check for modified methods
            for method_name, head_method in head_method_map.items():
                if method_name in base_method_map:
                    base_method = base_method_map[method_name]
                    if compare_methods(base_method, head_method):
                        changed_methods.append({
                            "contract": contract_name,
                            "contract_type": head_contract["type"],
                            "method": method_name
                        })
                else:
                    # New method
                    changed_methods.append({
                        "contract": contract_name,
                        "contract_type": head_contract["type"],
                        "method": method_name,
                        "status": "added"
                    })
            
            # Check for deleted methods
            for method_name in base_method_map:
                if method_name not in head_method_map:
                    changed_methods.append({
                        "contract": contract_name,
                        "contract_type": base_contract["type"],
                        "method": method_name,
                        "status": "deleted"
                    })
        else:
            # New contract - all methods are new
            for method in head_contract["methods"]:
                changed_methods.append({
                    "contract": contract_name,
                    "contract_type": head_contract["type"],
                    "method": method["name"],
                    "status": "added"
                })
    
    # Check for deleted contracts
    for contract_name in base_contract_map:
        if contract_name not in head_contract_map:
            base_contract = base_contract_map[contract_name]
            for method in base_contract["methods"]:
                changed_methods.append({
                    "contract": contract_name,
                    "contract_type": base_contract["type"],
                    "method": method["name"],
                    "status": "deleted"
                })
    
    return changed_methods

def analyze_changes(base_commit: str, head_commit: str, project_root: str = ".", scopeignore_path: str = ".scopeignore") -> List[Dict]:
    """Analyzes changes between commits and returns a list of change objects."""
    project_root = Path(project_root).resolve()
    ignore_spec = read_ignore_patterns(project_root, scopeignore_path)
    changed_files = get_changed_files(base_commit, head_commit, project_root)
    
    result = []
    
    for status, file_path in changed_files:
        match = ignore_spec.match_file(file_path)
        print(f"Checking {file_path}: ignored={match}")
        if match:
            print(f"Ignored file: {file_path}")
            continue
        
        print(f"Processing file: {file_path} (status: {status})")
        
        # Get file content at both commits
        head_content = get_file_content_at_head(head_commit, file_path, project_root)
        
        if status == "A":
            # New file - all contracts and methods are new
            head_tree = parse_solidity_file(head_content)
            head_contracts = extract_contracts(head_tree, head_content)
            
            file_entry = {
                "file": file_path,
                "status": status,
                "contracts": []
            }
            
            for contract in head_contracts:
                contract_entry = {
                    "name": contract["name"],
                    "type": contract["type"],
                    "methods": [method["name"] for method in contract["methods"]]
                }
                file_entry["contracts"].append(contract_entry)
            
            result.append(file_entry)
            
        elif status == "M":
            # Modified file - compare ASTs to find changed methods
            base_content = get_file_content_at_base(base_commit, file_path, project_root)
            
            if not base_content:
                print(f"Warning: Could not get base content for {file_path}, skipping")
                continue
            
            base_tree = parse_solidity_file(base_content)
            head_tree = parse_solidity_file(head_content)
            
            changed_methods = find_changed_methods(base_tree, head_tree, base_content, head_content)
            
            # Group changes by contract
            contract_changes = {}
            for change in changed_methods:
                contract_name = change["contract"]
                if contract_name not in contract_changes:
                    contract_changes[contract_name] = {
                        "name": contract_name,
                        "type": change["contract_type"],
                        "methods": []
                    }
                
                # Only include methods that were modified (not added or deleted)
                if "status" not in change:
                    contract_changes[contract_name]["methods"].append(change["method"])
            
            file_entry = {
                "file": file_path,
                "status": status,
                "contracts": list(contract_changes.values())
            }
            
            if file_entry["contracts"]:
                result.append(file_entry)
    
    print(f"Final result: {json.dumps(result, indent=2)}")
    return result

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python change_analyzer.py <base_commit> <head_commit> [project_path] [scopeignore_path]")
        sys.exit(1)
    
    base_commit, head_commit = sys.argv[1], sys.argv[2]
    project_path = sys.argv[3] if len(sys.argv) > 3 else "."
    scopeignore_path = sys.argv[4] if len(sys.argv) > 4 else ".scopeignore"
    
    print(f"Analyzing changes between {base_commit} and {head_commit} in {project_path}")
    print(f"Using scopeignore from: {scopeignore_path}")
    result = analyze_changes(base_commit, head_commit, project_path, scopeignore_path)
    
    with open("changed_declarations.json", "w") as f:
        json.dump(result, f, indent=2)
    print("Analysis completed. Results written to changed_declarations.json")