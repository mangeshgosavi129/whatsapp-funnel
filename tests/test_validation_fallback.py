
import json
import logging
from unittest.mock import MagicMock, patch
from llm.api_helpers import make_api_call
from openai import BadRequestError

# Configure logging to see our error log
logging.basicConfig(level=logging.INFO)

def test_json_validation_failure_handling():
    print("Testing JSON validation failure handling...")
    
    # Mock response data for BadRequestError
    error_response_data = {
        "error": {
            "message": "Generated JSON does not match the expected schema.",
            "type": "invalid_request_error",
            "code": "json_validate_failed",
            "failed_generation": '{"action":"send_now","confidence":0.97,"new_stage":"interest_exploration"}'
        }
    }
    
    # Create a mock response object
    mock_response = MagicMock()
    mock_response.json.return_value = error_response_data
    mock_response.status_code = 400
    
    # Create the BadRequestError
    mock_error = BadRequestError(
        message="Bad Request",
        response=mock_response,
        body=error_response_data
    )
    
    # Patch the OpenAI client.chat.completions.create to raise the mock error
    with patch("llm.api_helpers.client.chat.completions.create") as mock_create:
        mock_create.side_effect = mock_error
        
        try:
            result = make_api_call(
                messages=[{"role": "user", "content": "test"}],
                step_name="TestStep"
            )
            
            print(f"Result: {result}")
            expected = json.loads(error_response_data["error"]["failed_generation"])
            assert result == expected
            print("SUCCESS: make_api_call correctly extracted failed_generation.")
            
        except Exception as e:
            print(f"FAILED: make_api_call raised an exception instead of returning failed_generation: {e}")
            raise

if __name__ == "__main__":
    test_json_validation_failure_handling()
