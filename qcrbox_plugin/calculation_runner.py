"""Non-interactive command execution and calculation polling."""

import threading
import time
from typing import Optional, Callable

from qcrboxapiclient.api import calculations
from qcrboxapiclient.models.q_cr_box_response_calculations_response import (
    QCrBoxResponseCalculationsResponse
)

from .api_adapter import (
    QCrBoxWorkflows,
    CalculationStatus,
    CommandExecution
)


class CalculationRunner:
    """Manages non-interactive command execution and polling."""
    
    def __init__(self, client):
        """Initialize calculation runner.
        
        Args:
            client: QCrBox API client
        """
        self.client = client
        self.workflows = QCrBoxWorkflows(client)
    
    def run_command(
        self,
        command_obj,
        arguments: dict
    ) -> Optional[CommandExecution]:
        """Execute a non-interactive command.
        
        Args:
            command_obj: Command object with application and version info
            arguments: Command arguments dictionary
            
        Returns:
            CommandExecution object on success, None on failure
        """
        print(f"Running command: {command_obj.name} ({command_obj.application})")
        print(f"Arguments: {arguments}")
        
        try:
            execution = self.workflows.run_command(
                application_slug=command_obj.application,
                application_version=command_obj.version,
                command_name=command_obj.name,
                arguments=arguments,
                wait=False  # Don't block - caller handles polling
            )
            
            print(f"Command started! Calculation ID: {execution.calculation_id}")
            return execution
            
        except Exception as e:
            print(f"Failed to run command: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_calculation_status(self, calculation_id: str) -> Optional[CalculationStatus]:
        """Get current status of a calculation.
        
        Args:
            calculation_id: Calculation ID to check
            
        Returns:
            CalculationStatus or None on error
        """
        try:
            response = calculations.get_calculation_by_id.sync(
                id=calculation_id,
                client=self.client
            )
            
            if isinstance(response, QCrBoxResponseCalculationsResponse):
                calc = response.payload.calculations[0]
                return calc.status
            
            return None
            
        except Exception as e:
            print(f"Error getting calculation status: {e}")
            return None
    
    def start_polling(
        self,
        calculation_id: str,
        on_status_change: Callable[[CalculationStatus], None],
        poll_interval: float = 2.0
    ):
        """Start background polling of calculation status.
        
        Args:
            calculation_id: Calculation ID to poll
            on_status_change: Callback for status changes
            poll_interval: Seconds between polls
        """
        def poll():
            print(f"[POLL] Checking calculation {calculation_id}")
            
            try:
                status = self.get_calculation_status(calculation_id)
                
                if status:
                    print(f"[POLL] Current status: {status}")
                    on_status_change(status)
                    
                    # Continue polling if still running
                    if status == CalculationStatus.RUNNING:
                        print(f"[POLL] Scheduling next poll in {poll_interval} seconds...")
                        timer = threading.Timer(poll_interval, poll)
                        timer.daemon = True
                        timer.start()
                    else:
                        print(f"[POLL] Polling complete - status: {status}")
                else:
                    print(f"[POLL] Failed to get status")
                    
            except Exception as e:
                print(f"[POLL ERROR] Error polling calculation status: {e}")
                import traceback
                traceback.print_exc()
        
        # Start first poll
        timer = threading.Timer(poll_interval, poll)
        timer.daemon = True
        timer.start()
    
    def get_calculation_output_dataset(self, calculation_id: str) -> Optional[str]:
        """Get output dataset ID from a completed calculation.
        
        Args:
            calculation_id: Calculation ID
            
        Returns:
            Output dataset ID or None
        """
        try:
            response = calculations.get_calculation_by_id.sync(
                id=calculation_id,
                client=self.client
            )
            
            if isinstance(response, QCrBoxResponseCalculationsResponse):
                calc = response.payload.calculations[0]
                return calc.output_dataset_id
            
            return None
            
        except Exception as e:
            print(f"Error getting calculation output dataset: {e}")
            return None
