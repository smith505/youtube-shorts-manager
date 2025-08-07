import requests
import json

# Example of fixing the API call by removing session_id from metadata

def make_api_call():
    # Before (causes error):
    # payload = {
    #     "data": "your_data",
    #     "metadata": {
    #         "session_id": "some_session_id",  # Remove this line
    #         "other_field": "value"
    #     }
    # }
    
    # After (fixed):
    payload = {
        "data": "your_data",
        "metadata": {
            "other_field": "value"
        }
    }
    
    try:
        # Replace with your actual API endpoint
        response = requests.post("https://your-api-endpoint.com", json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error: {e}")
        return None

if __name__ == "__main__":
    result = make_api_call()
    if result:
        print("API call successful:", result)