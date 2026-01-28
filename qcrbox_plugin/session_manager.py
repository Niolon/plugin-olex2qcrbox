"""Interactive session management for QCrBox."""

import time
import webbrowser
from typing import Optional, Tuple

from qcrboxapiclient.api.interactive_sessions import (
    create_interactive_session,
    close_interactive_session,
    list_interactive_sessions
)
from qcrboxapiclient.models import (
    CreateInteractiveSessionParameters,
    CreateInteractiveSessionParametersCommandArguments,
    QCrBoxErrorResponse
)


class SessionManager:
    """Manages QCrBox interactive sessions lifecycle."""
    
    def __init__(self, client, qcrbox_url: str):
        """Initialize session manager.
        
        Args:
            client: QCrBox API client
            qcrbox_url: Base URL of QCrBox server
        """
        self.client = client
        self.qcrbox_url = qcrbox_url
    
    @staticmethod
    def is_command_interactive(command_obj) -> bool:
        """Check if a command is interactive based on its metadata.
        
        Args:
            command_obj: Command object from API
            
        Returns:
            True if command is interactive
        """
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
    
    def start_interactive_session(
        self,
        command_obj,
        arguments: dict
    ) -> Optional[str]:
        """Start an interactive session and open browser to VNC URL.
        
        Args:
            command_obj: Command object with application and version info
            arguments: Command arguments dictionary
            
        Returns:
            Session ID on success, None on failure
        """
        print(f"Starting interactive session: {command_obj.name} ({command_obj.application})")
        print(f"Arguments: {arguments}")
        
        try:
            # Create session parameters
            args = CreateInteractiveSessionParametersCommandArguments.from_dict(arguments)
            params = CreateInteractiveSessionParameters(
                command_obj.application,
                command_obj.version,
                args
            )
            
            # Create interactive session
            response = create_interactive_session.sync(
                client=self.client,
                body=params
            )
            
            if isinstance(response, QCrBoxErrorResponse) or response is None:
                print(f"Failed to create interactive session: {response}")
                return None
            
            session_id = response.payload.interactive_session_id
            print(f"Interactive session created! Session ID: {session_id}")
            
            # Construct VNC URL from stored qcrbox_url
            qcrbox_base = self.qcrbox_url.replace('http://', '').replace('https://', '').split(':')[0]
            vnc_url = f"http://{qcrbox_base}:12004/vnc.html?path=vnc&autoconnect=true&resize=remote&reconnect=true&show_dot=true"
            
            print(f"Opening browser to: {vnc_url}")
            
            # Open browser to VNC URL
            import subprocess
            webbrowser.open(vnc_url)
            
            return session_id
            
        except Exception as e:
            print(f"Failed to start interactive session: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def close_interactive_session(self, session_id: str) -> bool:
        """Close an interactive session.
        
        Args:
            session_id: ID of session to close
            
        Returns:
            True on success, False on failure
        """
        if not session_id:
            print("No session ID provided")
            return False
        
        print(f"Closing interactive session {session_id}...")
        
        try:
            response = close_interactive_session.sync(
                client=self.client,
                id=session_id
            )
            
            if isinstance(response, QCrBoxErrorResponse):
                print(f"Failed to close interactive session: {response}")
                return False
            
            print("Interactive session closed successfully")
            
            # Wait a moment for the session to finalize
            import time
            time.sleep(2)
            
            return True
            
        except Exception as e:
            print(f"Failed to close interactive session: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def list_active_sessions(self) -> list:
        """List all active interactive sessions on the server.
        
        Returns:
            List of session objects
        """
        try:
            response = list_interactive_sessions.sync(client=self.client)
            
            if hasattr(response, 'payload') and hasattr(response.payload, 'interactive_sessions'):
                sessions = response.payload.interactive_sessions
                print(f"\n{'='*60}")
                print(f"Active Interactive Sessions: {len(sessions)}")
                print(f"{'='*60}")
                
                for i, session in enumerate(sessions, 1):
                    print(f"{i}. Session ID: {session.session_id}")
                    print(f"   Status: {session.status if hasattr(session, 'status') else 'unknown'}")
                    print(f"   Created: {session.created_at if hasattr(session, 'created_at') else 'unknown'}")
                    print()
                
                print(f"{'='*60}\n")
                return sessions
            else:
                print("No active sessions found")
                return []
                
        except Exception as e:
            print(f"Failed to list active sessions: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def close_all_sessions(self) -> Tuple[int, int]:
        """Close all active interactive sessions on the server.
        
        Returns:
            Tuple of (closed_count, failed_count)
        """
        sessions = self.list_active_sessions()
        
        if not sessions:
            print("No sessions to close")
            return (0, 0)
        
        closed_count = 0
        failed_count = 0
        
        for session in sessions:
            try:
                print(f"Closing session {session.session_id}...")
                close_interactive_session.sync(
                    client=self.client,
                    id=session.session_id
                )
                print(f"  ✓ Closed successfully")
                closed_count += 1
            except Exception as e:
                print(f"  ✗ Failed to close: {e}")
                failed_count += 1
        
        print(f"\nClosed {closed_count} sessions, {failed_count} failures")
        return (closed_count, failed_count)
