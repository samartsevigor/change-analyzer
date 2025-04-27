import subprocess
import json
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import pathspec
import tree_sitter
import tree_sitter_solidity
import zipfile
import os
import tempfile
import requests
import sys

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
        patterns.extend(["node_modules/", ".github/"])
        with ignore_file.open("r") as f:
            patterns.extend(line.strip() for line in f if line.strip() and not line.startswith("#"))
        print(f"Using custom ignore patterns from {scopeignore_path}")
    else:
        patterns = default_patterns.copy()
        print(f"Using default ignore patterns (no {scopeignore_path} found)")
    
    print(f"Ignore patterns: {patterns}")
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)

def get_changed_files(base_commit: str, head_commit: str, project_root: Path) -> List[Tuple[str, str]]:
    """Gets a list of changed Solidity and document files with their status."""
    cmd = ["git", "diff", "--name-status", base_commit, head_commit]
    output = subprocess.check_output(cmd, cwd=project_root).decode("utf-8")
    changed_files = []
    
    print(f"git diff output:\n{output}")
    for line in output.strip().split("\n"):
        if line:
            status, file_path = line.split(maxsplit=1)
            # Include Solidity and document files
            if status in ("A", "M") and file_path.lower().endswith((".sol", ".txt", ".md", ".pdf", ".tex", ".doc")):
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

def create_project_zip(project_root: Path, ignore_spec: pathspec.PathSpec = None) -> str:
    """Creates a zip file of the complete project, including all files."""
    print("Creating full repository ZIP archive for audit submission...")
    
    # Create a temporary directory for the zip file
    temp_dir = tempfile.mkdtemp()
    
    # Get repository name from environment variable first
    repo_name = None
    if os.environ.get('GITHUB_REPOSITORY'):
        # Extract repo name without owner
        repo_name = os.environ.get('GITHUB_REPOSITORY').split('/')[-1]
        print(f"Using repository name from GITHUB_REPOSITORY: {repo_name}")
    
    # If not set in environment, try to get from path
    if not repo_name:
        repo_name = os.path.basename(project_root)
        print(f"Using repository name from path: {repo_name}")
    
    # If still not valid, use default
    if not repo_name or repo_name == '.' or repo_name == 'workspace':
        repo_name = "solidity-project"
        print(f"Using default repository name: {repo_name}")
    
    zip_filename = f"{repo_name}.zip"
    zip_path = os.path.join(temp_dir, zip_filename)
    
    print(f"Creating ZIP archive for repository: {repo_name}")
    
    # List of standard directories to skip
    standard_skip_dirs = ['.git', '.github', 'node_modules']
    
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for root, dirs, files in os.walk(project_root):
            # Convert to relative paths
            rel_root = os.path.relpath(root, project_root)
            if rel_root == '.':
                rel_root = ''
            
            # Skip standard directories that shouldn't be included in the archive
            dirs[:] = [d for d in dirs if d not in standard_skip_dirs]
            
            # Add all files (no filtering by ignore spec)
            for file in files:
                rel_path = os.path.join(rel_root, file)
                zipf.write(os.path.join(root, file), rel_path)
    
    print(f"Full repository ZIP created at {zip_path} (including all files)")
    return zip_path

