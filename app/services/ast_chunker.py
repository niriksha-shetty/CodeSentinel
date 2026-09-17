import ast
import re
from typing import List, Dict, Any, Tuple
from app.schemas import ASTChunk

def extract_added_code_from_diff(diff_content: str) -> Tuple[str, List[Tuple[int, str]]]:
    """
    Parses a unified diff string and reconstructs the 'new' version of the file
    along with line mapping of new line numbers.
    """
    lines = diff_content.splitlines()
    reconstructed_lines = []
    line_mappings = [] # list of (new_line_num, line_str)
    
    current_new_line = 1
    in_hunk = False

    for line in lines:
        if line.startswith('@@'):
            # Parse hunk header e.g. @@ -10,6 +15,8 @@
            match = re.search(r'\+(\d+)(?:,(\d+))?', line)
            if match:
                current_new_line = int(match.group(1))
                in_hunk = True
            continue
        
        if not in_hunk and not diff_content.startswith(('diff ', '--- ', '+++ ')):
            # Not a unified diff header, treat as raw code
            reconstructed_lines.append(line)
            line_mappings.append((len(reconstructed_lines), line))
            continue

        if line.startswith('-') and not line.startswith('---'):
            # Removed line in diff, ignore for new version AST
            continue
        elif line.startswith('+') and not line.startswith('+++'):
            # Added line
            code_line = line[1:] # strip '+'
            reconstructed_lines.append(code_line)
            line_mappings.append((current_new_line, code_line))
            current_new_line += 1
        elif line.startswith(' '):
            # Context line
            code_line = line[1:]
            reconstructed_lines.append(code_line)
            line_mappings.append((current_new_line, code_line))
            current_new_line += 1
        elif not in_hunk:
            # General line
            reconstructed_lines.append(line)
            line_mappings.append((len(reconstructed_lines), line))

    full_code = "\n".join(reconstructed_lines)
    return full_code, line_mappings


def chunk_code_by_ast(code_or_diff: str, filename: str = "code.py", max_chunk_lines: int = 150) -> List[ASTChunk]:
    """
    Custom code chunker that splits large diffs/files by Python function and class boundaries
    using AST node inspection rather than rigid line counts.
    
    Falls back to structural block chunking if AST parsing fails (e.g. non-Python or partial invalid syntax).
    """
    # First, extract clean code if passed a unified diff
    clean_code, _ = extract_added_code_from_diff(code_or_diff)
    if not clean_code.strip():
        clean_code = code_or_diff

    # Check if filename is python or code looks like python
    is_python = filename.endswith('.py') or 'def ' in clean_code or 'class ' in clean_code or 'import ' in clean_code

    if is_python:
        try:
            tree = ast.parse(clean_code, filename=filename)
            return _chunk_python_ast(tree, clean_code, max_chunk_lines)
        except Exception:
            # Fallback to structural block chunking if AST fails (e.g. syntax error in diff patch)
            pass

    return _chunk_structural_fallback(clean_code, max_chunk_lines)


