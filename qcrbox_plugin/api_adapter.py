import io
import pathlib
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional, Callable, Any
from enum import Enum

import httpx
from qcrboxapiclient.client import Client
from qcrboxapiclient.api import datasets, calculations, interactive_sessions, commands
from qcrboxapiclient.models import (
  CreateDatasetBody,
  InvokeCommandParameters,
  InvokeCommandParametersCommandArguments,
  CreateInteractiveSessionParameters,
  CreateInteractiveSessionParametersCommandArguments,
  QCrBoxErrorResponse,
  QCrBoxResponseCalculationsResponse,
)
from qcrboxapiclient.types import File

from qcrboxapiclient.api.calculations import get_calculation_by_id, stop_running_calculation
from qcrboxapiclient.api.commands import invoke_command
from qcrboxapiclient.api.datasets import (
  append_to_dataset,
  create_dataset,
  delete_dataset_by_id,
  download_dataset_by_id,
)
from qcrboxapiclient.client import Client
from qcrboxapiclient.models import (
  AppendToDatasetBody,
  CreateDatasetBody,
  InvokeCommandParameters,
  InvokeCommandParametersCommandArguments,
  QCrBoxErrorResponse,
)

from qcrboxapiclient.api.commands import list_commands
from qcrboxapiclient.models.q_cr_box_response_commands_response import QCrBoxResponseCommandsResponse

from qcrboxapiclient.types import File

from qcrboxapiclient.api.admin import healthz

class CalculationStatus(str, Enum):
  """Calculation status values."""
  RUNNING = "running"
  SUCCESSFUL = "successful"
  FAILED = "failed"
  STOPPED = "stopped"


@dataclass
class UploadedDataset:
  """Result of uploading a dataset."""
  dataset_id: str
  data_file_id: str
  file_name: str


@dataclass
class CommandExecution:
  """Result of invoking a command."""
  calculation_id: str
  status: Optional[str] = None
    
  def wait_for_completion(
    self, 
    client: Client, 
    timeout: int = 30, 
    poll_interval: float = 2.0,
    on_status_update: Optional[Callable[[str], None]] = None
  ) -> str:
    """Wait for calculation to complete.
    
    Args:
      client: QCrBox client
      timeout: Maximum time to wait in seconds
      poll_interval: Time between status checks
      on_status_update: Optional callback called with status updates
        
    Returns:
      Final calculation status
        
    Raises:
      TimeoutError: If calculation doesn't complete within timeout
      RuntimeError: If status check fails
    """
    elapsed = 0
    while elapsed < timeout:
      response = calculations.get_calculation_by_id.sync(
          id=self.calculation_id, 
          client=client
      )
      
      if isinstance(response, QCrBoxResponseCalculationsResponse):
        status = response.payload.calculations[0].status
        
        if on_status_update:
          on_status_update(status)
        
        if status != CalculationStatus.RUNNING:
          return status
            
        time.sleep(poll_interval)
        elapsed += poll_interval
      else:
        raise RuntimeError(f"Failed to get calculation status: {response}")
    
    raise TimeoutError(
        f"Calculation {self.calculation_id} did not complete within {timeout}s"
    )


