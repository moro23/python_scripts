import os
import argparse
import fnmatch # For more advanced file pattern matching

# --- Default Configuration ---
DEFAULT_EXTENSIONS = [
    '.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.scss', '.md',
    '.json', '.yaml', '.yml', '.sh', '.txt', '.java', '.c', '.cpp', '.h',
    '.hpp', '.go', '.rb', '.php', '.sql', '.feature', '.env', '.dockerfile',
    'Dockerfile', '.conf', '.ini', '.toml', '.xml', '.rst', '.adoc'
]
DEFAULT_EXCLUDE_DIRS = [
    '.git', '.vscode', '.idea', 'venv', 'env', '.env', '__pycache__',
    'node_modules', 'dist', 'build', 'target', 'out', 'logs', 'coverage',
    '.pytest_cache', '.mypy_cache', '.tox', '.next', '.nuxt', '.cache',
    'public', 'static/admin' # Common static/build output dirs
]
DEFAULT_EXCLUDE_FILES = [
    '.DS_Store', '*.min.js', '*.min.css', '*.log', '*.lock', 'package-lock.json',
    'yarn.lock', 'poetry.lock', 'Pipfile.lock', 'composer.lock', '*.swp',
    '*.swo', '*.pyc', '*.pyo', '*.exe', '*.dll', '*.so', '*.o', '*.a',
    '*.class', '*.jar', '*.war', '*.ear', '*.zip', '*.tar.gz', '*.rar',
    '*.7z', '*.map' # Common compiled, lock, or archive files
]
MAX_FILE_SIZE_MB = 5  # Skip individual files larger than this (in MB)

def should_exclude_dir(dir_name, exclude_dirs):
    """Check if a directory name matches any of the exclusion patterns."""
    return dir_name in exclude_dirs

def should_exclude_file(file_name, exclude_files):
    """Check if a file name matches any of the exclusion patterns."""
    for pattern in exclude_files:
        if fnmatch.fnmatch(file_name, pattern):
            return True
    return False

