
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
from textwrap import dedent

from pathlib import Path
import time

debug = bool(OV.GetParam("olex2.debug", False))

instance_path = OV.DataDir()

try:
  from_outside = False
  p_path = os.path.dirname(os.path.abspath(__file__))
except:
  from_outside = True
  p_path = os.path.dirname(os.path.abspath("__file__"))

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

from qcrbox_plugin import (
    QCrBoxAPIAdapter,
    QCrBoxWorkflows,
    CalculationStatus,
    CommandExecution,
    UploadedDataset,
)
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
    
    # Load applications and commands from API
    self.applications = []
    self.commands = []
    self.selected_command = None
    self.parameter_states = {}
    self.current_calculation_id = None
    self.current_calculation_status = None
    self.polling_active = False
    self.run_button_text = "Run Command"
    self.run_button_color = "#FFFFFF"
    self.run_button_enabled = True
    
    # Interactive session state
    self.current_session_id = None
    self.current_session_dataset_id = None
    self.is_interactive_session = False
    
    self.load_applications()
    
    # Initialize button HTML
    button_html = generate_run_button_html(self.run_button_text, self.run_button_color, self.run_button_enabled)
    OV.write_to_olex("qcb-run-button.htm", button_html)
    OV.write_to_olex("qcb-parameters.htm" , "")
    
    # Initialize help file
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
  
  def load_applications(self):
    """Load available applications and commands from QCrBox API"""
    try:
      from qcrboxapiclient.api.applications import list_applications
      response = list_applications.sync(client=self.qcrbox_adapter.client)
      
      if hasattr(response, 'payload') and hasattr(response.payload, 'applications'):
        self.applications = response.payload.applications
        
        # Extract all commands from all applications
        self.commands = []
        for app in self.applications:
          # Filter out internal/private commands (starting with __)
          public_commands = [cmd for cmd in app.commands if not cmd.name.startswith('__')]
          self.commands.extend(public_commands)
        
        # Initialize parameter states for all commands using command.id
        for cmd in self.commands:
          self.parameter_states[cmd.id] = {}
          
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
              self.parameter_states[cmd.id][param_name] = default_val
        
        # Set the first command as selected
        if self.commands:
          first_cmd = self.commands[0]
          self.selected_command = f"{first_cmd.name}({first_cmd.application})"
          
        print(f"Loaded {len(self.applications)} applications with {len(self.commands)} commands from QCrBox API")
      else:
        print("Failed to parse applications response")
        self.applications = []
        self.commands = []
    except Exception as e:
      print(f"Failed to load applications from QCrBox API: {e}")
      import traceback
      traceback.print_exc()
      self.applications = []
      self.commands = []
    
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
      import traceback
      traceback.print_exc()
      return None
  
  def print_commands(self):
    """Print all available commands with their details"""
    if not self.commands:
      print("No commands loaded. Try running load_commands() first.")
      return
    
    for cmd in self.commands:
      print(f"Command: {cmd.name}")
      print(f"  Application: {cmd.application} (ID: {cmd.application_id})")
      print(f"  Description: {cmd.description}")
      print(cmd)
      print("\n")
  
  def reload_commands(self):
    """Reload applications and commands from API and reset selection"""
    print("Reloading applications and commands from QCrBox API...")
    self.applications = []
    self.commands = []
    self.selected_command = None
    self.parameter_states = {}
    self.load_applications()
    # Update the GUI
    OV.write_to_olex("qcb-parameters.htm", "")
    self.update_run_button("Run Command", "#FFFFFF", True)
    self.update_help_file()
    return True
  
  def update_help_file(self):
    """Generate and write dynamic help HTML file based on current state"""
    try:
      # Generate help content using template module
      help_content = generate_help_content_html(
          qcrbox_available=self.qcrbox_adapter.health_check(),
          applications=self.applications,
          commands=self.commands,
          selected_command=self.selected_command
      )
      
      print(f"[DEBUG] Help content length: {len(help_content)}")
      print(f"[DEBUG] Help content preview: {help_content[:200]}")
      
      # Wrap in full HTML template
      help_html = generate_help_file_html(help_content)
      
      print(f"[DEBUG] Help HTML length: {len(help_html)}")
      print(f"[DEBUG] Writing help file...")
      
      # Write to file
      OV.write_to_olex("qcrbox_command_help.htm", help_html)
      print(f"[DEBUG] Help file written successfully")
      
    except Exception as e:
      print(f"[ERROR] Failed to update help file: {e}")
      import traceback
      traceback.print_exc()
    
  def generate_command_list_string(self):
    if not self.commands:
      return "No commands available"
    return ";".join([f"{cmd.name}({cmd.application})" for cmd in self.commands])
  
  def generate_default_command_value(self):
    return self.selected_command

  def set_selected_command(self, command_name):
    self.selected_command = command_name
    new_parameter_html = self.produce_parameter_html()
    OV.write_to_olex("qcb-parameters.htm" , new_parameter_html)
    # Update help file when command changes
    self.update_help_file()


  def set_parameter_state(self, command_id, parameter_name, value): 
    # Ensure command_id is always an integer for consistency
    command_id = int(command_id)
    print(f"Setting parameter state for command {command_id}, {parameter_name} to {value}")
    if command_id in self.parameter_states:
      self.parameter_states[command_id][parameter_name] = value
    else:
      self.parameter_states[command_id] = {parameter_name: value}

  def get_parameter_state(self, command_id, parameter_name):
    # Ensure command_id is always an integer for consistency
    command_id = int(command_id)
    return self.parameter_states.get(command_id, {}).get(parameter_name, None)
  
  def is_command_interactive(self, command_obj):
    """Check if a command is interactive based on its metadata."""
    if not command_obj:
      return False
    # Check if command has interactive flag in metadata
    if hasattr(command_obj, 'interactive') and command_obj.interactive:
      return True
    # Check if command name or description suggests it's interactive
    if 'interactive' in command_obj.name.lower():
      return True
    if hasattr(command_obj, 'description') and command_obj.description:
      if 'interactive' in command_obj.description.lower():
        return True
    return False
  
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
  
  def reset_session_state(self):
    """Force reset all session state. Use if a session is stuck or failed."""
    print("Resetting session state...")
    
    # Try to close any active session if one exists
    if self.current_session_id:
      try:
        from qcrboxapiclient.api.interactive_sessions import close_interactive_session
        print(f"Attempting to close session {self.current_session_id}...")
        close_interactive_session.sync(
          client=self.qcrbox_adapter.client,
          id=self.current_session_id
        )
        print("Session closed")
      except Exception as e:
        print(f"Could not close session (may not exist): {e}")
    
    # Reset all state
    self.current_session_id = None
    self.current_session_dataset_id = None
    self.is_interactive_session = False
    self.current_calculation_id = None
    self.current_calculation_status = None
    self.polling_active = False
    self.update_run_button("Run Command", "#FFFFFF", True)
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
    sessions = self.list_active_sessions()
    
    if not sessions:
      print("No sessions to close")
      return
    
    from qcrboxapiclient.api.interactive_sessions import close_interactive_session
    
    for session in sessions:
      try:
        print(f"Closing session {session.session_id}...")
        close_interactive_session.sync(
          client=self.qcrbox_adapter.client,
          id=session.session_id
        )
        print(f"  ✓ Closed successfully")
      except Exception as e:
        print(f"  ✗ Failed to close: {e}")
    
    # Reset local state
    self.current_session_id = None
    self.current_session_dataset_id = None
    self.is_interactive_session = False
    self.update_run_button("Run Command", "#FFFFFF", True)
    print("\nAll sessions closed and local state reset")
  
  def poll_calculation_status(self):
    """Poll the current calculation status and update GUI"""
    print(f"[POLL] Checking calculation {self.current_calculation_id}, polling_active={self.polling_active}")
    
    if not self.current_calculation_id or not self.polling_active:
      print("[POLL] Stopping - no calculation ID or polling inactive")
      return
    
    try:
      from qcrboxapiclient.api import calculations
      from qcrboxapiclient.models.q_cr_box_response_calculations_response import QCrBoxResponseCalculationsResponse
      
      print(f"[POLL] Fetching status from API...")
      response = calculations.get_calculation_by_id.sync(
        id=self.current_calculation_id,
        client=self.qcrbox_adapter.client
      )
      
      if isinstance(response, QCrBoxResponseCalculationsResponse):
        calc = response.payload.calculations[0]
        status = calc.status
        print(f"[POLL] Current status: {status}")
        
        if status != self.current_calculation_status:
          self.current_calculation_status = status
          print(f"[POLL] Status changed: {status}")
          
          if status == CalculationStatus.SUCCESSFUL:
            self.polling_active = False
            self.update_run_button("Retrieve Results", "#00AA00", True)
            print("Calculation completed successfully!")
          
          elif status == CalculationStatus.FAILED:
            self.polling_active = False
            self.update_run_button("Calculation Failed (see log)", "#AA0000", True)
            print(f"Calculation FAILED!")
            print(f"Calculation metadata: {calc}")
            if hasattr(calc, 'error_message'):
              print(f"Error message: {calc.error_message}")
          
          elif status == CalculationStatus.STOPPED:
            self.polling_active = False
            self.update_run_button("Calculation Stopped", "#FF8800", True)
            print("Calculation was stopped")
        
        # Continue polling if still running
        if self.polling_active:
          print(f"[POLL] Scheduling next poll in 2 seconds...")
          import threading
          timer = threading.Timer(2.0, self.poll_calculation_status)
          timer.daemon = True
          timer.start()
        else:
          print(f"[POLL] Polling complete")
      
    except Exception as e:
      print(f"[POLL ERROR] Error polling calculation status: {e}")
      import traceback
      traceback.print_exc()
      self.polling_active = False
  
  def still_running_calculation(self):
    """Show message when user clicks disabled button during calculation"""
    print("Still running calculation")
    return "Still running calculation"
  
  def start_interactive_session(self):
    """Start an interactive session and open browser to VNC URL."""
    # Check if we have lingering session state and clean it up
    if self.is_interactive_session or self.current_session_id:
      print("WARNING: Found lingering session state, cleaning up...")
      self.reset_session_state()
    
    if not self.selected_command or not self.commands:
      print("No command selected")
      return None
    
    current_command = self.selected_command
    command_obj = next((cmd for cmd in self.commands if f"{cmd.name}({cmd.application})" == current_command), None)
    
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
        param_value = self.parameter_states.get(command_obj.id, {}).get(param_name)
        
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
      self.current_session_id = session_id
      self.current_calculation_id = session_id  # Session ID is also calculation ID
      self.current_session_dataset_id = dataset_id
      self.is_interactive_session = True
      
      # Construct VNC URL from stored qcrbox_url
      qcrbox_base = self.qcrbox_url.replace('http://', '').replace('https://', '').split(':')[0]
      vnc_url = f"http://{qcrbox_base}:12004/vnc.html?path=vnc&autoconnect=true&resize=remote&reconnect=true&show_dot=true"
      
      print(f"Opening browser to: {vnc_url}")
      
      # Open browser to VNC URL
      import webbrowser
      webbrowser.open(vnc_url)
      
      # Update button to show session is active
      self.update_run_button("Close Session & Retrieve Results", "#FF8800", True)
      
      return session_id
      
    except Exception as e:
      print(f"Failed to start interactive session: {e}")
      import traceback
      traceback.print_exc()
      # Clean up state on failure
      self.current_session_id = None
      self.current_session_dataset_id = None
      self.is_interactive_session = False
      self.update_run_button("Run Command", "#FFFFFF", True)
      return None
  
  def close_interactive_session_and_retrieve(self):
    """Close the interactive session and retrieve the resulting CIF file."""
    if not self.current_session_id:
      print("No active interactive session")
      return False
    
    print(f"Closing interactive session {self.current_session_id}...")
    
    try:
      from qcrboxapiclient.api.interactive_sessions import close_interactive_session
      from qcrboxapiclient.models import QCrBoxErrorResponse
      
      # Close the session
      response = close_interactive_session.sync(
        client=self.qcrbox_adapter.client,
        id=self.current_session_id
      )
      
      if isinstance(response, QCrBoxErrorResponse):
        print(f"Failed to close interactive session: {response}")
        return False
      
      print("Interactive session closed successfully")
      
      # Wait a moment for the session to finalize
      import time
      time.sleep(2)
      
      # Check if this command even produces output CIFs
      current_command = self.selected_command
      command_obj = None
      if current_command and self.commands:
        command_obj = next((cmd for cmd in self.commands if f"{cmd.name}({cmd.application})" == current_command), None)
      
      has_output_cif = self.command_has_output_cif(command_obj) if command_obj else False
      
      if not has_output_cif:
        print("This command does not produce an output CIF file - nothing to retrieve")
        # Clean up and exit
        self.current_session_id = None
        self.current_session_dataset_id = None
        self.is_interactive_session = False
        self.update_run_button("Run Command", "#FFFFFF", True)
        return True  # Successfully closed, just no output
      
      # Now retrieve the output - the session should have created an output dataset
      from qcrboxapiclient.api import calculations
      from qcrboxapiclient.models.q_cr_box_response_calculations_response import QCrBoxResponseCalculationsResponse
      
      print("Checking for output dataset...")
      # Get calculation details to find output dataset
      calc_response = calculations.get_calculation_by_id.sync(
        id=self.current_session_id,
        client=self.qcrbox_adapter.client
      )
      
      if isinstance(calc_response, QCrBoxResponseCalculationsResponse):
        calc = calc_response.payload.calculations[0]
        print(f"Calculation status: {calc.status}")
        output_dataset_id = calc.output_dataset_id
        
        if output_dataset_id:
          print(f"Output dataset ID: {output_dataset_id}")
          
          # Set the status and ID BEFORE calling download method
          self.current_calculation_id = self.current_session_id
          self.current_calculation_status = CalculationStatus.SUCCESSFUL
          
          # Use existing download method
          result = self.download_and_open_result()
          
          # Clean up session state after download
          self.current_session_id = None
          self.current_session_dataset_id = None
          self.is_interactive_session = False
          self.current_calculation_id = None
          self.current_calculation_status = None
          
          return result
        else:
          print("No output dataset found from interactive session")
          print("This may be normal if no output CIF was created during the session")
          # Still clean up
          self.current_session_id = None
          self.current_session_dataset_id = None
          self.is_interactive_session = False
          self.update_run_button("Run Command", "#FFFFFF", True)
          return False
      else:
        print("Failed to get calculation details")
        # Clean up
        self.current_session_id = None
        self.current_session_dataset_id = None
        self.is_interactive_session = False
        self.update_run_button("Run Command", "#FFFFFF", True)
        return False
        
    except Exception as e:
      print(f"Failed to close interactive session and retrieve results: {e}")
      import traceback
      traceback.print_exc()
      # Clean up
      self.current_session_id = None
      self.current_session_dataset_id = None
      self.is_interactive_session = False
      self.update_run_button("Run Command", "#FFFFFF", True)
      return False
  
  def update_run_button(self, text, color, enabled):
    """Update the run button appearance"""
    self.run_button_text = text
    self.run_button_color = color
    self.run_button_enabled = enabled
    print(f"Button updated: '{text}' (color: {color}, enabled: {enabled})")
    
    # Regenerate the button HTML and update the GUI
    try:
      button_html = generate_run_button_html(self.run_button_text, self.run_button_color, self.run_button_enabled)
      OV.write_to_olex("qcb-run-button.htm", button_html)
      print(f"[GUI] Button HTML updated")
    except Exception as e:
      print(f"[GUI] Failed to update button HTML: {e}")
  
  def download_and_open_result(self):
    """Download the result CIF from completed calculation and open in Olex2"""
    if not self.current_calculation_id:
      print("No calculation to retrieve results from")
      return False
    
    if self.current_calculation_status != CalculationStatus.SUCCESSFUL:
      print(f"Cannot retrieve results - calculation status is: {self.current_calculation_status}")
      return False
    
    try:
      from qcrboxapiclient.api import calculations
      from qcrboxapiclient.models.q_cr_box_response_calculations_response import QCrBoxResponseCalculationsResponse
      
      # Get calculation details to find output dataset
      response = calculations.get_calculation_by_id.sync(
        id=self.current_calculation_id,
        client=self.qcrbox_adapter.client
      )
      
      if not isinstance(response, QCrBoxResponseCalculationsResponse):
        print("Failed to get calculation details")
        return False
      
      calc = response.payload.calculations[0]
      print(f"Retrieving results from calculation {self.current_calculation_id}")
      
      # Get output dataset ID
      output_dataset_id = calc.output_dataset_id
      if not output_dataset_id:
        print("No output dataset found in calculation results")
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
                  olx.Atreap(output_path)
                  # Reset button for next calculation
                  self.update_run_button("Run Command", "#FFFFFF", True)
                  return True
        
        print("Could not find file content in JSON response")
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
        olx.Atreap(output_path)
        # Reset button for next calculation
        self.update_run_button("Run Command", "#FFFFFF", True)
        return True
      
    except Exception as e:
      print(f"Failed to download and open result: {e}")
      import traceback
      traceback.print_exc()
      return False
  
  def convert_cif_ddl2_to_ddl1(self, cif_text):
    """Convert CIF data names from DDL2 format (dots) to DDL1 format (underscores).
    
    Converts entries like _cell.length_a to _cell_length_a while preserving
    numeric values (12.3), string values, and multiline strings.
    Only converts dots within CIF data names (starting with _ at line beginning).
    
    Args:
        cif_text: The CIF file content as a string
        
    Returns:
        Modified CIF text with DDL1 format data names
    """
    import re
    
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
    if not self.selected_command or not self.commands:
      return
    
    current_command = self.selected_command
    command_obj = next((cmd for cmd in self.commands if f"{cmd.name}({cmd.application})" == current_command), None)
    
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
            self.parameter_states[command_obj.id][param_name] = {
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
    if self.is_interactive_session and self.current_session_id:
      return self.close_interactive_session_and_retrieve()
    
    if not self.selected_command or not self.commands:
      print("No command selected")
      return None
    
    current_command = self.selected_command
    command_obj = next((cmd for cmd in self.commands if f"{cmd.name}({cmd.application})" == current_command), None)
    
    if not command_obj:
      print(f"Command not found: {current_command}")
      return None
    
    # Check if this is an interactive command
    if self.is_command_interactive(command_obj):
      print("Detected interactive command - starting interactive session")
      return self.start_interactive_session()
    
    # Non-interactive command execution follows
    print(f"DEBUG: command_obj.id = {command_obj.id}")
    print(f"DEBUG: parameter_states keys = {list(self.parameter_states.keys())}")
    print(f"DEBUG: parameter_states[{command_obj.id}] = {self.parameter_states.get(command_obj.id, 'NOT FOUND')}")
    
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
        param_value = self.parameter_states.get(command_obj.id, {}).get(param_name)
        
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
      
      # Store calculation info and start polling
      self.current_calculation_id = execution.calculation_id
      self.current_calculation_status = CalculationStatus.RUNNING
      self.polling_active = True
      
      # Update button to show running state
      self.update_run_button("Calculation Running...", "#0088FF", False)
      
      # Start background polling
      import threading
      timer = threading.Timer(2.0, self.poll_calculation_status)
      timer.daemon = True
      timer.start()
      
      return execution
      
    except Exception as e:
      print(f"Failed to run command: {e}")
      import traceback
      traceback.print_exc()
      self.update_run_button("Run Command", "#FFFFFF", True)
      return None
  
  def produce_parameter_html(self):
    if not self.selected_command or not self.commands:
      return "<td>No command selected</td>"
    
    current_command = self.selected_command
    command_obj = next((cmd for cmd in self.commands if f"{cmd.name}({cmd.application})" == current_command), None)
    
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
