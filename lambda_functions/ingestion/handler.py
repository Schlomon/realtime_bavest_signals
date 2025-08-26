"""
Bavest API Ingestion Lambda Function

This function fetches financial signals from the Bavest API and sends them to a Kinesis stream.
It's triggered by EventBridge on a scheduled basis (every 5 minutes by default).
"""

import json
import boto3
import requests
import os
from datetime import datetime
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
kinesis = boto3.client('kinesis')

def handler(event, context):
    """
    Main Lambda handler function
    
    Args:
        event: EventBridge event or manual trigger
        context: Lambda context object
        
    Returns:
        dict: Response with status code and body
    """
    try:
        logger.info("Starting Bavest API ingestion")
        
        # Get environment variables
        bavest_api_url = os.environ.get('BAVEST_API_URL')
        api_key = os.environ.get('BAVEST_API_KEY')
        kinesis_stream_name = os.environ.get('KINESIS_STREAM_NAME')
        
        if not all([bavest_api_url, api_key, kinesis_stream_name]):
            raise ValueError("Missing required environment variables")
        
        # Fetch data from Bavest API
        bavest_data = fetch_bavest_signals(bavest_api_url, api_key)
        
        # Send to Kinesis
        kinesis_response = send_to_kinesis(bavest_data, kinesis_stream_name)
        
        logger.info(f"Successfully processed {len(bavest_data) if isinstance(bavest_data, list) else 1} records")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Data successfully ingested and sent to Kinesis',
                'records_processed': len(bavest_data) if isinstance(bavest_data, list) else 1,
                'kinesis_sequence_numbers': kinesis_response
            })
        }
        
    except Exception as e:
        logger.error(f"Error in ingestion: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Failed to ingest Bavest data'
            })
        }


def fetch_bavest_signals(api_url, api_key):
    """
    Fetch financial signals from Bavest API
    
    Args:
        api_url (str): Bavest API endpoint URL
        api_key (str): API authentication key
        
    Returns:
        dict or list: API response data
    """
    payload = {
        "isin": "DE0005104400"
    }
    headers = {
        'x-api-key': api_key,
        'accept': 'application/json',
        'content-type': 'application/json',
    }
    
    logger.info(f"Fetching data from: {api_url}")
    
    try:
        response = requests.post(f'{api_url}/quote', json=payload, headers=headers, timeout=25)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"Successfully fetched data from Bavest API")
        
        return data
        
    except requests.exceptions.Timeout:
        logger.error("Request to Bavest API timed out")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"Request to Bavest API failed: {str(e)}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {str(e)}")
        raise


def send_to_kinesis(data, stream_name):
    """
    Send data to Kinesis stream
    
    Args:
        data (dict or list): Data to send to Kinesis
        stream_name (str): Name of the Kinesis stream
        
    Returns:
        list: List of sequence numbers from Kinesis responses
    """
    sequence_numbers = []
    
    # Ensure data is a list for consistent processing
    if not isinstance(data, list):
        data = [data]
    
    for record in data:
        # Add metadata
        enriched_record = {
            'data': record,
            'ingestion_timestamp': datetime.utcnow().isoformat(),
            'source': 'bavest_api',
            'lambda_request_id': os.environ.get('AWS_REQUEST_ID', 'unknown')
        }
        
        # Determine partition key (use a fixed key since we're querying specific ISIN)
        partition_key = "DE0005104400"  # The ISIN we're querying
        
        try:
            response = kinesis.put_record(
                StreamName=stream_name,
                Data=json.dumps(enriched_record),
                PartitionKey=partition_key
            )
            
            sequence_numbers.append(response['SequenceNumber'])
            logger.info(f"Sent record to Kinesis with sequence number: {response['SequenceNumber']}")
            
        except Exception as e:
            logger.error(f"Failed to send record to Kinesis: {str(e)}")
            raise
    
    return sequence_numbers


def validate_bavest_data(data):
    """
    Validate the structure of data received from Bavest API
    
    Args:
        data (dict or list): Data to validate
        
    Returns:
        bool: True if data is valid
    """
    if isinstance(data, list):
        return all(isinstance(item, dict) for item in data)
    elif isinstance(data, dict):
        return True
    else:
        return False
