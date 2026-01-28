
from olexFunctions import OlexFunctions
OV = OlexFunctions()

import os
import htmlTools
import olex
import olx
import gui
import httpx
import io
import sys
import json
import re
import threading
import time
import webbrowser
from textwrap import dedent

from pathlib import Path

debug = bool(OV.GetParam("olex2.debug", False))

# In debug mode, disable Python bytecode cache to ensure code changes are reflected
if debug:
    sys.dont_write_bytecode = True
    print("[DEBUG] Python bytecode caching disabled")

instance_path = OV.DataDir()

try:
  from_outside = False
  p_path = os.path.dirname(os.path.abspath(__file__))
except:
  from_outside = True
  p_path = os.path.dirname(os.path.abspath("__file__"))

# Clear cache after p_path is determined
if debug:
    try:
        import shutil
        cache_dir = os.path.join(p_path, '__pycache__')
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
            print(f"[DEBUG] Cleared cache directory: {cache_dir}")
        
        # Clear qcrbox_plugin cache too
        plugin_cache = os.path.join(p_path, 'qcrbox_plugin', '__pycache__')
        if os.path.exists(plugin_cache):
            shutil.rmtree(plugin_cache)
            print(f"[DEBUG] Cleared plugin cache directory: {plugin_cache}")
    except Exception as e:
        print(f"[DEBUG] Could not clear cache: {e}")

if p_path not in sys.path:
    sys.path.insert(0, p_path)

l = open(os.sep.join([p_path, 'def.txt'])).readlines()
d = {}
for line in l:
  line = line.strip()
  if not line or line.startswith("#"):
    continue
  d[line.split("=")[0].strip()] = line.split("=")[1].strip()

p_name = d['p_name']
p_htm = d['p_htm']
p_img = eval(d['p_img'])
p_scope = d['p_scope']

OV.SetVar('olex2qcrbox_plugin_path', p_path)

from PluginTools import PluginTools as PT
import inspect
import importlib
import traceback

from qcrbox_plugin import (
    QCrBoxAPIAdapter,
    QCrBoxWorkflows,
    CalculationStatus,
    CommandExecution,
    UploadedDataset,
    PluginState,
    SessionManager,
    CalculationRunner,
    convert_cif_ddl2_to_ddl1,
    extract_cif_from_json_response,
    tests,
    gui_controller,
)

# Force reload of html_templates to pick up changes
import qcrbox_plugin.html_templates
importlib.reload(qcrbox_plugin.html_templates)

from qcrbox_plugin.html_templates import (
    generate_parameter_html, 
    generate_run_button_html,
    generate_help_file_html,
    generate_help_content_html
)
from qcrboxapiclient.api.commands import list_commands
from qcrboxapiclient.models.q_cr_box_response_commands_response import QCrBoxResponseCommandsResponse

### ----------------------------------------------------------------------------------------------------------------------------------
# Plugin Implementation
### ----------------------------------------------------------------------------------------------------------------------------------
### ----------------------------------------------------------------------------------------------------------------------------------

def get_current_cif_bytes():
    cif_path = os.path.join(OV.FilePath(), OV.FileName()) + ".cif"
    cif_bytes = Path(cif_path).read_text(encoding='utf-8')
    print(cif_bytes)

