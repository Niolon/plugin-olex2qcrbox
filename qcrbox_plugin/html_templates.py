"""HTML template generation for QCrBox parameter forms and help files."""

from textwrap import dedent


# Template for boolean parameters (checkbox)
BOOL_PARAMETER_TEMPLATE = dedent("""
  <td name="{parameter_name}:label" width="25%">
    <b>{parameter_name}</b>{required_marker}
  </td>
  <td name="{parameter_name}:control" width="75%" align='right'>
    <font size="$GetVar('HtmlFontSizeControls')">
    <input
      type="checkbox"
      name = "{parameter_name}"
      checked="spy.qcb.get_parameter_state({command_id}, '{parameter_name}')"
      onclick="spy.qcb.set_parameter_state({command_id}, '{parameter_name}', html.GetState('~name~'))"
    >
    </font>
  </td>
""")

# Template for string parameters (text input)
STRING_PARAMETER_TEMPLATE = dedent("""
  <td name="{parameter_name}:label" width="25%">
    <b>{parameter_name}</b>{required_marker}
  </td>
  <td name="{parameter_name}:control" width="75%">
    <font size="$GetVar('HtmlFontSizeControls')">
    <input
      type="text"
      width="100%"
      name="{parameter_name}"
      value="spy.qcb.get_parameter_state({command_id}, '{parameter_name}')"
      onchange="spy.qcb.set_parameter_state({command_id}, '{parameter_name}', html.GetValue('~name~'))"
    >
    </font>
  </td>
""")

# Template for number parameters (numeric input)
NUMBER_PARAMETER_TEMPLATE = dedent("""
  <td name="{parameter_name}:label" width="25%">
    <b>{parameter_name}</b>{required_marker}
  </td>
  <td name="{parameter_name}:control" width="75%">
    <font size="$GetVar('HtmlFontSizeControls')">
    <input
      type="text"
      width="100%"
      name="{parameter_name}"
      value="spy.qcb.get_parameter_state({command_id}, '{parameter_name}')"
      onchange="spy.qcb.set_parameter_state({command_id}, '{parameter_name}', html.GetValue('~name~'))"
    >
    </font>
  </td>
""")


def generate_bool_parameter(command_id: int, parameter_name: str, description: str = "", required: bool = False) -> str:
    """Generate HTML for a boolean parameter.
    
    Args:
        command_id: The command ID
        parameter_name: Name of the parameter
        description: Description text for the parameter (stored but not displayed)
        required: Whether the parameter is required
        
    Returns:
        HTML string for the parameter
    """
    required_marker = " *" if required else ""
    return BOOL_PARAMETER_TEMPLATE.format(
        command_id=command_id,
        parameter_name=parameter_name,
        required_marker=required_marker
    )


def generate_string_parameter(command_id: int, parameter_name: str, description: str = "", required: bool = False) -> str:
    """Generate HTML for a string parameter.
    
    Args:
        command_id: The command ID
        parameter_name: Name of the parameter
        description: Description text for the parameter
        required: Whether the parameter is required
        
    Returns:
        HTML string for the parameter
    """
    required_marker = " *" if required else ""
    return STRING_PARAMETER_TEMPLATE.format(
        command_id=command_id,
        parameter_name=parameter_name,
        description=description,
        required_marker=required_marker
    )


def generate_number_parameter(command_id: int, parameter_name: str, description: str = "", required: bool = False) -> str:
    """Generate HTML for a number parameter.
    
    Args:
        command_id: The command ID
        parameter_name: Name of the parameter
        description: Description text for the parameter
        required: Whether the parameter is required
        
    Returns:
        HTML string for the parameter
    """
    required_marker = " *" if required else ""
    return NUMBER_PARAMETER_TEMPLATE.format(
        command_id=command_id,
        parameter_name=parameter_name,
        description=description,
        required_marker=required_marker
    )


def generate_parameter_html(command_id: int, parameter_name: str, parameter_dtype: str, 
                           description: str = "", required: bool = False) -> str:
    """Generate HTML for any parameter type.
    
    Args:
        command_id: The command ID
        parameter_name: Name of the parameter
        parameter_dtype: Data type of the parameter (bool, str, int, float, QCrBox.*)
        description: Description text for the parameter
        required: Whether the parameter is required
        
    Returns:
        HTML string for the parameter
    """
    if parameter_dtype == "bool":
        return generate_bool_parameter(command_id, parameter_name, description)
    elif parameter_dtype in ["str", "QCrBox.cif_data_file", "QCrBox.output_cif", "QCrBox.data_file"]:
        return generate_string_parameter(command_id, parameter_name, description, required)
    elif parameter_dtype in ["int", "float"]:
        return generate_number_parameter(command_id, parameter_name, description, required)
    # Default to string input for unknown types
    return generate_string_parameter(command_id, parameter_name, description, required)


# ==================== Button Generation ====================