def _chunk_python_ast(tree: ast.AST, code: str, max_chunk_lines: int) -> List[ASTChunk]:
    """Extracts top-level AST nodes (Classes, Functions) and module statements."""
    lines = code.splitlines()
    total_lines = len(lines)
    chunks: List[ASTChunk] = []

    # Track covered line numbers
    covered_lines = set()

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = getattr(node, 'lineno', 1)
            end = getattr(node, 'end_lineno', start)
            
            # Ensure line ranges are within bounds
            start = max(1, min(start, total_lines))
            end = max(start, min(end, total_lines))

            chunk_type = "function"
            if isinstance(node, ast.AsyncFunctionDef):
                chunk_type = "async_function"
            elif isinstance(node, ast.ClassDef):
                chunk_type = "class"

            chunk_code = "\n".join(lines[start - 1 : end])
            
            # Mark lines as covered
            for l in range(start, end + 1):
                covered_lines.add(l)

            # If class is very large, chunk its individual methods
            if chunk_type == "class" and (end - start + 1) > max_chunk_lines:
                method_chunks = _chunk_class_methods(node, lines, start, end)
                if method_chunks:
                    chunks.extend(method_chunks)
                    continue

            chunks.append(ASTChunk(
                chunk_type=chunk_type,
                name=getattr(node, 'name', 'anonymous'),
                start_line=start,
                end_line=end,
                code=chunk_code
            ))

    # Collect uncovered module-level statements (e.g., imports, global constants, setup code)
    uncovered_ranges = []
    current_start = None

    for i in range(1, total_lines + 1):
        if i not in covered_lines:
            if current_start is None:
                current_start = i
        else:
            if current_start is not None:
                uncovered_ranges.append((current_start, i - 1))
                current_start = None
    if current_start is not None:
        uncovered_ranges.append((current_start, total_lines))

    for start, end in uncovered_ranges:
        block_lines = lines[start - 1 : end]
        block_text = "\n".join(block_lines).strip()
        if block_text:  # Avoid empty whitespace chunks
            chunks.append(ASTChunk(
                chunk_type="module_level",
                name="module_globals",
                start_line=start,
                end_line=end,
                code="\n".join(block_lines)
            ))

    # Sort chunks by start line order
    chunks.sort(key=lambda c: c.start_line)
    return chunks if chunks else [_make_full_chunk(lines, "module_level")]


def _chunk_class_methods(class_node: ast.ClassDef, lines: List[str], class_start: int, class_end: int) -> List[ASTChunk]:
    """Splits an oversized class node into method-level chunks while retaining class signature."""
    chunks = []
    class_header = lines[class_start - 1] # e.g. class MyService:
    
    for item in class_node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            m_start = getattr(item, 'lineno', class_start)
            m_end = getattr(item, 'end_lineno', m_start)
            
            m_code = f"# Class Context: {class_header}\n" + "\n".join(lines[m_start - 1 : m_end])
            chunks.append(ASTChunk(
                chunk_type="class_method",
                name=f"{class_node.name}.{item.name}",
                start_line=m_start,
                end_line=m_end,
                code=m_code
            ))

    return chunks


def _chunk_structural_fallback(code: str, max_chunk_lines: int) -> List[ASTChunk]:
    """Fallback chunker for non-Python or syntax-invalid diff snippets using block boundaries."""
    lines = code.splitlines()
    if not lines:
        return [ASTChunk(chunk_type="raw_block", name="empty", start_line=1, end_line=1, code="")]

    chunks = []
    current_lines = []
    current_start = 1
    current_name = "block_1"
    block_counter = 1

    for idx, line in enumerate(lines, start=1):
        # Look for structural markers (e.g., def, class, function, struct, pub fn)
        is_boundary = bool(re.match(r'^(def |class |async def |function |pub fn |class\b)', line.strip()))
        
        if is_boundary and current_lines and (idx - current_start >= 10):
            chunks.append(ASTChunk(
                chunk_type="structural_block",
                name=current_name,
                start_line=current_start,
                end_line=idx - 1,
                code="\n".join(current_lines)
            ))
            current_lines = []
            current_start = idx
            block_counter += 1
            match = re.search(r'(?:def|class|function)\s+([a-zA-Z0-9_]+)', line)
            current_name = match.group(1) if match else f"block_{block_counter}"

        current_lines.append(line)

        if len(current_lines) >= max_chunk_lines:
            chunks.append(ASTChunk(
                chunk_type="structural_block",
                name=current_name,
                start_line=current_start,
                end_line=idx,
                code="\n".join(current_lines)
            ))
            current_lines = []
            current_start = idx + 1
            block_counter += 1
            current_name = f"block_{block_counter}"

    if current_lines:
        chunks.append(ASTChunk(
            chunk_type="structural_block",
            name=current_name,
            start_line=current_start,
            end_line=len(lines),
            code="\n".join(current_lines)
        ))

    return chunks


def _make_full_chunk(lines: List[str], chunk_type: str) -> ASTChunk:
    return ASTChunk(
        chunk_type=chunk_type,
        name="full_file",
        start_line=1,
        end_line=max(1, len(lines)),
        code="\n".join(lines)
    )