class olex2qcrbox(PT):

  def __init__(self):
    super(olex2qcrbox, self).__init__()
    self.p_name = p_name
    self.p_path = p_path
    self.p_scope = p_scope
    self.p_htm = p_htm
    self.p_img = p_img
    self.deal_with_phil(operation='read')
    self.print_version_date()
    
    # Initialize QCrBox adapter
    self.qcrbox_url = OV.GetParam("olex2.qcrbox_url", "http://localhost:11000")
    self.qcrbox_adapter = QCrBoxAPIAdapter(base_url=self.qcrbox_url)
    
    # Initialize plugin state
    self.state = PluginState()
    
    # Initialize session manager
    self.session_manager = SessionManager(
        self.qcrbox_adapter.client, 
        self.qcrbox_url
    )
    
    # Initialize calculation runner
    self.calc_runner = CalculationRunner(self.qcrbox_adapter.client)
    
    # Cache health check result to avoid repeated network calls
    self.state.qcrbox_available = self.qcrbox_adapter.health_check()
    
    # Load applications and commands from API
    self.load_applications()
    
    # Initialize GUI
    gui_controller.update_run_button(
        self.state.run_button_text,
        self.state.run_button_color,
        self.state.run_button_enabled
    )
    gui_controller.clear_parameter_panel()
    self.update_help_file()

    if not from_outside:
      self.setup_gui()
    self._register_all_methods()
    # END Generated =======================================

  def _register_all_methods(self):
    """Automatically register all non-magic, public methods defined in this class only."""
    for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
      # Skip magic methods, private methods, and parent class methods
      if not name.startswith('_') and name in self.__class__.__dict__:
        OV.registerFunction(method, True, "qcb")
        if debug:
          print(f"Registered method: {name}")
    

  def check_available(self):
    return self.qcrbox_adapter.health_check()
  
  def get_olex2_colors(self):
    """Get Olex2 color scheme from settings."""
    return gui_controller.get_olex2_colors()
  
  def load_applications(self):
    """Load available applications and commands from QCrBox API"""
    try:
      from qcrboxapiclient.api.applications import list_applications
      response = list_applications.sync(client=self.qcrbox_adapter.client)
      
      if hasattr(response, 'payload') and hasattr(response.payload, 'applications'):
        self.state.applications = response.payload.applications
        
        # Extract all commands from all applications
        self.state.commands = []
        for app in self.state.applications:
          # Filter out internal/private commands (starting with __)
          public_commands = [cmd for cmd in app.commands if not cmd.name.startswith('__')]
          self.state.commands.extend(public_commands)
        
        # Initialize parameter states for all commands using command.id
        for cmd in self.state.commands:
          self.state.parameter_states[cmd.id] = {}
          
          # Set default values from parameters
          if hasattr(cmd.parameters, 'additional_properties'):
            for param_name, param_info in cmd.parameters.additional_properties.items():
              dtype = param_info.get('dtype', '')
              default_val = param_info.get('default_value', '')
              
              # Auto-fill output_cif parameters with generic name
              if dtype == 'QCrBox.output_cif' and not default_val:
                default_val = 'output'
              
              if default_val is None:
                default_val = ''
              self.state.parameter_states[cmd.id][param_name] = default_val
        
        # Set the first command as selected
        if self.state.commands:
          first_cmd = self.state.commands[0]
          self.state.selected_command = f"{first_cmd.name}({first_cmd.application})"
          
        print(f"Loaded {len(self.state.applications)} applications with {len(self.state.commands)} commands from QCrBox API")
      else:
        print("Failed to parse applications response")
        self.state.applications = []
        self.state.commands = []
    except Exception as e:
      print(f"Failed to load applications from QCrBox API: {e}")
      traceback.print_exc()
      self.state.applications = []
      self.state.commands = []
    
  def print_applications(self):
    """Retrieve and print all available applications from QCrBox API"""
    try:
      from qcrboxapiclient.api.applications import list_applications
      response = list_applications.sync(client=self.qcrbox_adapter.client)
      
      print("=" * 80)
      print("APPLICATIONS DATA FROM API")
      print("=" * 80)
      print(f"Response type: {type(response)}")
      print(f"Response: {response}")
      
      # Try to access different possible attributes
      if hasattr(response, 'payload'):
        print(f"\nPayload: {response.payload}")
        if hasattr(response.payload, 'applications'):
          print(f"\nApplications count: {len(response.payload.applications)}")
          for app in response.payload.applications:
            print(f"\n--- Application ---")
            print(f"  Type: {type(app)}")
            print(f"  Data: {app}")
            if hasattr(app, '__dict__'):
              for key, value in app.__dict__.items():
                print(f"  {key}: {value}")
      
      print("=" * 80)
      return response
      
    except Exception as e:
      print(f"Error retrieving applications: {e}")
      traceback.print_exc()
      return None
  
  def print_commands(self):
    """Print all available commands with their details"""
    if not self.state.commands:
      print("No commands loaded. Try running load_commands() first.")
      return
    
    for cmd in self.state.commands:
      print(f"Command: {cmd.name}")
      print(f"  Application: {cmd.application} (ID: {cmd.application_id})")
      print(f"  Description: {cmd.description}")
      print(cmd)
      print("\n")
  
  def reload_commands(self):
    """Reload applications and commands from API and reset selection"""
    print("Reloading applications and commands from QCrBox API...")
    self.state.applications = []
    self.state.commands = []
    self.state.selected_command = None
    self.state.parameter_states = {}
    # Cache health check result
    self.state.qcrbox_available = self.qcrbox_adapter.health_check()
    self.load_applications()
    # Update the GUI
    gui_controller.clear_parameter_panel()
    gui_controller.update_run_button("Run Command", "#FFFFFF", True)
    self.update_help_file()
    return True
  
  def update_help_file(self):
    """Generate and write dynamic help HTML file based on current state"""
    gui_controller.update_help_file(
        qcrbox_available=self.state.qcrbox_available,
        applications=self.state.applications,
        commands=self.state.commands,
        selected_command=self.state.selected_command
    )
    
  def generate_command_list_string(self):
    if not self.state.commands:
      return "No commands available"
    return ";".join([f"{cmd.name}({cmd.application})" for cmd in self.state.commands])
  
  def generate_default_command_value(self):
    return self.state.selected_command

  def set_selected_command(self, command_name):
    self.state.selected_command = command_name
    new_parameter_html = self.produce_parameter_html()
    gui_controller.update_parameter_panel(new_parameter_html)


  def set_parameter_state(self, command_id, parameter_name, value): 
    # Ensure command_id is always an integer for consistency
    command_id = int(command_id)
    print(f"Setting parameter state for command {command_id}, {parameter_name} to {value}")
    
    # Check if this is a file parameter that needs to be uploaded
    command_obj = next((cmd for cmd in self.state.commands if cmd.id == command_id), None)
    if command_obj and hasattr(command_obj.parameters, 'additional_properties'):
      param_info = command_obj.parameters.additional_properties.get(parameter_name)
      if param_info:
        dtype = param_info.get('dtype', '')
        
        # If it's a data_file parameter and value looks like a file path, upload it
        if dtype == 'QCrBox.data_file' and value and isinstance(value, str):
          if os.path.exists(value) and os.path.isfile(value):
            print(f"Uploading file: {value}")
            try:
              workflows = QCrBoxWorkflows(self.qcrbox_adapter.client)
              uploaded = workflows.upload_file(value)
              print(f"Uploaded {uploaded.file_name} -> dataset_id: {uploaded.dataset_id}, file_id: {uploaded.data_file_id}")
              
              # Store the file_id instead of the path
              value = {'data_file_id': uploaded.data_file_id}
              print(f"Converted file path to data_file_id: {uploaded.data_file_id}")
            except Exception as e:
              print(f"Failed to upload file: {e}")
              import traceback
              traceback.print_exc()
              # Keep the original value on failure
    
    if command_id in self.state.parameter_states:
      self.state.parameter_states[command_id][parameter_name] = value
    else:
      self.state.parameter_states[command_id] = {parameter_name: value}

  def get_parameter_state(self, command_id, parameter_name):
    # Ensure command_id is always an integer for consistency
    command_id = int(command_id)
    return self.state.parameter_states.get(command_id, {}).get(parameter_name, None)
  
  def get_file_parameter_status(self, command_id, parameter_name):
    """Get display status for file parameters (Missing/Uploaded)."""
    command_id = int(command_id)
    value = self.state.parameter_states.get(command_id, {}).get(parameter_name)
    
    if value is None or value == '':
      return "<i>Missing</i>"
    elif isinstance(value, dict) and 'data_file_id' in value:
      return "<i>Uploaded</i>"
    else:
      return "<i>Unknown status</i>"
  
  def is_command_interactive(self, command_obj):
    """Check if a command is interactive based on its metadata."""
    return self.session_manager.is_command_interactive(command_obj)
  
  def command_has_output_cif(self, command_obj):
    """Check if a command has an output_cif parameter (will produce a CIF file)."""
    if not command_obj:
      return False
    if hasattr(command_obj.parameters, 'additional_properties'):
      for param_name, param_info in command_obj.parameters.additional_properties.items():
        dtype = param_info.get('dtype', '')
        if dtype == 'QCrBox.output_cif':
          return True
    return False
  
  def run_tests(self):
    """Run all plugin tests (registered function for Olex2)."""
    return tests.run_all_tests(OV, olx)
  
  def reset_session_state(self):
    """Force reset all session state. Use if a session is stuck or failed."""
    print("Resetting session state...")
    
    # Try to close any active session if one exists
    if self.state.current_session_id:
      try:
        self.session_manager.close_interactive_session(self.state.current_session_id)
      except Exception as e:
        print(f"Could not close session (may not exist): {e}")
    
    # Reset all state
    self.state.reset_all_execution_state()
    gui_controller.update_run_button("Run Command", "#FFFFFF", True)
    print("Session state reset complete")
  
  def list_active_sessions(self):
    """List all active interactive sessions on the server."""
    try:
      from qcrboxapiclient.api.interactive_sessions import list_interactive_sessions
      
      response = list_interactive_sessions.sync(client=self.qcrbox_adapter.client)
      
      if hasattr(response, 'payload') and hasattr(response.payload, 'interactive_sessions'):
        sessions = response.payload.interactive_sessions
        print(f"\n{'='*60}")
        print(f"Active Interactive Sessions: {len(sessions)}")
        print(f"{'='*60}")
        
        for i, session in enumerate(sessions, 1):
          print(f"\n[{i}] Session ID: {session.session_id}")
          print(f"    Application: {session.application_slug} v{session.application_version}")
          print(f"    Command: {session.command_name}")
          if hasattr(session, 'arguments'):
            print(f"    Arguments: {session.arguments}")
        
        print(f"\n{'='*60}\n")
        return sessions
      else:
        print("No active sessions found")
        return []
        
    except Exception as e:
      print(f"Failed to list active sessions: {e}")
      import traceback
      traceback.print_exc()
      return []
  
  def close_all_sessions(self):
    """Close all active interactive sessions on the server."""
    closed, failed = self.session_manager.close_all_sessions()
    
    # Reset local state
    self.state.reset_session_state()
    gui_controller.update_run_button("Run Command", "#FFFFFF", True)
    print("\nLocal state reset")
    return (closed, failed)
  
  def check_calculation_status(self):
    """Check the current calculation status once and update GUI accordingly.
    
    This is called manually by the user clicking the 'Check Status' button.
    """
    if not self.state.current_calculation_id:
      print("No active calculation to check")
      return
    
    try:
      from qcrboxapiclient.api import calculations
      from qcrboxapiclient.models.q_cr_box_response_calculations_response import QCrBoxResponseCalculationsResponse
      
      print(f"Checking calculation {self.state.current_calculation_id} status...")
      response = calculations.get_calculation_by_id.sync(
        id=self.state.current_calculation_id,
        client=self.qcrbox_adapter.client
      )
      
      if isinstance(response, QCrBoxResponseCalculationsResponse):
        calc = response.payload.calculations[0]
        status = calc.status
        print(f"Current status: {status}")
        
        self.state.current_calculation_status = status
        
        if status == CalculationStatus.SUCCESSFUL:
          gui_controller.update_run_button("Retrieve Results", "#00AA00", True)
          print("Calculation completed successfully!")
        
        elif status == CalculationStatus.FAILED:
          gui_controller.update_run_button("Calculation Failed (see log)", "#AA0000", True)
          print(f"Calculation FAILED!")
          print(f"Calculation metadata: {calc}")
          if hasattr(calc, 'error_message'):
            print(f"Error message: {calc.error_message}")
        
        elif status == CalculationStatus.STOPPED:
          gui_controller.update_run_button("Calculation Stopped", "#FF8800", True)
          print("Calculation was stopped")
        
        elif status == CalculationStatus.RUNNING:
          gui_controller.update_run_button("Check Status", "#0088FF", True)
          print("Calculation still running - click 'Check Status' again to refresh")
      
    except Exception as e:
      print(f"Error checking calculation status: {e}")
      import traceback
      traceback.print_exc()
  
  def reset_calculation_state(self):
    """Reset calculation state after failed/stopped calculation to allow retry"""
    print("Resetting calculation state...")
    self.state.reset_calculation_state()
    self.state.reset_session_state()
    gui_controller.update_run_button("Run Command", "#FFFFFF", True)
    print("Ready for new calculation")
    return True
  
  def still_running_calculation(self):
    """Called when user clicks the 'Check Status' button - just check status"""
    self.check_calculation_status()
  
  def start_interactive_session(self):
    """Start an interactive session and open browser to VNC URL."""
    # Check if we have lingering session state and clean it up
    if self.state.is_interactive_session or self.state.current_session_id:
      print("WARNING: Found lingering session state, cleaning up...")
      self.reset_session_state()
    
    if not self.state.selected_command or not self.state.commands:
      print("No command selected")
      return None
    
    current_command = self.state.selected_command
    command_obj = next((cmd for cmd in self.state.commands if f"{cmd.name}({cmd.application})" == current_command), None)
    
    if not command_obj:
      print(f"Command not found: {current_command}")
      return None
    
    # Upload current CIF file
    print("Uploading CIF file for interactive session...")
    upload_result = self.auto_fill_cif_parameters()
    if upload_result is None:
      print("Failed to upload current CIF file")
      return None
    
    dataset_id, data_file_id = upload_result
    
    # Build arguments from parameter states
    arguments = {}
    if hasattr(command_obj.parameters, 'additional_properties'):
      for param_name, param_info in command_obj.parameters.additional_properties.items():
        param_value = self.state.parameter_states.get(command_obj.id, {}).get(param_name)
        
        # Skip if no value set
        if param_value is None or param_value == '':
          if param_info.get('required', False):
            dtype = param_info.get('dtype', '')
            if dtype != 'QCrBox.cif_data_file':
              print(f"Missing required parameter: {param_name}")
              return None
          continue
        
        arguments[param_name] = param_value
    
    print(f"Starting interactive session: {command_obj.name} ({command_obj.application})")
    print(f"Arguments: {arguments}")
    
    try:
      from qcrboxapiclient.api.interactive_sessions import create_interactive_session
      from qcrboxapiclient.models import (
        CreateInteractiveSessionParameters,
        CreateInteractiveSessionParametersCommandArguments,
        QCrBoxErrorResponse
      )
      
      # Create session parameters
      args = CreateInteractiveSessionParametersCommandArguments.from_dict(arguments)
      params = CreateInteractiveSessionParameters(
        command_obj.application,
        command_obj.version,
        args
      )
      
      # Create interactive session
      response = create_interactive_session.sync(
        client=self.qcrbox_adapter.client,
        body=params
      )
      
      if isinstance(response, QCrBoxErrorResponse) or response is None:
        print(f"Failed to create interactive session: {response}")
        return None
      
      session_id = response.payload.interactive_session_id
      print(f"Interactive session created! Session ID: {session_id}")
      
      # Store session info
      self.state.current_session_id = session_id
      self.state.current_calculation_id = session_id  # Session ID is also calculation ID
      self.state.current_session_dataset_id = dataset_id
      self.state.is_interactive_session = True
      
      # Construct VNC URL from stored qcrbox_url
      qcrbox_base = self.qcrbox_url.replace('http://', '').replace('https://', '').split(':')[0]
      vnc_url = f"http://{qcrbox_base}:12004/vnc.html?path=vnc&autoconnect=true&resize=remote&reconnect=true&show_dot=true"
      
      print(f"Opening browser to: {vnc_url}")
      
      # Open browser to VNC URL
      import webbrowser
      webbrowser.open(vnc_url)
      
      # Update button to show session is active
      gui_controller.update_run_button("Close Session & Retrieve Results", "#FF8800", True)
      
      return session_id
      
    except Exception as e:
      print(f"Failed to start interactive session: {e}")
      import traceback
      traceback.print_exc()
      # Clean up state on failure
      self.state.current_session_id = None
      self.state.current_session_dataset_id = None
      self.state.is_interactive_session = False
      gui_controller.update_run_button("Run Command", "#FFFFFF", True)
      return None
  
  def close_interactive_session_and_retrieve(self):
    """Close the interactive session and retrieve the resulting CIF file."""
    if not self.state.current_session_id:
      print("No active interactive session")
      return False
    
    print(f"Closing interactive session {self.state.current_session_id}...")
    
    try:
      from qcrboxapiclient.api.interactive_sessions import close_interactive_session
      from qcrboxapiclient.models import QCrBoxErrorResponse
      
      # Close the session
      response = close_interactive_session.sync(
        client=self.qcrbox_adapter.client,
        id=self.state.current_session_id
      )
      
      if isinstance(response, QCrBoxErrorResponse):
        print(f"Failed to close interactive session: {response}")
        return False
      
      print("Interactive session closed successfully")
      
      # Wait a moment for the session to finalize
      import time
      time.sleep(2)
      
      # Check if this command even produces output CIFs
      current_command = self.state.selected_command
      command_obj = None
      if current_command and self.state.commands:
        command_obj = next((cmd for cmd in self.state.commands if f"{cmd.name}({cmd.application})" == current_command), None)
      
      has_output_cif = self.command_has_output_cif(command_obj) if command_obj else False
      
      if not has_output_cif:
        print("This command does not produce an output CIF file - nothing to retrieve")
        # Clean up and exit
        self.state.current_session_id = None
        self.state.current_session_dataset_id = None
        self.state.is_interactive_session = False
        gui_controller.update_run_button("Run Command", "#FFFFFF", True)
        return True  # Successfully closed, just no output
      
      # Now retrieve the output - the session should have created an output dataset
      from qcrboxapiclient.api import calculations
      from qcrboxapiclient.models.q_cr_box_response_calculations_response import QCrBoxResponseCalculationsResponse
      
      print("Checking for output dataset...")
      # Get calculation details to find output dataset
      calc_response = calculations.get_calculation_by_id.sync(
        id=self.state.current_session_id,
        client=self.qcrbox_adapter.client
      )
      
      if isinstance(calc_response, QCrBoxResponseCalculationsResponse):
        calc = calc_response.payload.calculations[0]
        print(f"Calculation status: {calc.status}")
        
        # Convert string status to CalculationStatus enum
        try:
          calc_status = CalculationStatus(calc.status)
        except ValueError:
          print(f"Unknown calculation status: {calc.status}")
          calc_status = None
        
        output_dataset_id = calc.output_dataset_id
        
        if output_dataset_id:
          print(f"Output dataset ID: {output_dataset_id}")
          
          # Set the actual status from the calculation
          self.state.current_calculation_id = self.state.current_session_id
          self.state.current_calculation_status = calc_status
          
          # Only proceed if calculation was successful
          if calc_status != CalculationStatus.SUCCESSFUL:
            print(f"Cannot retrieve results - calculation status is: {calc_status}")
            # Clean up all state
            self.state.current_session_id = None
            self.state.current_session_dataset_id = None
            self.state.is_interactive_session = False
            self.state.reset_calculation_state()
            gui_controller.update_run_button("Run Command", "#FFFFFF", True)
            return False
          
          # Use existing download method
          result = self.download_and_open_result()
          
          # Clean up session state after download
          self.state.current_session_id = None
          self.state.current_session_dataset_id = None
          self.state.is_interactive_session = False
          self.state.current_calculation_id = None
          self.state.current_calculation_status = None
          
          return result
        else:
          print("No output dataset found from interactive session")
          print("This may be normal if no output CIF was created during the session")
          # Clean up all state
          self.state.current_session_id = None
          self.state.current_session_dataset_id = None
          self.state.is_interactive_session = False
          self.state.reset_calculation_state()
          gui_controller.update_run_button("Run Command", "#FFFFFF", True)
          return False
      else:
        print("Failed to get calculation details")
        # Clean up all state
        self.state.current_session_id = None
        self.state.current_session_dataset_id = None
        self.state.is_interactive_session = False
        self.state.reset_calculation_state()
        gui_controller.update_run_button("Run Command", "#FFFFFF", True)
        return False
        
    except Exception as e:
      print(f"Failed to close interactive session and retrieve results: {e}")
      import traceback
      traceback.print_exc()
      # Clean up all state
      self.state.current_session_id = None
      self.state.current_session_dataset_id = None
      self.state.is_interactive_session = False
      self.state.reset_calculation_state()
      gui_controller.update_run_button("Run Command", "#FFFFFF", True)
      return False
  
  def update_run_button(self, text, color, enabled):
    """Update the run button appearance - delegates to GUI controller"""
    self.state.run_button_text = text
    self.state.run_button_color = color
    self.state.run_button_enabled = enabled
    gui_controller.update_run_button(text, color, enabled)
  
  def download_and_open_result(self):
    """Download the result CIF from completed calculation and open in Olex2"""
    if not self.state.current_calculation_id:
      print("No calculation to retrieve results from")
      return False
    
    if self.state.current_calculation_status != CalculationStatus.SUCCESSFUL:
      print(f"Cannot retrieve results - calculation status is: {self.state.current_calculation_status}")
      return False
    
    try:
      from qcrboxapiclient.api import calculations
      from qcrboxapiclient.models.q_cr_box_response_calculations_response import QCrBoxResponseCalculationsResponse
      
      # Get calculation details to find output dataset
      response = calculations.get_calculation_by_id.sync(
        id=self.state.current_calculation_id,
        client=self.qcrbox_adapter.client
      )
      
      if not isinstance(response, QCrBoxResponseCalculationsResponse):
        print("Failed to get calculation details")
        return False
      
      calc = response.payload.calculations[0]
      print(f"Retrieving results from calculation {self.state.current_calculation_id}")
      
      # Get output dataset ID
      output_dataset_id = calc.output_dataset_id
      if not output_dataset_id:
        print("No output dataset found in calculation results")
        print("This command may not produce output files, or the calculation did not complete properly")
        # Reset state so user can continue
        self.state.reset_calculation_state()
        gui_controller.update_run_button("Run Command", "#FFFFFF", True)
        return False
      
      print(f"Output dataset ID: {output_dataset_id}")
      
      # Download the entire dataset as a ZIP
      from qcrboxapiclient.api.datasets import download_dataset_by_id
      
      print(f"Downloading dataset {output_dataset_id}...")
      download_response = download_dataset_by_id.sync_detailed(
        id=output_dataset_id,
        client=self.qcrbox_adapter.client
      )
      
      if download_response.status_code != 200:
        print(f"Failed to download dataset: HTTP {download_response.status_code}")
        # Reset state so user can retry
        self.state.reset_calculation_state()
        gui_controller.update_run_button("Run Command", "#FFFFFF", True)
        return False
      
      # Debug: Check what we actually got
      print(f"Response content type: {download_response.headers.get('content-type', 'unknown')}")
      print(f"Response content length: {len(download_response.content)}")
      print(f"First 200 bytes: {download_response.content[:200]}")
      
      # Check if it's actually a JSON response with dataset info
      import json
      try:
        json_data = json.loads(download_response.content)
        print(f"Got JSON response: {json_data}")
        
        # Try to extract file data from the response
        if 'payload' in json_data and 'datasets' in json_data['payload']:
          dataset = json_data['payload']['datasets'][0]
          if 'data_files' in dataset:
            # Find CIF file in data_files
            for filename, file_info in dataset['data_files'].items():
              if filename.endswith('.cif'):
                print(f"Found CIF file in response: {filename}")
                # Try to get file content
                if 'content' in file_info:
                  file_content = file_info['content']
                  # Convert DDL2 to DDL1 format for Olex2 compatibility
                  file_content = self.convert_cif_ddl2_to_ddl1(file_content)
                  output_path = os.path.join(OV.FilePath(), filename)
                  with open(output_path, 'w') as f:
                    f.write(file_content)
                  print(f"Saved to: {output_path} (converted to DDL1 format)")
                  print("Opening in Olex2...")
                  gui_controller.open_file_in_olex2(output_path)
                  # Reset calculation state for next calculation
                  self.state.reset_calculation_state()
                  gui_controller.update_run_button("Run Command", "#FFFFFF", True)
                  return True
        
        print("Could not find CIF file content in JSON response")
        print("Dataset may not contain CIF output files")
        # Reset state so user can continue
        self.state.reset_calculation_state()
        gui_controller.update_run_button("Run Command", "#FFFFFF", True)
        return False
        
      except json.JSONDecodeError:
        print("Response is not JSON, trying as direct file content...")
        # If not JSON, treat as direct file content
        file_content = download_response.content.decode('utf-8')
        # Convert DDL2 to DDL1 format for Olex2 compatibility
        file_content = self.convert_cif_ddl2_to_ddl1(file_content)
        output_path = os.path.join(OV.FilePath(), "qcrbox_result.cif")
        with open(output_path, 'w') as f:
          f.write(file_content)
        print(f"Saved to: {output_path} (converted to DDL1 format)")
        print("Opening in Olex2...")
        gui_controller.open_file_in_olex2(output_path)
        # Reset calculation state for next calculation
        self.state.reset_calculation_state()
        gui_controller.update_run_button("Run Command", "#FFFFFF", True)
        return True
      
    except Exception as e:
      print(f"Failed to download and open result: {e}")
      import traceback
      traceback.print_exc()
      # Reset state so user can retry or start new calculation
      self.state.reset_calculation_state()
      gui_controller.update_run_button("Run Command", "#FFFFFF", True)
      return False
  
  def convert_cif_ddl2_to_ddl1(self, cif_text):
    """Convert CIF data names from DDL2 format (dots) to DDL1 format (underscores)."""
    return convert_cif_ddl2_to_ddl1(cif_text)
  
  def get_current_cif_text(self):
    """Get the current structure as CIF text"""
    cif_path = OV.file_ChangeExt(OV.FileFull(), 'cif')
    
    if not os.path.exists(cif_path):
      print(f"CIF file not found: {cif_path}")
      return None
    
    with open(cif_path, 'r') as f:
      return f.read()
  
  def get_current_cif_filename(self):
    """Get the current CIF filename"""
    return OV.FileName() + ".cif"
  
  def auto_fill_cif_parameters(self):
    """Automatically fill input_cif parameters with current structure"""
    if not self.state.selected_command or not self.state.commands:
      return
    
    current_command = self.state.selected_command
    command_obj = next((cmd for cmd in self.state.commands if f"{cmd.name}({cmd.application})" == current_command), None)
    
    if not command_obj:
      return
    
    # Get current CIF path
    cif_path = OV.file_ChangeExt(OV.FileFull(), 'cif')
    
    if not os.path.exists(cif_path):
      print(f"CIF file not found: {cif_path}")
      return None
    
    # Upload to QCrBox using workflows
    try:
      workflows = QCrBoxWorkflows(self.qcrbox_adapter.client)
      uploaded = workflows.upload_file(cif_path)
      
      print(f"Uploaded {uploaded.file_name} -> dataset_id: {uploaded.dataset_id}, file_id: {uploaded.data_file_id}")
      
      # Fill in all CIF input parameters
      if hasattr(command_obj.parameters, 'additional_properties'):
        for param_name, param_info in command_obj.parameters.additional_properties.items():
          dtype = param_info.get('dtype', '')
          
          # Auto-fill CIF data file parameters
          if dtype == 'QCrBox.cif_data_file':
            self.state.parameter_states[command_obj.id][param_name] = {
              'data_file_id': uploaded.data_file_id
            }
            print(f"Auto-filled {param_name} with current CIF (file_id: {uploaded.data_file_id})")
      
      return uploaded.dataset_id, uploaded.data_file_id
      
    except Exception as e:
      print(f"Failed to auto-fill CIF parameters: {e}")
      import traceback
      traceback.print_exc()
      return None
  
  def run_current_cmd_with_pars(self):
    """Execute the currently selected command with the current parameter states.
    
    Routes to either interactive session or non-interactive command execution.
    """
    # If there's an active interactive session and button was clicked, close it
    if self.state.is_interactive_session and self.state.current_session_id:
      return self.close_interactive_session_and_retrieve()
    
    if not self.state.selected_command or not self.state.commands:
      print("No command selected")
      return None
    
    current_command = self.state.selected_command
    command_obj = next((cmd for cmd in self.state.commands if f"{cmd.name}({cmd.application})" == current_command), None)
    
    if not command_obj:
      print(f"Command not found: {current_command}")
      return None
    
    # Check if this is an interactive command
    if self.is_command_interactive(command_obj):
      print("Detected interactive command - starting interactive session")
      return self.start_interactive_session()
    
    # Non-interactive command execution follows
    print(f"DEBUG: command_obj.id = {command_obj.id}")
    print(f"DEBUG: parameter_states keys = {list(self.state.parameter_states.keys())}")
    print(f"DEBUG: parameter_states[{command_obj.id}] = {self.state.parameter_states.get(command_obj.id, 'NOT FOUND')}")
    
    # Always auto-fill CIF parameters from current structure
    print("Auto-filling CIF parameters from current structure...")
    upload_result = self.auto_fill_cif_parameters()
    if upload_result is None:
      print("Failed to upload current CIF file")
      return None
    
    # Build arguments from parameter states
    arguments = {}
    if hasattr(command_obj.parameters, 'additional_properties'):
      for param_name, param_info in command_obj.parameters.additional_properties.items():
        param_value = self.state.parameter_states.get(command_obj.id, {}).get(param_name)
        
        print(f"DEBUG: Checking parameter '{param_name}': value = {param_value}, type = {type(param_value)}")
        
        # Skip if no value set
        if param_value is None or param_value == '':
          # Required parameters should have been auto-filled or have defaults
          if param_info.get('required', False):
            dtype = param_info.get('dtype', '')
            # CIF input files are auto-filled, so don't complain if missing
            if dtype != 'QCrBox.cif_data_file':
              print(f"Missing required parameter: {param_name}")
              return None
          continue
        
        # Add to arguments
        arguments[param_name] = param_value
    
    print(f"Running command: {command_obj.name} ({command_obj.application})")
    print(f"Arguments: {arguments}")
    
    # Use the workflows helper to execute
    try:
      workflows = QCrBoxWorkflows(self.qcrbox_adapter.client)
      
      # Execute the command (non-blocking)
      execution = workflows.run_command(
        application_slug=command_obj.application,
        application_version=command_obj.version,
        command_name=command_obj.name,
        arguments=arguments,
        wait=False  # Don't block - we'll poll in background
      )
      
      print(f"Command started! Calculation ID: {execution.calculation_id}")
      
      # Store calculation info
      self.state.current_calculation_id = execution.calculation_id
      self.state.current_calculation_status = CalculationStatus.RUNNING
      
      # Update button to allow manual status checking
      gui_controller.update_run_button("Check Status", "#0088FF", True)
      print("Calculation started! Click 'Check Status' to check progress.")
      
      return execution
      
    except Exception as e:
      print(f"Failed to run command: {e}")
      import traceback
      traceback.print_exc()
      gui_controller.update_run_button("Run Command", "#FFFFFF", True)
      return None
  
  def produce_parameter_html(self):
    if not self.state.selected_command or not self.state.commands:
      return "<td>No command selected</td>"
    
    current_command = self.state.selected_command
    command_obj = next((cmd for cmd in self.state.commands if f"{cmd.name}({cmd.application})" == current_command), None)
    
    if not command_obj:
      return "<td>Command not found</td>"

    html_parts = []
    
    # Check if parameters exist and have additional_properties
    if hasattr(command_obj.parameters, 'additional_properties'):
      for param_name, param_info in command_obj.parameters.additional_properties.items():
        parameter_dtype = param_info.get('dtype', 'str')
        description = param_info.get('description', '')
        required = param_info.get('required', False)

        # Skip CIF input parameters - they're auto-filled from current structure
        if parameter_dtype == 'QCrBox.cif_data_file':
          continue
        
        # Skip output_cif parameters - they're auto-filled with generic name
        if parameter_dtype == 'QCrBox.output_cif':
          continue

        part = generate_parameter_html(
          command_id=command_obj.id,
          parameter_name=param_name,
          parameter_dtype=parameter_dtype,
          description=description,
          required=required
        )
        if part:
          html_parts.append(part)

    if not html_parts:
      # Wrap in proper row structure
      return '<!-- #include tool-row gui/blocks/tool-row.htm;1; -->\n<td>No parameters for this command</td>\n<!-- #include row_table_off gui/blocks/row_table_off.htm;1; -->'
    
    # Wrap each parameter row in proper row structure
    wrapped_parts = []
    for part in html_parts:
      wrapped_parts.append(
        '<!-- #include tool-row gui/blocks/tool-row.htm;1; -->\n' +
        part + '\n' +
        '<!-- #include row_table_off gui/blocks/row_table_off.htm;1; -->'
      )
    
    return "\n".join(wrapped_parts)
    

olex2qcrbox_instance = olex2qcrbox()
print("OK.")