def generate_run_button_html(button_text: str, button_color: str, enabled: bool) -> str:
    """Generate HTML for the run/retrieve button.
    
    Args:
        button_text: Text to display on the button
        button_color: Background color for the button (hex color)
        enabled: Whether the button is enabled
        
    Returns:
        HTML string for the button
    """
    # Determine onclick action based on button text and enabled state
    if not enabled:
        onclick_action = "spy.qcb.still_running_calculation()"
    elif "Retrieve" in button_text:
        onclick_action = "spy.qcb.download_and_open_result()>>html.update()"
    else:
        onclick_action = "spy.qcb.run_current_cmd_with_pars()>>html.update()"
    
    enabled_str = "true" if enabled else "false"
    
    return dedent(f'''
      <!-- #include tool-row gui/blocks/tool-row.htm;1; -->
      <td width="100%">
        $+
        html.Snippet("gui/snippets/input-button",
          "name=QCB_RUN_BUTTON",
          "value={button_text}",
          "onclick={onclick_action}",
          "width=100%",
          "bgcolor={button_color}",
          "enabled={enabled_str}"
        )
        $-
      </td>
      <!-- #include row_table_off gui/blocks/row_table_off.htm;1; -->
    ''').strip()

def generate_help_file_html(help_content: str, colors: dict) -> str:
    """Wrap help content in Olex2 help file template structure.
    
    Args:
        help_content: HTML content to display in the help file body
        colors: Dictionary of Olex2 color settings
        
    Returns:
        Complete HTML string with Olex2 help template tags
    """
    return dedent(f'''
      <body link="{colors['link_color']}" bgcolor='{colors['bg_color']}'>
      <font size='3' color='{colors['font_color']}' face="{colors['font_name']}">
      <table bgcolor='{colors['table_bg']}' width='100%%' border='0' cellspacing='5' cellpadding='5'>
      <tr bgcolor='{colors['table_bg']}'>
      <td bgcolor='{colors['table_bg']}'>
      {help_content}
      </td>
      </tr>
      </table>
      </font>
      </body>
    ''')


def generate_help_content_html(
    qcrbox_available: bool,
    applications: list,
    commands: list,
    selected_command: str = None,
    colors: dict = None
) -> str:
    """Generate context-aware help content HTML based on current state.
    
    Args:
        qcrbox_available: Whether the QCrBox server is accessible
        applications: List of application objects from the API
        commands: List of command dictionaries
        selected_command: Currently selected command name (None if no selection)
        colors: Dictionary of Olex2 color settings (optional, uses defaults if None)
        
    Returns:
        HTML string with help content for the current state
    """
    # Use default colors if none provided
    if colors is None:
        colors = {
            'bg_color': '#222222',
            'font_color': '#ffffff',
            'table_bg': '#222222',
            'highlight': '#ff8888',
            'link_color': '#ababff',
            'font_name': 'Bahnschrift',
            'error_color': '#ff6666',
            'secondary_color': '#aaaaaa',
        }
    
    # State 1: Server not available
    if not qcrbox_available:
        return dedent(f'''
        <font color='{colors['error_color']}' size='4'><b>QCrBox Server Not Available</b></font><br><br>
        The QCrBox server is not running or not accessible.<br>
        Please start the QCrBox server and ensure it is reachable.
        ''')
    
    # State 2: No command selected - show available applications
    if not selected_command:
        help_parts = [
            "<font size='4'><b>Available Applications</b></font><br><br>",
            "Select a command from the dropdown to see detailed help.<br><br>"
        ]
        
        for app in applications:
            help_parts.append(f"<b>{app.name}</b> (v{app.version})<br>")
            if app.description:
                help_parts.append(f"{app.description}<br>")
            help_parts.append("<br>")
        
        return ''.join(help_parts)
    
    # State 3: Command selected - show full details
    # selected_command format is "command_name(application_slug)"
    command_obj = next((cmd for cmd in commands if f"{cmd.name}({cmd.application})" == selected_command), None)
    
    if not command_obj:
        return f"<font color='{colors['error_color']}'>Command not found</font>"
    
    app = next((a for a in applications if a.id == command_obj.application_id), None)
    if not app:
        return f"<font color='{colors['error_color']}'>Application not found</font>"
    
    help_parts = [
        f"<font size='5' color='{colors['font_color']}'><b>{command_obj.name}</b></font><br><br>"
    ]
    
    # Command description
    if command_obj.description:
        help_parts.append(f"{command_obj.description}<br><br>")
    
    # Add parameter descriptions if any
    if hasattr(command_obj.parameters, 'additional_properties'):
        param_descs = []
        for param_name, param_info in command_obj.parameters.additional_properties.items():
            dtype = param_info.get('dtype', '')
            # Skip CIF input and output parameters (auto-filled)
            if dtype in ['QCrBox.cif_data_file', 'QCrBox.output_cif']:
                continue
            description = param_info.get('description', '')
            required = param_info.get('required', False)
            req_marker = f" <font color='{colors['highlight']}'>(required)</font>" if required else ""
            default_val = param_info.get('default_value')
            default_str = f" [default: {default_val}]" if default_val not in [None, '', 'None'] else ""
            
            if description:
                param_descs.append(f"<br>• <b>{param_name}</b>{req_marker}{default_str}: {description}")
        
        if param_descs:
            help_parts.append("<b>Parameters:</b>")
            help_parts.extend(param_descs)
            help_parts.append("<br><br>")
    
    # Application information (Provided by)
    help_parts.append(f"<font size='2' color='{colors['secondary_color']}'>")
    help_parts.append(f"<b>Provided by:</b> {app.name} v{app.version}<br>")
    if app.description:
        help_parts.append(f"{app.description}<br>")
    if app.url:
        help_parts.append(f"<b>URL:</b> {app.url}<br>")
    if app.doi:
        help_parts.append(f"<b>DOI:</b> {app.doi}<br>")
    help_parts.append(f"</font>")
    
    return ''.join(help_parts)
