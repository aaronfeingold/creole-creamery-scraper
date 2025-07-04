#!/usr/bin/env python3
"""
Local testing script for the Creole Creamery scraper.
Run this to test the scraper logic before deploying to Lambda.
"""

import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from lambda_function import lambda_handler


def test_scraper():
    """Test the scraper locally."""
    # Load environment variables from .env file
    load_dotenv()

    # Check required environment variables
    required_vars = ["NEON_DATABASE_URL", "OPENAI_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"Missing required environment variables: {', '.join(missing_vars)}")
        print("Please create a .env file with the required variables.")
        sys.exit(1)

    print("Testing Creole Creamery scraper locally...")
    print(f"Database URL: {os.getenv('NEON_DATABASE_URL')[:50]}...")
    print(f"OpenAI API Key: {os.getenv('OPENAI_API_KEY')[:20]}...")
    print()

    # Run the lambda handler
    try:
        result = lambda_handler({}, {})

        print("Test completed successfully!")
        print(f"Status Code: {result['statusCode']}")

        if result["statusCode"] == 200:
            import json

            body = json.loads(result["body"])
            print("Results:")
            print(f"  - Total entries processed: {body.get('message', 'N/A')}")
            print(f"  - New entries saved: {body.get('new_entries_saved', 'N/A')}")
            print(f"  - Last saved number: {body.get('last_saved_number', 'N/A')}")
            print(
                f"  - Highest number found: {body.get('highest_number_found', 'N/A')}"
            )
        else:
            import json

            body = json.loads(result["body"])
            print(f"Error: {body.get('error', 'Unknown error')}")

    except Exception as e:
        print(f"Test failed with error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    test_scraper()
