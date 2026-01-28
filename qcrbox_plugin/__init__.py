"""QCrBox integration package for Olex2."""

from .api_adapter import (
    QCrBoxAPIAdapter,
    QCrBoxWorkflows,
    CalculationStatus,
    CommandExecution,
    UploadedDataset,
    upload_file_as_dataset,
)

from .cif_utils import (
    convert_cif_ddl2_to_ddl1,
    extract_cif_from_json_response,
    validate_cif_data_name,
)

from .state import PluginState

from . import gui_controller

from .session_manager import SessionManager

from .calculation_runner import CalculationRunner

from . import tests

__all__ = [
    # API & Workflows
    'QCrBoxAPIAdapter',
    'QCrBoxWorkflows',
    'CalculationStatus',
    'CommandExecution',
    'UploadedDataset',
    'upload_file_as_dataset',
    # CIF Utilities
    'convert_cif_ddl2_to_ddl1',
    'extract_cif_from_json_response',
    'validate_cif_data_name',
    # State Management
    'PluginState',
    # GUI Controller (functions)
    'gui_controller',
    # Session Manager
    'SessionManager',
    # Calculation Runner
    'CalculationRunner',
    # Testing
    'tests',
]