def send_to_audit_service(zip_path: str, code_entries: List[str], doc_files: List[str], api_token: str, api_url: str, dry_run: bool, tier: str, project_id: Optional[str] = None) -> Dict:
    """Sends the project ZIP and changed files to the audit service."""
    if not api_token:
        print("ERROR: API token is required to send the project to the audit service.")
        print("Please get an API token from https://savant.chat:")
        print("1. Login to your account")
        print("2. Go to Settings")
        print("3. Navigate to API Keys tab")
        print("4. Create a new API key")
        return {"error": "API token is required"}
    
    audit_api_url = f"{api_url}/ci-cd/requests"
    
    print(f"Sending project to audit service at {audit_api_url}...")
    
    # Prepare request data
    headers = {
        "Authorization": f"Bearer {api_token}"
    }
    
    # Log the entries we're going to analyze
    if code_entries:
        print("Code entries to be analyzed by audit service:")
        for idx, entry in enumerate(code_entries, 1):
            print(f"  {idx}. {entry}")
    if doc_files:
        print("Document files to be included in audit:")
        for idx, file in enumerate(doc_files, 1):
            print(f"  {idx}. {file}")

    # Prepare the params data
    params_data = {
        "ignoreLimits": False,
        "dryRun": dry_run,
        "tier": tier,
        "selectedFiles": {
            "code": code_entries
        }
    }
    # Include documents only if provided
    if doc_files:
        params_data["selectedFiles"]["documents"] = doc_files
    # Include documentation project ID if provided
    if project_id:
        params_data["projectId"] = project_id
    
    print(f"Selected files parameter: {json.dumps(params_data['selectedFiles'])}")
    
    # Get the zip filename from the path
    zip_filename = os.path.basename(zip_path)
    print(f"Using filename for upload: {zip_filename}")
    
    # Verify the ZIP file exists and is readable
    if not os.path.exists(zip_path):
        print(f"ERROR: ZIP file does not exist at {zip_path}")
        return {"error": "ZIP file does not exist"}
    
    # Get ZIP file size
    zip_size = os.path.getsize(zip_path)
    print(f"ZIP file size: {zip_size} bytes ({zip_size / (1024*1024):.2f} MB)")
    
    try:
        # Verify the contents of the ZIP file
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            zip_contents = zipf.namelist()
            print(f"ZIP contains {len(zip_contents)} files")
    except Exception as e:
        print(f"ERROR verifying ZIP contents: {str(e)}")
    
    # Create multipart form data
    files = {
        'file': (zip_filename, open(zip_path, 'rb'), 'application/zip'),
        'params': (None, json.dumps(params_data), 'application/json')
    }
    
    # Log request details
    print("Request details:")
    print(f"  URL: {audit_api_url}")
    print(f"  Headers: {json.dumps({key: '***' if key == 'Authorization' else value for key, value in headers.items()})}")
    print(f"  Files: {zip_filename} ({zip_size} bytes)")
    print(f"  Params: {json.dumps(params_data, indent=2)}")
    
    try:
        # Send the request with detailed logging
        print(f"Sending POST request to {audit_api_url} with file {zip_filename}")
        response = requests.post(audit_api_url, headers=headers, files=files)
        
        # Print response status and headers
        print(f"Response status code: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        
        # Try to get JSON response
        try:
            result = response.json()
            print(f"Response JSON: {json.dumps(result, indent=2)}")
            
            # Check for specific error conditions
            if 'error' in result:
                print(f"ERROR from audit service: {result['error']}")
                if result['error'] == 'No valid files selected':
                    print("The audit service couldn't find any valid Solidity files among the selected files")
            
            return result
        except json.JSONDecodeError:
            # If response is not JSON, print the text
            print(f"Response text (not JSON): {response.text[:500]}")
            return {"error": f"Invalid JSON response: {response.text[:200]}..."}
        
    except requests.exceptions.RequestException as e:
        print(f"ERROR sending project to audit service: {str(e)}")
        if hasattr(e, 'response') and e.response:
            try:
                print(f"Response status code: {e.response.status_code}")
                print(f"Response headers: {dict(e.response.headers)}")
                
                error_data = e.response.json()
                print(f"Server error: {json.dumps(error_data, indent=2)}")
                return error_data
            except (json.JSONDecodeError, AttributeError):
                if hasattr(e, 'response') and e.response and hasattr(e.response, 'text'):
                    print(f"Response text: {e.response.text[:500]}")
                return {"error": str(e)}
        return {"error": str(e)}
    finally:
        # Clean up the zip file
        try:
            os.remove(zip_path)
            os.rmdir(os.path.dirname(zip_path))
        except Exception as cleanup_error:
            print(f"WARNING: Failed to clean up temporary files: {str(cleanup_error)}")

def analyze_changes(base_commit: str, head_commit: str, project_root: str = ".", scopeignore_path: str = ".scopeignore",
                   api_token: str = None, api_url: str = None, dry_run: str = "false", tier: str = "advanced", project_id: Optional[str] = None) -> List[Dict]:
    """Analyzes changes between commits and returns a list of change objects."""
    project_root = Path(project_root).resolve()
    ignore_spec = read_ignore_patterns(project_root, scopeignore_path)
    changed_files = get_changed_files(base_commit, head_commit, project_root)
    
    result = []
    all_changed_file_paths = []
    
    for status, file_path in changed_files:
        match = ignore_spec.match_file(file_path)
        print(f"Checking {file_path}: ignored={match}")
        if match:
            print(f"Ignored file: {file_path}")
            continue
        
        all_changed_file_paths.append(file_path)
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
    
    # Send to audit service if there are changes
    if all_changed_file_paths:
        # Create a complete repository ZIP without filtering
        zip_path = create_project_zip(project_root)
        dry_run_flag = dry_run.lower() == "true"
        # Build lists for audit: method-level code entries, and documents only if project_id provided
        code_entries: List[str] = []
        # Compute document files only when project_id is set
        if project_id:
            raw_docs = [f for f in all_changed_file_paths if f.lower().endswith((".txt", ".md", ".pdf", ".tex", ".doc"))]
            # Fetch allowed document list for the project
            project_endpoint = f"{api_url}/projects/{project_id}"
            try:
                proj_resp = requests.get(project_endpoint, headers={"Authorization": f"Bearer {api_token}"})
                proj_resp.raise_for_status()
                allowed_docs = proj_resp.json().get("documents", []) or []
            except Exception as e:
                print(f"WARNING: Failed to fetch project documents: {e}")
                allowed_docs = []
            # Filter only allowed documents
            doc_files = [f for f in raw_docs if os.path.basename(f) in allowed_docs]
        else:
            doc_files = []
        # Iterate over analysis result to get changed methods
        for entry in result:
            file_path = entry["file"]
            for contract in entry.get("contracts", []):
                name = contract.get("name")
                for method in contract.get("methods", []):
                    code_entries.append(f"{file_path}:{name}.{method}")
        # Log summary
        print(f"Code entries for audit ({len(code_entries)}): {code_entries}")
        print(f"Document files for audit ({len(doc_files)}): {doc_files}")
        # Send detailed entries to audit service
        audit_result = send_to_audit_service(zip_path, code_entries, doc_files, api_token, api_url, dry_run_flag, tier, project_id)
        # Save requestLink to artifact file
        request_link = None
        if isinstance(audit_result, dict) and 'requestLink' in audit_result:
            request_link = audit_result['requestLink']
        # Write workflow_results.json even if request_link is None
        try:
            with open("workflow_results.json", "w") as f:
                json.dump({"requestLink": request_link}, f)
        except Exception as e:
            print(f"WARNING: Failed to write workflow_results.json: {e}")
        # Mask the link if present
        if request_link:
            print(f"::add-mask::{request_link}")
        # Fail workflow if audit returned an error
        if isinstance(audit_result, dict) and 'error' in audit_result:
            print(f"Audit service returned an error: {audit_result['error']}")
            sys.exit(1)
    
    return result

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python change_analyzer.py <base_commit> <head_commit> [project_path] [scopeignore_path] [api_token] [api_url] [dry_run] [tier] [project_id]")
        sys.exit(1)
    
    base_commit, head_commit = sys.argv[1], sys.argv[2]
    project_path = sys.argv[3] if len(sys.argv) > 3 else "."
    scopeignore_path = sys.argv[4] if len(sys.argv) > 4 else ".scopeignore"
    api_token = sys.argv[5] if len(sys.argv) > 5 else None
    api_url = sys.argv[6] if len(sys.argv) > 6 else "https://savant.chat/api/v1"
    dry_run = sys.argv[7] if len(sys.argv) > 7 else "false"
    tier = sys.argv[8] if len(sys.argv) > 8 else "advanced"
    project_id = sys.argv[9] if len(sys.argv) > 9 else None
    
    print(f"Analyzing changes between {base_commit} and {head_commit} in {project_path}")
    print(f"Using scopeignore from: {scopeignore_path}")
    
    # Ensure API token is provided
    if not api_token:
        print("ERROR: API token is required to send the project to the audit service.")
        print("Please get an API token from https://savant.chat:")
        print("1. Login to your account")
        print("2. Go to Settings")
        print("3. Navigate to API Keys tab")
        print("4. Create a new API key")
        sys.exit(1)
    print(f"Will send changes to audit service at {api_url} (dry run: {dry_run})")
    
    analyze_changes(base_commit, head_commit, project_path, scopeignore_path, api_token, api_url, dry_run, tier, project_id)