class QCrBoxWorkflows:
    """High-level workflow helpers for common QCrBox operations.
    
    These methods encapsulate common multi-step patterns and reduce boilerplate
    without hiding the underlying API structure.
    """
    
    def __init__(self, client: Client):
        """Initialize workflows with a QCrBox client.
        
        Args:
            client: Configured QCrBox client
        """
        self.client = client
    
    # ==================== File & Dataset Workflows ====================
    
    def upload_file(
        self, 
        file_path: str | pathlib.Path,
        check_exists: bool = True
    ) -> UploadedDataset:
        """Upload a file and create a dataset in one operation.
        
        This is the most common first step in QCrBox workflows.
        
        Args:
            file_path: Path to file to upload
            check_exists: Whether to check if file exists first
            
        Returns:
            UploadedDataset with IDs needed for commands
            
        Raises:
            FileNotFoundError: If file doesn't exist and check_exists=True
            RuntimeError: If upload fails
            
        Example:
            >>> workflows = QCrBoxWorkflows(client)
            >>> dataset = workflows.upload_file("structure.cif")
            >>> print(dataset.data_file_id)
        """
        file_path = pathlib.Path(file_path)
        
        if check_exists and not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Create file object
        with file_path.open("rb") as f:
            file = File(io.BytesIO(f.read()), file_path.name)
        
        # Upload
        upload_payload = CreateDatasetBody(file)
        response = datasets.create_dataset.sync(
            client=self.client, 
            body=upload_payload
        )
        
        # Check for errors
        if isinstance(response, QCrBoxErrorResponse) or response is None:
            raise RuntimeError(f"Failed to upload file: {response}")
        
        # Extract IDs
        dataset = response.payload.datasets[0]
        data_file = dataset.data_files[file_path.name]
        
        return UploadedDataset(
            dataset_id=dataset.qcrbox_dataset_id,
            data_file_id=data_file.qcrbox_file_id,
            file_name=file_path.name
        )
    
    def upload_multiple_files(
        self, 
        *file_paths: str | pathlib.Path
    ) -> list[UploadedDataset]:
        """Upload multiple files as separate datasets.
        
        Args:
            *file_paths: Paths to files to upload
            
        Returns:
            List of UploadedDataset objects
        """
        return [self.upload_file(fp) for fp in file_paths]
    
    @contextmanager
    def temporary_dataset(self, file_path: str | pathlib.Path):
        """Context manager for automatic dataset cleanup.
        
        Uploads file on enter, deletes dataset on exit (even if error occurs).
        
        Args:
            file_path: Path to file to upload
            
        Yields:
            UploadedDataset
            
        Example:
            >>> with workflows.temporary_dataset("test.cif") as dataset:
            ...     # Use dataset.data_file_id for commands
            ...     result = workflows.run_command(...)
            ... # Dataset automatically deleted here
        """
        uploaded = self.upload_file(file_path)
        try:
            yield uploaded
        finally:
            datasets.delete_dataset_by_id.sync(
                id=uploaded.dataset_id, 
                client=self.client
            )
    
    # ==================== Command Execution Workflows ====================
    
    def run_command(
        self,
        application_slug: str,
        application_version: str,
        command_name: str,
        arguments: dict[str, Any],
        wait: bool = False,
        timeout: int = 30,
        poll_interval: float = 2.0,
        on_status_update: Optional[Callable[[str], None]] = None
    ) -> CommandExecution:
        """Execute a non-interactive command.
        
        Args:
            application_slug: Application identifier (e.g., "qcrboxtools")
            application_version: Application version (e.g., "0.0.5")
            command_name: Command to invoke (e.g., "check_structure_convergence")
            arguments: Command arguments dict
            wait: Whether to wait for completion
            timeout: Max wait time if wait=True
            poll_interval: Status check interval if wait=True
            on_status_update: Optional status callback if wait=True
            
        Returns:
            CommandExecution object
            
        Raises:
            RuntimeError: If command invocation fails
            TimeoutError: If wait=True and command doesn't complete in time
            
        Example:
            >>> # Quick fire-and-forget
            >>> exec = workflows.run_command(
            ...     "qcrboxtools", "0.0.5", "print_cif",
            ...     {"input_cif": {"data_file_id": file_id}, "print_times": 3}
            ... )
            >>> 
            >>> # Wait for completion with progress
            >>> exec = workflows.run_command(
            ...     "qcrboxtools", "0.0.5", "analyze",
            ...     {"input": {"data_file_id": file_id}},
            ...     wait=True,
            ...     on_status_update=lambda s: print(f"Status: {s}")
            ... )
        """
        # Build command parameters
        args = InvokeCommandParametersCommandArguments.from_dict(arguments)
        params = InvokeCommandParameters(
            application_slug, 
            application_version, 
            command_name, 
            args
        )
        
        # Invoke command
        response = commands.invoke_command.sync(client=self.client, body=params)
        
        if isinstance(response, QCrBoxErrorResponse) or response is None:
            raise RuntimeError(f"Failed to invoke command: {response}")
        
        execution = CommandExecution(
            calculation_id=response.payload.calculation_id
        )
        
        # Wait if requested
        if wait:
            execution.status = execution.wait_for_completion(
                self.client, 
                timeout, 
                poll_interval, 
                on_status_update
            )
        
        return execution
    
    def run_command_with_file(
        self,
        file_path: str | pathlib.Path,
        application_slug: str,
        application_version: str,
        command_name: str,
        file_argument_name: str,
        additional_arguments: Optional[dict[str, Any]] = None,
        cleanup: bool = True,
        wait: bool = True,
        timeout: int = 30
    ) -> CommandExecution:
        """Upload file and run command in one operation.
        
        Common pattern: upload file, run command, optionally cleanup.
        
        Args:
            file_path: File to upload
            application_slug: Application identifier
            application_version: Application version
            command_name: Command to run
            file_argument_name: Name of file parameter (e.g., "input_cif")
            additional_arguments: Other command arguments
            cleanup: Whether to delete dataset after command completes
            wait: Whether to wait for command completion
            timeout: Max wait time
            
        Returns:
            CommandExecution object
            
        Example:
            >>> # Simple one-liner for common case
            >>> result = workflows.run_command_with_file(
            ...     "structure.cif",
            ...     "qcrboxtools", "0.0.5", "analyze_cif",
            ...     file_argument_name="input_cif",
            ...     additional_arguments={"option": "value"}
            ... )
        """
        if cleanup:
            with self.temporary_dataset(file_path) as dataset:
                args = {file_argument_name: {"data_file_id": dataset.data_file_id}}
                if additional_arguments:
                    args.update(additional_arguments)
                
                return self.run_command(
                    application_slug,
                    application_version,
                    command_name,
                    args,
                    wait=wait,
                    timeout=timeout
                )
        else:
            dataset = self.upload_file(file_path)
            args = {file_argument_name: {"data_file_id": dataset.data_file_id}}
            if additional_arguments:
                args.update(additional_arguments)
            
            return self.run_command(
                application_slug,
                application_version,
                command_name,
                args,
                wait=wait,
                timeout=timeout
            )
    
    # ==================== Interactive Session Workflows ====================
    
    @contextmanager
    def interactive_session(
        self,
        application_slug: str,
        application_version: str,
        arguments: dict[str, Any],
        startup_delay: float = 3.0
    ):
        """Context manager for interactive sessions with automatic cleanup.
        
        Args:
            application_slug: Application identifier (e.g., "olex2")
            application_version: Application version
            arguments: Session arguments
            startup_delay: Time to wait for session startup
            
        Yields:
            Session ID
            
        Example:
            >>> with workflows.interactive_session(
            ...     "olex2", "1.5-alpha",
            ...     {"input_file": {"data_file_id": file_id}}
            ... ) as session_id:
            ...     print(f"Session at: http://localhost:12004/vnc.html")
            ...     input("Press enter when done...")
            ... # Session automatically closed here
        """
        # Create session
        args = CreateInteractiveSessionParametersCommandArguments.from_dict(arguments)
        params = CreateInteractiveSessionParameters(
            application_slug, 
            application_version, 
            args
        )
        
        response = interactive_sessions.create_interactive_session.sync(
            client=self.client, 
            body=params
        )
        
        if isinstance(response, QCrBoxErrorResponse) or response is None:
            raise RuntimeError(f"Failed to create interactive session: {response}")
        
        session_id = response.payload.interactive_session_id
        
        # Wait for startup
        if startup_delay > 0:
            time.sleep(startup_delay)
        
        try:
            yield session_id
        finally:
            # Always close session
            interactive_sessions.close_interactive_session.sync(
                client=self.client, 
                id=session_id
            )
    
    # ==================== Error Handling Utilities ====================
    
    @staticmethod
    def is_error(response: Any) -> bool:
        """Check if response is an error.
        
        Args:
            response: Any API response
            
        Returns:
            True if error, False otherwise
        """
        return isinstance(response, QCrBoxErrorResponse) or response is None
    
    @staticmethod
    def raise_on_error(response: Any, context: str = "Operation"):
        """Raise exception if response is an error.
        
        Args:
            response: API response
            context: Context string for error message
            
        Raises:
            RuntimeError: If response is an error
        """
        if QCrBoxWorkflows.is_error(response):
            raise RuntimeError(f"{context} failed: {response}")