def concatenate_project_files(project_dir, output_file,
                              extensions, exclude_dirs, exclude_files,
                              max_file_size, no_header, verbose):
    """
    Concatenates specified files from a project directory into a single output file.
    """
    if not os.path.isdir(project_dir):
        print(f"Error: Project directory '{project_dir}' not found or is not a directory.")
        return

    concatenated_content = []
    total_files_processed = 0
    total_files_included = 0
    total_bytes_included = 0

    if not no_header:
        concatenated_content.append(f"# Project: {os.path.abspath(project_dir)}\n")
        concatenated_content.append(f"# Concatenated Files Output\n")
        concatenated_content.append(f"# --------------------------------------------------\n\n")

    # Normalize exclude_dirs and exclude_files to ensure consistency
    exclude_dirs_set = set(exclude_dirs)
    exclude_files_patterns = list(exclude_files)

    for root, dirs, files in os.walk(project_dir, topdown=True):
        # Filter out excluded directories
        # Modify dirs in-place to prevent os.walk from traversing into them
        dirs[:] = [d for d in dirs if not should_exclude_dir(d, exclude_dirs_set)]

        relative_root = os.path.relpath(root, project_dir)
        if relative_root == ".": # Avoid "./" for top-level files
            relative_root = ""

        # Sort files for deterministic output (optional, but good for consistency)
        files.sort()

        for file_name in files:
            total_files_processed += 1
            file_path = os.path.join(root, file_name)
            relative_file_path = os.path.join(relative_root, file_name) if relative_root else file_name


            # 1. Check extension (case-insensitive for file_name part)
            # Handle files with no extension if they are explicitly in extensions (e.g. "Dockerfile")
            file_base, file_ext = os.path.splitext(file_name)
            if not (file_ext.lower() in extensions or file_name in extensions):
                if verbose:
                    print(f"Skipping (extension mismatch): {relative_file_path}")
                continue

            # 2. Check explicit file exclusions
            if should_exclude_file(file_name, exclude_files_patterns):
                if verbose:
                    print(f"Skipping (excluded file): {relative_file_path}")
                continue

            # 3. Check file size
            try:
                file_size_bytes = os.path.getsize(file_path)
                if file_size_bytes > max_file_size * 1024 * 1024:
                    if verbose:
                        print(f"Skipping (too large: {file_size_bytes / (1024*1024):.2f}MB): {relative_file_path}")
                    continue
                if file_size_bytes == 0: # Optionally skip empty files
                    if verbose:
                        print(f"Skipping (empty file): {relative_file_path}")
                    # continue # Uncomment to skip empty files
            except OSError as e:
                if verbose:
                    print(f"Skipping (cannot get size: {e}): {relative_file_path}")
                continue


            # 4. Try to read and append content
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                # Avoid adding empty files or files that became empty after 'errors=ignore'
                if not content.strip() and file_size_bytes > 0: # File had size but read as empty
                    if verbose:
                        print(f"Skipping (content became empty after decode): {relative_file_path}")
                    continue
                elif not content.strip() and file_size_bytes == 0: # Truly empty file already handled if skipping
                    pass


                concatenated_content.append(f"--- START FILE: {relative_file_path} ---\n")
                concatenated_content.append(content)
                concatenated_content.append(f"\n--- END FILE: {relative_file_path} ---\n\n")
                total_files_included += 1
                total_bytes_included += file_size_bytes
                if verbose:
                    print(f"Including: {relative_file_path} ({file_size_bytes / 1024:.2f} KB)")

            except UnicodeDecodeError as e:
                if verbose:
                    print(f"Skipping (UnicodeDecodeError: {e}): {relative_file_path}. Likely a binary file.")
            except Exception as e:
                if verbose:
                    print(f"Skipping (read error: {e}): {relative_file_path}")

    final_output_str = "".join(concatenated_content)

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(final_output_str)
        print(f"\nSuccessfully concatenated {total_files_included} files out of {total_files_processed} scanned.")
        print(f"Output written to: {os.path.abspath(output_file)}")
        output_size_mb = len(final_output_str.encode('utf-8')) / (1024 * 1024)
        # More accurate source file size sum:
        # source_size_mb = total_bytes_included / (1024 * 1024)
        # print(f"Total size of included source files: {source_size_mb:.2f} MB")
        print(f"Total output string size: {output_size_mb:.2f} MB")
        # Estimate token count (very rough estimate, assuming 1 token ~ 4 chars)
        estimated_tokens = len(final_output_str) / 4
        print(f"Estimated token count (rough): {int(estimated_tokens):,}")

        if output_size_mb > 2 or estimated_tokens > 200000 : # Common context window warning threshold
             print("Warning: The output is large. LLMs have context window limits. Consider refining your includes/excludes.")
             print("         For very large projects, consider processing specific subdirectories or features.")
    except IOError as e:
        print(f"Error: Could not write to output file '{output_file}'. Reason: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Concatenate project files into a single file for LLM input.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "project_dir",
        help="The root directory of the project to scan."
    )
    parser.add_argument(
        "output_file",
        help="The path to the output file where concatenated content will be saved."
    )
    parser.add_argument(
        "--extensions",
        nargs='*', # Changed from '+' to '*' to allow specifying no extensions (which is unlikely but possible)
        default=DEFAULT_EXTENSIONS,
        help="List of file extensions/names to include (e.g., .py .js Dockerfile)."
    )
    parser.add_argument(
        "--exclude-dirs",
        nargs='*',
        default=DEFAULT_EXCLUDE_DIRS,
        help="List of directory names to exclude."
    )
    parser.add_argument(
        "--exclude-files",
        nargs='*',
        default=DEFAULT_EXCLUDE_FILES,
        help="List of file names/patterns to exclude (supports wildcards like *.log)."
    )
    parser.add_argument(
        "--max-file-size",
        type=float,
        default=MAX_FILE_SIZE_MB,
        help="Maximum size (in MB) for individual files to be included."
    )
    parser.add_argument(
        "--no-header",
        action="store_true",
        help="Do not include the overall project header in the output."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print verbose output, showing which files are being skipped or included."
    )

    args = parser.parse_args()

    # Ensure extensions include the leading dot if not already present, unless it's a specific filename
    processed_extensions = []
    for ext in args.extensions:
        if '.' not in ext and ext: # e.g. "py" or "Dockerfile"
            if os.path.sep in ext or fnmatch.translate(ext) != ext: # if it looks like a path or pattern
                processed_extensions.append(ext)
            elif ext.islower() and len(ext) < 5: # likely an extension like "py"
                processed_extensions.append(f".{ext}")
            else: # likely a specific filename like "Dockerfile"
                processed_extensions.append(ext)
        else: # e.g., ".py"
            processed_extensions.append(ext)
    args.extensions = list(set(processed_extensions)) # Make unique

    if args.verbose:
        print("--- Configuration ---")
        print(f"Project Directory: {args.project_dir}")
        print(f"Output File: {args.output_file}")
        print(f"Included Extensions/Files: {args.extensions}")
        print(f"Excluded Directories: {args.exclude_dirs}")
        print(f"Excluded Files/Patterns: {args.exclude_files}")
        print(f"Max File Size: {args.max_file_size} MB")
        print(f"No Header: {args.no_header}")
        print("---------------------\n")


    concatenate_project_files(
        args.project_dir,
        args.output_file,
        args.extensions,
        args.exclude_dirs,
        args.exclude_files,
        args.max_file_size,
        args.no_header,
        args.verbose
    )

if __name__ == "__main__":
    main()