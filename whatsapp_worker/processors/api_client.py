"""
API Client for Internal Server Endpoints.

This module provides an HTTP client for the whatsapp_worker to interact
with the server's internal API endpoints instead of direct database access.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx

from whatsapp_worker.config import config

logger = logging.getLogger(__name__)


class InternalsAPIError(Exception):
    """Exception raised when internal API call fails."""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API Error {status_code}: {detail}")


class InternalsAPIClient:
    """
    HTTP client for internal server API calls.
    
    All database operations from whatsapp_worker should go through this client.
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        secret_key: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.base_url = (base_url or config.INTERNAL_API_BASE_URL).rstrip("/")
        self.secret_key = secret_key or config.INTERNAL_API_SECRET
        self.timeout = timeout
        self._client: Optional[httpx.Client] = None
    
    @property
    def client(self) -> httpx.Client:
        """Lazy-initialize HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.base_url,
                headers={"X-Internal-Secret": self.secret_key},
                timeout=self.timeout,
            )
        return self._client
    
    def close(self):
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None
    
    def _handle_response(self, response: httpx.Response) -> Any:
        """Handle API response and raise on errors."""
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise InternalsAPIError(response.status_code, detail)
        
        if response.status_code == 204:
            return None
        
        # Handle empty responses
        if not response.content:
            return None
            
        return response.json()
    
    # ========================================
    # Integration/Organization Methods
    # ========================================
    
    def get_integration_with_org(self, phone_number_id: str) -> Optional[Dict]:
        """
        Get WhatsApp integration and organization data by phone_number_id.
        
        Returns None if not found.
        """
        try:
            response = self.client.get(
                f"/internals/whatsapp/by-phone-number-id/{phone_number_id}/with-org"
            )
            return self._handle_response(response)
        except InternalsAPIError as e:
            if e.status_code == 404:
                return None
            raise
    
    # ========================================
    # Lead Methods
    # ========================================
    
    def get_lead_by_phone(
        self, organization_id: UUID, phone: str
    ) -> Optional[Dict]:
        """Get lead by organization ID and phone number."""
        response = self.client.get(
            "/internals/leads/by-phone",
            params={"organization_id": str(organization_id), "phone": phone}
        )
        result = self._handle_response(response)
        # The endpoint returns null if not found
        return result if result else None
    
    def create_lead(
        self,
        organization_id: UUID,
        phone: str,
        name: Optional[str] = None
    ) -> Dict:
        """Create a new lead."""
        response = self.client.post(
            "/internals/leads",
            json={
                "organization_id": str(organization_id),
                "phone": phone,
                "name": name,
            }
        )
        return self._handle_response(response)
    
    def update_lead(self, lead_id: UUID, name: Optional[str] = None) -> Dict:
        """Update lead details."""
        params = {}
        if name is not None:
            params["name"] = name
        response = self.client.patch(
            f"/internals/leads/{lead_id}",
            params=params
        )
        return self._handle_response(response)
    
    def get_or_create_lead(
        self,
        organization_id: UUID,
        phone: str,
        name: Optional[str] = None
    ) -> Dict:
        """Get existing lead or create new one."""
        lead = self.get_lead_by_phone(organization_id, phone)
        
        if lead:
            # Update name if provided and not already set
            if name and not lead.get("name"):
                lead = self.update_lead(UUID(lead["id"]), name=name)
            return lead
        
        return self.create_lead(organization_id, phone, name)
    
    # ========================================
    # Conversation Methods
    # ========================================
    
    def get_conversation_by_lead(
        self, organization_id: UUID, lead_id: UUID
    ) -> Optional[Dict]:
        """Get the most recent conversation for a lead."""
        response = self.client.get(
            "/internals/conversations/by-lead",
            params={
                "organization_id": str(organization_id),
                "lead_id": str(lead_id),
            }
        )
        result = self._handle_response(response)
        return result if result else None
    
    def create_conversation(
        self, organization_id: UUID, lead_id: UUID
    ) -> Dict:
        """Create a new conversation."""
        response = self.client.post(
            "/internals/conversations",
            json={
                "organization_id": str(organization_id),
                "lead_id": str(lead_id),
            }
        )
        return self._handle_response(response)
    
    def get_conversation(self, conversation_id: UUID) -> Dict:
        """Get conversation by ID."""
        response = self.client.get(f"/internals/conversations/{conversation_id}")
        return self._handle_response(response)
    
    def update_conversation(self, conversation_id: UUID, **updates) -> Dict:
        """Update conversation state."""
        # Convert enums to strings if present
        payload = {}
        for key, value in updates.items():
            if hasattr(value, 'value'):  # Enum
                payload[key] = value.value
            elif isinstance(value, UUID):
                payload[key] = str(value)
            elif isinstance(value, datetime):
                payload[key] = value.isoformat()
            else:
                payload[key] = value
        
        response = self.client.patch(
            f"/internals/conversations/{conversation_id}",
            json=payload
        )
        return self._handle_response(response)
    
    def get_or_create_conversation(
        self, organization_id: UUID, lead_id: UUID
    ) -> tuple[Dict, bool]:
        """
        Get existing conversation or create new one.
        
        Returns:
            Tuple of (conversation_dict, is_new)
        """
        conv = self.get_conversation_by_lead(organization_id, lead_id)
        if conv:
            return conv, False
        return self.create_conversation(organization_id, lead_id), True
    
    def get_conversation_messages(
        self, conversation_id: UUID, limit: int = 3
    ) -> List[Dict]:
        """Get last N messages for pipeline context."""
        response = self.client.get(
            f"/internals/conversations/{conversation_id}/messages",
            params={"limit": limit}
        )
        return self._handle_response(response)
    
    # ========================================
    # Message Methods
    # ========================================
    
    def store_incoming_message(
        self,
        conversation_id: UUID,
        lead_id: UUID,
        content: str
    ) -> Dict:
        """Store incoming lead message and update conversation timestamps."""
        response = self.client.post(
            "/internals/messages/incoming",
            json={
                "conversation_id": str(conversation_id),
                "lead_id": str(lead_id),
                "content": content,
            }
        )
        return self._handle_response(response)
    
    def store_outgoing_message(
        self,
        conversation_id: UUID,
        lead_id: UUID,
        content: str,
        message_from: str  # "bot" or "human"
    ) -> Dict:
        """Store outgoing bot/human message and update conversation timestamps."""
        response = self.client.post(
            "/internals/messages/outgoing",
            json={
                "conversation_id": str(conversation_id),
                "lead_id": str(lead_id),
                "content": content,
                "message_from": message_from,
            }
        )
        return self._handle_response(response)

    def send_bot_message(
        self,
        organization_id: UUID,
        conversation_id: UUID,
        content: str,
        access_token: str,
        phone_number_id: str,
        version: str = "v18.0",
        to: Optional[str] = None
    ) -> Dict:
        """
        Send a WhatsApp message via the server's /message/send_bot endpoint.
        This handles both sending to WhatsApp and storing in the DB.
        """
        payload = {
            "organization_id": str(organization_id),
            "conversation_id": str(conversation_id),
            "content": content,
            "access_token": access_token,
            "phone_number_id": phone_number_id,
            "version": version,
        }
        if to:
            payload["to"] = to
            
        response = self.client.post("/messages/send_bot", json=payload)
        return self._handle_response(response)
    
    # ========================================
    # Scheduled Action Methods
    # ========================================
    
    def get_due_actions(self, limit: int = 50) -> List[Dict]:
        """Get pending scheduled actions that are due."""
        response = self.client.get(
            "/internals/scheduled-actions/due",
            params={"limit": limit}
        )
        return self._handle_response(response)
    
    def create_scheduled_action(
        self,
        conversation_id: UUID,
        organization_id: UUID,
        scheduled_at: datetime,
        action_type: str = "followup",
        action_context: Optional[str] = None
    ) -> Dict:
        """Create a new scheduled action."""
        response = self.client.post(
            "/internals/scheduled-actions",
            json={
                "conversation_id": str(conversation_id),
                "organization_id": str(organization_id),
                "scheduled_at": scheduled_at.isoformat(),
                "action_type": action_type,
                "action_context": action_context,
            }
        )
        return self._handle_response(response)
    
    def get_scheduled_action(self, action_id: UUID) -> Dict:
        """Get scheduled action by ID."""
        response = self.client.get(f"/internals/scheduled-actions/{action_id}")
        return self._handle_response(response)
    
    def update_action_status(
        self,
        action_id: UUID,
        status: str,
        executed_at: Optional[datetime] = None
    ) -> Dict:
        """Update scheduled action status."""
        payload = {"status": status}
        if executed_at:
            payload["executed_at"] = executed_at.isoformat()
        
        response = self.client.patch(
            f"/internals/scheduled-actions/{action_id}",
            json=payload
        )
        return self._handle_response(response)
    
    def cancel_pending_actions(self, conversation_id: UUID) -> int:
        """Cancel all pending scheduled actions for a conversation."""
        response = self.client.post(
            "/internals/scheduled-actions/cancel-pending",
            params={"conversation_id": str(conversation_id)}
        )
        result = self._handle_response(response)
        return result.get("cancelled", 0)
    
    def get_followup_context(self, action_id: UUID) -> Dict:
        """Get full context needed to process a scheduled followup."""
        response = self.client.get(
            f"/internals/scheduled-actions/{action_id}/context"
        )
        return self._handle_response(response)
    
    # ========================================
    # Pipeline Event Methods
    # ========================================
    
    def log_pipeline_event(
        self,
        conversation_id: UUID,
        event_type: str,
        pipeline_step: Optional[str] = None,
        input_summary: Optional[str] = None,
        output_summary: Optional[str] = None,
        latency_ms: Optional[int] = None,
        tokens_used: Optional[int] = None
    ) -> Dict:
        """Log a pipeline execution event."""
        response = self.client.post(
            "/internals/conversation-events",
            json={
                "conversation_id": str(conversation_id),
                "event_type": event_type,
                "pipeline_step": pipeline_step,
                "input_summary": input_summary,
                "output_summary": output_summary,
                "latency_ms": latency_ms,
                "tokens_used": tokens_used,
            }
        )
        return self._handle_response(response)
    
    # ========================================
    # Utility Methods
    # ========================================
    
    def reset_followup_counts(self) -> int:
        """Reset daily followup counts for all conversations."""
        response = self.client.post("/internals/conversations/reset-followup-counts")
        result = self._handle_response(response)
        return result.get("reset", 0)
    
    # ========================================
    # WebSocket Event Methods
    # ========================================
    
    def emit_cta_initiated(
        self,
        conversation_id: UUID,
        organization_id: UUID,
        cta_type: str,
        cta_name: str | None = None,
        scheduled_time: str | None = None,
    ) -> Dict:
        """Emit CTA initiated WebSocket event to frontend."""
        response = self.client.post(
            "/internals/emit-cta-initiated",
            params={
                "conversation_id": str(conversation_id),
                "organization_id": str(organization_id),
                "cta_type": cta_type,
                "cta_name": cta_name,
                "scheduled_time": scheduled_time,
            }
        )
        return self._handle_response(response)
    
    def emit_human_attention(
        self,
        conversation_id: UUID,
        organization_id: UUID,
    ) -> Dict:
        """Emit human attention required WebSocket event to frontend."""
        response = self.client.post(
            "/internals/emit-human-attention",
            params={
                "conversation_id": str(conversation_id),
                "organization_id": str(organization_id),
            }
        )
        return self._handle_response(response)


# Module-level singleton for convenience
api_client = InternalsAPIClient()