class QCrBoxAPIAdapter:
    def __init__(self, base_url: str):
        self.client = Client(base_url)
    
    def health_check(self) -> bool:
      try:
        response = healthz.sync(client=self.client)
        return response and response.status == "ok"
      except httpx.ConnectError:
        print("Failed to connect: The server is unreachable.")
      except httpx.TimeoutException:
        print("Failed to connect: The request timed out.")
      except Exception as e:
        print(f"An unexpected error occurred: {e}")
      return False
    

def upload_file_as_dataset(client: Client, file_content: str|bytes, file_name: str) -> tuple[str, str]:
  """
  Upload a CIF file to QCrBox and create a dataset.

  Args:
      client: The QCrBox API client
      file_content: The file content as a string or bytes
      file_name: The name for the uploaded file

  Returns
  -------
      Tuple of (dataset_id, data_file_id)

  Raises
  ------
      TypeError: If the upload fails

  """
  if isinstance(file_content, str):
      fileb = file_content.encode("utf-8")
  else:
      fileb = file_content
  file = File(io.BytesIO(fileb), file_name)
  upload_payload = CreateDatasetBody(file)

  response = create_dataset.sync(client=client, body=upload_payload)
  if isinstance(response, QCrBoxErrorResponse) or response is None:
      raise TypeError("Failed to upload file", response)

  dataset_id = response.payload.datasets[0].qcrbox_dataset_id
  data_file_id = response.payload.datasets[0].data_files[file_name].qcrbox_file_id

  return dataset_id, data_file_id