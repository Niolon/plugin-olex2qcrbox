"""Olex2 GUI interaction facade - centralizes all GUI operations."""

from olexFunctions import OlexFunctions
import olx

from .html_templates import (
    generate_run_button_html,
    generate_help_file_html,
    generate_help_content_html
)

OV = OlexFunctions()


def get_olex2_colors() -> dict:
    """Get Olex2 color scheme from settings.
    
    Returns:
        Dictionary of color values with keys: bg_color, font_color, 
        table_bg, highlight, link_color, font_name, error_color, secondary_color
    """
    try:
        return {
            'bg_color': olx.GetVar('HtmlBgColour', '#222222'),
            'font_color': olx.GetVar('HtmlFontColour', '#ffffff'),
            'table_bg': olx.GetVar('HtmlTableBgColour', '#222222'),
            'highlight': olx.GetVar('HtmlHighlightColour', '#ff8888'),
            'link_color': olx.GetVar('HtmlLinkColour', '#ababff'),
            'font_name': olx.GetVar('HtmlFontName', 'Bahnschrift'),
            'error_color': _get_color_hex(OV.GetParam('gui.red', '#ff6666')),
            'secondary_color': _get_color_hex(OV.GetParam('gui.grey', '#aaaaaa')),
        }
    except Exception as e:
        print(f"Warning: Could not load Olex2 colors, using defaults: {e}")
        return _default_colors()


def _get_color_hex(color_value):
    """Extract hex color from Olex2 color object or string."""
    if hasattr(color_value, 'hexadecimal'):
        return color_value.hexadecimal
    return str(color_value)


def _default_colors() -> dict:
    """Get default color scheme."""
    return {
        'bg_color': '#222222',
        'font_color': '#ffffff',
        'table_bg': '#222222',
        'highlight': '#ff8888',
        'link_color': '#ababff',
        'font_name': 'Bahnschrift',
        'error_color': '#ff6666',
        'secondary_color': '#aaaaaa',
    }


def update_run_button(text: str, color: str, enabled: bool):
    """Update the run button appearance.
    
    Args:
        text: Button text
        color: Background color (hex)
        enabled: Whether button is enabled
    """
    try:
        button_html = generate_run_button_html(text, color, enabled)
        OV.write_to_olex("qcb-run-button.htm", button_html)
        print(f"[GUI] Button updated: '{text}' (color: {color}, enabled: {enabled})")
    except Exception as e:
        print(f"[GUI] Failed to update button HTML: {e}")


def update_parameter_panel(html_content: str):
    """Update the parameter panel content.
    
    Args:
        html_content: HTML content for parameters
    """
    try:
        OV.write_to_olex("qcb-parameters.htm", html_content)
        print(f"[GUI] Parameter panel updated")
    except Exception as e:
        print(f"[GUI] Failed to update parameter panel: {e}")


def update_help_file(qcrbox_available: bool, applications: list, 
                    commands: list, selected_command: str = None):
    """Generate and update the help file.
    
    Args:
        qcrbox_available: Whether QCrBox server is accessible
        applications: List of application objects
        commands: List of command objects
        selected_command: Currently selected command name
    """
    try:
        colors = get_olex2_colors()
        
        help_content = generate_help_content_html(
            qcrbox_available=qcrbox_available,
            applications=applications,
            commands=commands,
            selected_command=selected_command,
            colors=colors
        )
        
        help_html = generate_help_file_html(help_content, colors)
        
        # Register help content as Olex2 variable
        olx.SetVar('qcrbox_command_help', help_html)
        print(f"[GUI] Help content updated (length: {len(help_html)})")
        
    except Exception as e:
        print(f"[GUI] Failed to update help file: {e}")
        import traceback
        traceback.print_exc()


def clear_parameter_panel():
    """Clear the parameter panel."""
    update_parameter_panel("")


def open_file_in_olex2(file_path: str):
    """Open a file in Olex2.
    
    Args:
        file_path: Path to file to open
    """
    try:
        olx.Atreap(file_path)
        print(f"[GUI] Opened file in Olex2: {file_path}")
    except Exception as e:
        print(f"[GUI] Failed to open file in Olex2: {e}")
