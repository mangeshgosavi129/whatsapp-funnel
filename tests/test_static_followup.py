import os
import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4, UUID
from datetime import datetime, timezone

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.enums import ConversationMode, ConversationStage
from llm.schemas import PipelineResult, ClassifyOutput, RiskFlags, GenerateOutput

# Avoid top-level imports that might capture unpatched singletons
# import whatsapp_worker.tasks
# import whatsapp_worker.main

def test_realtime_followup_processing():
    print("Testing real-time followup processing workflow...")
    
    # Patch the api_client in the tasks module specifically
    with patch('whatsapp_worker.tasks.api_client') as mock_api:
        from whatsapp_worker.tasks import process_due_followups
        
        # Setup mock data for get_due_followups
        conv_id = uuid4()
        lead_id = uuid4()
        org_id = uuid4()
        
        mock_api.get_due_followups.return_value = [
            {
                "followup_number": 1,
                "conversation": {"id": str(conv_id), "mode": "bot", "stage": "greeting", "followup_count_24h": 0},
                "lead": {"id": str(lead_id), "phone": "123456789"},
                "organization_id": str(org_id),
                "organization_name": "Test Org",
                "access_token": "test_token",
                "phone_number_id": "phone_id",
                "version": "v18.0",
            }
        ]
        
        # Mock other dependencies in tasks
        with patch('whatsapp_worker.tasks.run_followup_pipeline') as mock_pipeline, \
             patch('whatsapp_worker.tasks.handle_pipeline_result') as mock_handle_res, \
             patch('whatsapp_worker.tasks.build_pipeline_context'):
            
            mock_pipeline.return_value = PipelineResult(
                brain=ClassifyOutput(
                    implementation_plan="Send a followup nudge",
                    thought_process="Thinking...",
                    situation_summary="Nudge",
                    intent_level="unknown",
                    user_sentiment="neutral",
                    risk_flags=RiskFlags(),
                    action="wait_schedule",
                    new_stage="greeting",
                    should_respond=True,
                    confidence=1.0
                ),
                mouth=GenerateOutput(message_text="Followup text")
            )
            mock_handle_res.return_value = "Followup text"
            
            # Execute
            process_due_followups()
            
            # Verify API interaction
            mock_api.get_due_followups.assert_called_once()
            mock_api.send_bot_message.assert_called_once_with(
                organization_id=org_id,
                conversation_id=conv_id,
                content="Followup text",
                access_token="test_token",
                phone_number_id="phone_id",
                version="v18.0",
                to="123456789"
            )
            print("✅ Real-time followup processed and sent successfully")

def test_no_scheduling_on_message():
    print("\nTesting that no scheduling/deletion happens during normal message processing...")
    
    with patch('whatsapp_worker.main.api_client') as mock_api:
        from whatsapp_worker.main import process_message
        
        # Setup mock data
        organization_id = uuid4()
        conversation_id = uuid4()
        lead_id = uuid4()
        
        mock_api.get_integration_with_org.return_value = {
            "organization_id": str(organization_id),
            "organization_name": "Test Org",
            "access_token": "test_token",
            "version": "v18.0",
        }
        mock_api.get_or_create_lead.return_value = {"id": str(lead_id), "phone": "1"}
        mock_api.get_or_create_conversation.return_value = ({"id": str(conversation_id), "mode": "bot"}, False)
        mock_api.get_conversation.return_value = {"id": str(conversation_id), "mode": "bot"}
        
        with patch('whatsapp_worker.main.run_pipeline') as mock_pipeline, \
             patch('whatsapp_worker.main.build_pipeline_context'), \
             patch('whatsapp_worker.main.handle_pipeline_result'), \
             patch('llm.steps.memory.run_memory'):
            
            mock_pipeline.return_value = MagicMock()
            
            # Execute
            process_message("phone_id", "123", "Name", "Hello")
            
            # Verify NO calls to legacy methods
            assert not hasattr(mock_api, 'create_scheduled_action') or mock_api.create_scheduled_action.call_count == 0
            assert not hasattr(mock_api, 'delete_pending_actions') or mock_api.delete_pending_actions.call_count == 0
            print("✅ No legacy scheduling or deletion calls in process_message")

if __name__ == "__main__":
    try:
        test_realtime_followup_processing()
        test_no_scheduling_on_message()
        print("\nALL TESTS PASSED")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
