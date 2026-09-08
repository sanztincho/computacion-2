#!/usr/bin/env python3
"""
Mini-grep: A simplified version of the Unix grep command.
Searches for patterns in files or stdin with various options.
"""

import argparse
import sys
import re
from pathlib import Path
from typing import List, Tuple


def search_in_file(
    filepath: str,
    pattern: str,
    ignore_case: bool = False,
    show_line_numbers: bool = False,
    count_only: bool = False,
    invert: bool = False,
) -> Tuple[int, List[str]]:
    """
    Search for pattern in a file.
    
    Returns:
        Tuple of (match_count, lines_to_print)
    """
    flags = re.IGNORECASE if ignore_case else 0
    compiled_pattern = re.compile(pattern, flags)
    
    matches = 0
    output_lines = []
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                line_content = line.rstrip('\n')
                is_match = compiled_pattern.search(line_content) is not None
                
                # If invert is True, we want lines that DON'T match
                if invert:
                    is_match = not is_match
                
                if is_match:
                    matches += 1
                    if not count_only:
                        # Format output line
                        prefix = ""
                        if show_line_numbers:
                            prefix = f"{filepath}:{line_num}: "
                        else:
                            prefix = f"{filepath}: " if len(sys.argv) > 3 else ""
                        
                        output_lines.append(f"{prefix}{line_content}")
    
    except FileNotFoundError:
        print(f"Error: No se puede leer '{filepath}'", file=sys.stderr)
        return 0, []
    except Exception as e:
        print(f"Error al procesar '{filepath}': {e}", file=sys.stderr)
        return 0, []
    
    return matches, output_lines


def search_in_stdin(
    pattern: str,
    ignore_case: bool = False,
    show_line_numbers: bool = False,
    count_only: bool = False,
    invert: bool = False,
) -> Tuple[int, List[str]]:
    """
    Search for pattern in stdin.
    
    Returns:
        Tuple of (match_count, lines_to_print)
    """
    flags = re.IGNORECASE if ignore_case else 0
    compiled_pattern = re.compile(pattern, flags)
    
    matches = 0
    output_lines = []
    
    for line_num, line in enumerate(sys.stdin, 1):
        line_content = line.rstrip('\n')
        is_match = compiled_pattern.search(line_content) is not None
        
        # If invert is True, we want lines that DON'T match
        if invert:
            is_match = not is_match
        
        if is_match:
            matches += 1
            if not count_only:
                prefix = ""
                if show_line_numbers:
                    prefix = f"{line_num}: "
                
                output_lines.append(f"{prefix}{line_content}")
    
    return matches, output_lines


def main():
    parser = argparse.ArgumentParser(
        description='Mini-grep: Busca patrones en archivos (como el comando grep de Unix)',
        epilog='Si no se especifican archivos, lee de stdin'
    )
    
    parser.add_argument(
        'pattern',
        help='Patrón a buscar (puede ser una expresión regular)'
    )
    
    parser.add_argument(
        'archivos',
        nargs='*',
        help='Archivos en los que buscar (si no se especifica, lee de stdin)'
    )
    
    parser.add_argument(
        '-i', '--ignore-case',
        action='store_true',
        help='Búsqueda insensible a mayúsculas/minúsculas'
    )
    
    parser.add_argument(
        '-n', '--line-number',
        action='store_true',
        help='Mostrar número de línea'
    )
    
    parser.add_argument(
        '-c', '--count',
        action='store_true',
        help='Solo mostrar el conteo de coincidencias'
    )
    
    parser.add_argument(
        '-v', '--invert',
        action='store_true',
        help='Mostrar líneas que NO coinciden con el patrón'
    )
    
    args = parser.parse_args()
    
    # Determine if we should show line numbers by default
    # (activated by default if multiple files)
    show_line_numbers = args.line_number or (len(args.archivos) > 1)
    
    total_matches = 0
    total_files = 0
    
    # If no files specified, read from stdin
    if not args.archivos:
        if sys.stdin.isatty():
            print("Error: Debe especificar archivos o proporcionar entrada por stdin", 
                  file=sys.stderr)
            sys.exit(1)
        
        matches, output_lines = search_in_stdin(
            args.pattern,
            ignore_case=args.ignore_case,
            show_line_numbers=show_line_numbers,
            count_only=args.count,
            invert=args.invert
        )
        total_matches += matches
        
        if args.count:
            print(matches)
        else:
            for line in output_lines:
                print(line)
    
    else:
        # Search in specified files
        for filepath in args.archivos:
            # Expand wildcards if needed (this is handled by the shell in practice)
            path_obj = Path(filepath)
            
            # Check if it's a glob pattern (contains *, ?, etc.)
            if any(char in filepath for char in '*?[]'):
                # Handle glob pattern
                matching_files = list(Path('.').glob(filepath))
                if not matching_files:
                    print(f"Error: No se encontraron archivos que coincidan con '{filepath}'", 
                          file=sys.stderr)
                    continue
                files_to_search = [str(f) for f in matching_files]
            else:
                files_to_search = [filepath]
            
            for file_path in files_to_search:
                matches, output_lines = search_in_file(
                    file_path,
                    args.pattern,
                    ignore_case=args.ignore_case,
                    show_line_numbers=show_line_numbers,
                    count_only=args.count,
                    invert=args.invert
                )
                
                total_matches += matches
                total_files += 1
                
                if args.count:
                    print(f"{file_path}: {matches} coincidencias")
                else:
                    for line in output_lines:
                        print(line)
        
        # Print total count if --count option was used
        if args.count and total_files > 1:
            print(f"Total: {total_matches} coincidencias")


if __name__ == '__main__':
    main()
