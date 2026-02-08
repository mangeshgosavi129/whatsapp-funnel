import os
import ast

def get_definitions(file_path):
    definitions = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                # details = f"def {node.name}({', '.join(arg.arg for arg in node.args.args)})"
                details = f"def {node.name}"
                definitions.append(details)
            elif isinstance(node, ast.ClassDef):
                definitions.append(f"class {node.name}")
                for item in node.body:
                     if isinstance(item, ast.FunctionDef):
                        # definitions.append(f"  - def {item.name}")
                        pass # Keep it a bit cleaner, top-level only or it gets too huge? 
                        # User asked for "all files and functions in all files". 
                        # Let's include methods flattened or indented.
                        definitions.append(f"    - def {item.name}")
            elif isinstance(node, ast.AsyncFunctionDef):
                 definitions.append(f"async def {node.name}")

    except Exception as e:
        # print(f"Error parsing {file_path}: {e}")
        pass
    return definitions

def generate_tree(start_path, exclude_dirs=None):
    if exclude_dirs is None:
        exclude_dirs = ['.git', '__pycache__', 'venv', 'node_modules', '.idea', '.vscode', 'dist', 'build', 'coverage']
    
    output = []
    
    for root, dirs, files in os.walk(start_path):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        level = root.replace(start_path, '').count(os.sep)
        indent = '  ' * level
        dirname = os.path.basename(root)
        if dirname == '.': continue
        
        # Don't show the root folder name repeatedly, but do show subfolders
        if level > 0:
            output.append(f"{indent}- **{dirname}/**")
        
        sub_indent = '  ' * (level + 1)
        
        for f in sorted(files):
            if f.endswith('.pyc') or f == '__init__.py': continue # Skip init? maybe keep if important. Let's keep non-empty inits? 
            # Actually user wants "all files", let's keep everything but pyc.
            
            file_path = os.path.join(root, f)
            output.append(f"{sub_indent}- `{f}`")
            
            if f.endswith('.py'):
                defs = get_definitions(file_path)
                for d in defs:
                    output.append(f"{sub_indent}  - *{d}*")

    return "\n".join(output)

if __name__ == "__main__":
    base_dir = os.getcwd()
    # We focus on the main Backend/Worker logic folders
    target_dirs = ['server', 'llm', 'whatsapp_worker', 'whatsapp_receive']
    
    output_content = ["## Detailed Project Structure\n"]
    
    for d in target_dirs:
        full_path = os.path.join(base_dir, d)
        if os.path.exists(full_path):
            output_content.append(f"- **{d}/**")
            output_content.append(generate_tree(full_path))
            
    with open('project_structure.md', 'w', encoding='utf-8') as f:
        f.write("\n".join(output_content))
    print("Project structure written to project_structure.md")
