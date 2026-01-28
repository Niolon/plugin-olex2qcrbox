"""Centralized state container for the QCrBox plugin."""

from dataclasses import dataclass, field
from typing import Optional
from .api_adapter import CalculationStatus


@dataclass
class PluginState:
    """Centralized state for the Olex2 QCrBox plugin.
    
    Tracks applications, commands, parameters, calculations, and interactive sessions.
    """
    
    # Application & Command state
    applications: list = field(default_factory=list)
    commands: list = field(default_factory=list)
    selected_command: Optional[str] = None
    parameter_states: dict = field(default_factory=dict)
    qcrbox_available: bool = False  # Cached health check result
    
    # Calculation state (non-interactive commands)
    current_calculation_id: Optional[str] = None
    current_calculation_status: Optional[CalculationStatus] = None
    
    # Interactive session state
    current_session_id: Optional[str] = None
    current_session_dataset_id: Optional[str] = None
    is_interactive_session: bool = False
    
    # GUI Button state
    run_button_text: str = "Run Command"
    run_button_color: str = "#FFFFFF"
    run_button_enabled: bool = True
    
    def reset_calculation_state(self):
        """Reset calculation-related state."""
        self.current_calculation_id = None
        self.current_calculation_status = None
    
    def reset_session_state(self):
        """Reset interactive session state."""
        self.current_session_id = None
        self.current_session_dataset_id = None
        self.is_interactive_session = False
    
    def reset_all_execution_state(self):
        """Reset all calculation and session state."""
        self.reset_calculation_state()
        self.reset_session_state()
        self.run_button_text = "Run Command"
        self.run_button_color = "#FFFFFF"
        self.run_button_enabled = True
    
    def get_selected_command_obj(self):
        """Get the currently selected command object.
        
        Returns:
            Command object or None if not found
        """
        if not self.selected_command or not self.commands:
            return None
        return next(
            (cmd for cmd in self.commands 
             if f"{cmd.name}({cmd.application})" == self.selected_command),
            None
        )
