"""CIF file utilities - pure functions with no external dependencies."""

import re


def convert_cif_ddl2_to_ddl1(cif_text: str) -> str:
    """Convert CIF data names from DDL2 format (dots) to DDL1 format (underscores).
    
    Converts entries like _cell.length_a to _cell_length_a while preserving
    numeric values (12.3), string values, and multiline strings.
    Only converts dots within CIF data names (starting with _ at line beginning).
    
    Args:
        cif_text: The CIF file content as a string
        
    Returns:
        Modified CIF text with DDL1 format data names
        
    Example:
        >>> cif = "_cell.length_a 10.5\\n_atom.label C1"
        >>> convert_cif_ddl2_to_ddl1(cif)
        "_cell_length_a 10.5\\n_atom_label C1"
    """
    lines = cif_text.split('\n')
    result_lines = []
    in_multiline_string = False
    
    # Pattern to match CIF data names: optional whitespace, underscore, then name with dots
    # Captures the full data name including dots
    data_name_pattern = re.compile(r'^(\s*)(_[a-zA-Z0-9_.\-]+)')
    
    for line in lines:
        # Check for multiline string delimiters (semicolon at start of line)
        if line.startswith(';'):
            in_multiline_string = not in_multiline_string
            result_lines.append(line)
            continue
        
        # If inside a multiline string, don't modify
        if in_multiline_string:
            result_lines.append(line)
            continue
        
        # Check if line starts with a CIF data name
        match = data_name_pattern.match(line)
        if match:
            # Extract the whitespace prefix and the data name
            whitespace = match.group(1)
            data_name = match.group(2)
            rest_of_line = line[match.end():]
            
            # Convert dots to underscores in the data name only
            converted_name = data_name.replace('.', '_')
            
            # Reconstruct the line
            result_lines.append(whitespace + converted_name + rest_of_line)
        else:
            # No data name at start of line, keep as is
            result_lines.append(line)
    
    return '\n'.join(result_lines)


def extract_cif_from_json_response(json_data: dict) -> str | None:
    """Extract CIF content from a QCrBox JSON response.
    
    Args:
        json_data: Parsed JSON response from QCrBox dataset download
        
    Returns:
        CIF file content as string, or None if not found
    """
    try:
        if 'payload' in json_data and 'datasets' in json_data['payload']:
            dataset = json_data['payload']['datasets'][0]
            if 'data_files' in dataset:
                # Find CIF file in data_files
                for filename, file_info in dataset['data_files'].items():
                    if filename.endswith('.cif'):
                        if 'content' in file_info:
                            return file_info['content']
        return None
    except (KeyError, IndexError, TypeError):
        return None


def validate_cif_data_name(name: str) -> bool:
    """Check if a string is a valid CIF data name.
    
    Args:
        name: String to validate
        
    Returns:
        True if valid CIF data name format
    """
    if not name or not name.startswith('_'):
        return False
    # CIF data names: underscore followed by alphanumeric, dots, underscores, hyphens
    return bool(re.match(r'^_[a-zA-Z0-9_.\-]+$', name))
