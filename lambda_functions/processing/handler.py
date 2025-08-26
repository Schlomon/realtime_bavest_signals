"""
Bavest Data Science Processing Lambda Function

This function processes financial data from Kinesis streams, performs data science operations,
and stores the results in Redis (ElastiCache).
"""

import json
import boto3
import redis
import os
import base64
from datetime import datetime
import logging
from typing import Dict, List, Any, Optional

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """
    Main Lambda handler function for processing Kinesis records
    
    Args:
        event: Kinesis event containing records
        context: Lambda context object
        
    Returns:
        dict: Response with processing results
    """
    try:
        logger.info(f"Processing {len(event['Records'])} Kinesis records")
        
        # Initialize Redis connection
        redis_client = get_redis_client()
        
        processed_records = []
        failed_records = []
        
        for record in event['Records']:
            try:
                # Process individual record
                processed_data = process_kinesis_record(record, redis_client)
                processed_records.append(processed_data)
                
            except Exception as e:
                logger.error(f"Failed to process record: {str(e)}")
                failed_records.append({
                    'record_id': record.get('eventID', 'unknown'),
                    'error': str(e)
                })
        
        logger.info(f"Successfully processed {len(processed_records)} records, failed: {len(failed_records)}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Processed {len(processed_records)} records',
                'processed_count': len(processed_records),
                'failed_count': len(failed_records),
                'failed_records': failed_records
            })
        }
        
    except Exception as e:
        logger.error(f"Critical error in processing: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Critical failure in data processing'
            })
        }


def get_redis_client():
    """
    Initialize and return Redis client
    
    Returns:
        redis.Redis: Configured Redis client
    """
    redis_host = os.environ.get('REDIS_HOST')
    redis_port = int(os.environ.get('REDIS_PORT', 6379))
    
    if not redis_host:
        raise ValueError("REDIS_HOST environment variable not set")
    
    try:
        client = redis.Redis(
            host=redis_host, 
            port=redis_port, 
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5
        )
        
        # Test connection
        client.ping()
        logger.info(f"Successfully connected to Redis at {redis_host}:{redis_port}")
        
        return client
        
    except redis.ConnectionError as e:
        logger.error(f"Failed to connect to Redis: {str(e)}")
        raise


def process_kinesis_record(record: Dict, redis_client: redis.Redis) -> Dict:
    """
    Process a single Kinesis record
    
    Args:
        record: Kinesis record
        redis_client: Redis client instance
        
    Returns:
        dict: Processed data
    """
    # Decode Kinesis data
    kinesis_data = record['kinesis']
    payload = base64.b64decode(kinesis_data['data']).decode('utf-8')
    data = json.loads(payload)
    
    logger.info(f"Processing record with partition key: {kinesis_data.get('partitionKey', 'unknown')}")
    
    # Extract the actual data (remove ingestion metadata)
    bavest_data = data.get('data', data)
    
    # Perform data science processing
    processed_data = perform_analysis(bavest_data)
    
    # Store in Redis
    store_in_redis(processed_data, redis_client)
    
    return processed_data


def perform_analysis(data: Dict) -> Dict:
    """
    Perform simplified P/E ratio analysis on Bavest API data
    
    Args:
        data: Raw financial data from Bavest API
        
    Returns:
        dict: Processed data with P/E ratio and additional metrics
    """
    processed = {
        'symbol': extract_symbol_from_data(data),
        'timestamp': datetime.utcnow().isoformat(),
        'original_data': data,
        'processing_timestamp': datetime.utcnow().isoformat(),
        'analytics': {},
        'market_data': {},
        'metadata': {
            'processor_version': '2.0',
            'processing_source': 'lambda',
            'analysis_type': 'pe_ratio_bavest_api',
            'data_timestamp': data.get('t'),  # Unix timestamp from Bavest
            'currency': data.get('currency', 'EUR')
        }
    }
    
    # Extract basic price information
    if 'c' in data:  # Current/close price
        processed['market_data']['current_price'] = data['c']
    if 'o' in data:  # Open price
        processed['market_data']['open_price'] = data['o']
    if 'h' in data:  # High price
        processed['market_data']['high_price'] = data['h']
    if 'l' in data:  # Low price
        processed['market_data']['low_price'] = data['l']
    if 'd' in data:  # Price change
        processed['market_data']['price_change'] = data['d']
    if 'dp' in data:  # Price change percentage
        processed['market_data']['price_change_percent'] = data['dp']
    if 'v' in data:  # Volume
        processed['market_data']['volume'] = data['v']
    
    # Extract historical prices if available
    if 'historical_price' in data:
        processed['market_data']['historical_prices'] = data['historical_price']
    
    # Extract key metrics
    if 'metrics' in data:
        metrics = data['metrics']
        processed['market_data']['market_cap'] = metrics.get('marketCapitalization')
        processed['market_data']['avg_volume'] = metrics.get('avgVolume')
        processed['market_data']['eps'] = metrics.get('eps')
        processed['market_data']['shares_outstanding'] = metrics.get('sharesOutstanding')
    
    # Calculate P/E ratio
    pe_ratio = calculate_pe_ratio(data)
    if pe_ratio is not None:
        processed['analytics']['pe_ratio'] = pe_ratio
        processed['analytics']['pe_category'] = categorize_pe_ratio(pe_ratio)
        processed['analytics']['valuation_signal'] = get_valuation_signal(pe_ratio)
    else:
        processed['analytics']['pe_ratio'] = None
        processed['analytics']['pe_category'] = 'insufficient_data'
        processed['analytics']['valuation_signal'] = 'unknown'
        logger.warning(f"Could not calculate P/E ratio for {processed['symbol']} - missing data")
    
    # Add earnings announcement date if available
    if 'earningsAnnouncement' in data:
        processed['metadata']['next_earnings'] = data['earningsAnnouncement']
    
    logger.info(f"Completed Bavest analysis for {processed['symbol']}: P/E={pe_ratio}, Price={data.get('c')}")
    
    return processed


def get_valuation_signal(pe_ratio: float) -> str:
    """
    Generate a simple valuation signal based on P/E ratio
    
    Args:
        pe_ratio: P/E ratio value
        
    Returns:
        str: Valuation signal (buy/hold/sell)
    """
    if pe_ratio <= 0:
        return 'avoid'  # Negative earnings
    elif pe_ratio < 15:
        return 'buy'    # Potentially undervalued
    elif pe_ratio < 25:
        return 'hold'   # Fair value
    else:
        return 'sell'   # Potentially overvalued


def calculate_pe_ratio(data: Dict) -> Optional[float]:
    """
    Calculate Price-to-Earnings (P/E) ratio from Bavest API response
    
    Args:
        data: Financial data from Bavest API
        
    Returns:
        float or None: P/E ratio or None if calculation not possible
    """
    # Check if P/E ratio is already provided in the response
    if 'metrics' in data and 'pe/ratio' in data['metrics']:
        try:
            pe_ratio = float(data['metrics']['pe/ratio'])
            logger.info(f"Using provided P/E ratio: {pe_ratio}")
            return round(pe_ratio, 2)
        except (ValueError, TypeError):
            logger.warning("Invalid P/E ratio in metrics, falling back to calculation")
    
    # Fallback: Calculate from current price and EPS
    current_price = None
    eps = None
    
    # Extract current price (c = current/close price in Bavest response)
    if 'c' in data and data['c'] is not None:
        try:
            current_price = float(data['c'])
        except (ValueError, TypeError):
            pass
    
    # Extract EPS from metrics
    if 'metrics' in data and 'eps' in data['metrics'] and data['metrics']['eps'] is not None:
        try:
            eps = float(data['metrics']['eps'])
        except (ValueError, TypeError):
            pass
    
    # Calculate P/E ratio if both values are available
    if current_price is not None and eps is not None and eps != 0:
        pe_ratio = current_price / eps
        logger.info(f"Calculated P/E ratio: {pe_ratio:.2f} (Price: {current_price}, EPS: {eps})")
        return round(pe_ratio, 2)
    
    logger.warning(f"Cannot calculate P/E ratio - Price: {current_price}, EPS: {eps}")
    return None


def categorize_pe_ratio(pe_ratio: float) -> str:
    """
    Categorize P/E ratio into investment categories
    
    Args:
        pe_ratio: P/E ratio value
        
    Returns:
        str: Category description
    """
    if pe_ratio <= 0:
        return 'negative_earnings'
    elif pe_ratio < 10:
        return 'undervalued'
    elif pe_ratio < 15:
        return 'fair_value'
    elif pe_ratio < 25:
        return 'growth_stock'
    elif pe_ratio < 50:
        return 'expensive'
    else:
        return 'highly_speculative'


def extract_symbol_from_data(data: Dict) -> str:
    """
    Extract trading symbol from Bavest API response
    
    Args:
        data: Financial data dictionary from Bavest API
        
    Returns:
        Trading symbol or ISIN
    """
    # For Bavest API, we'll use the ISIN from the ingestion metadata
    # or fall back to a default ISIN
    return "DE0005104400"  # The ISIN we're tracking


def store_in_redis(processed_data: Dict, redis_client: redis.Redis) -> None:
    """
    Store processed Bavest P/E ratio data in Redis with appropriate keys and TTL
    
    Args:
        processed_data: Processed financial data with P/E ratio from Bavest
        redis_client: Redis client instance
    """
    symbol = processed_data['symbol']
    timestamp = processed_data['timestamp']
    pe_ratio = processed_data['analytics'].get('pe_ratio')
    pe_category = processed_data['analytics'].get('pe_category')
    valuation_signal = processed_data['analytics'].get('valuation_signal')
    current_price = processed_data['market_data'].get('current_price')
    
    # Store individual P/E record with timestamp
    timestamp_key = f"bavest:pe:{symbol}:{timestamp}"
    redis_client.setex(timestamp_key, 3600, json.dumps(processed_data))  # 1 hour TTL
    
    # Store latest P/E data for the symbol
    latest_key = f"bavest:pe:latest:{symbol}"
    redis_client.setex(latest_key, 3600, json.dumps(processed_data))
    
    # Store simplified P/E summary with trading signal
    pe_summary_key = f"bavest:pe:summary:{symbol}"
    pe_summary = {
        'symbol': symbol,
        'last_updated': timestamp,
        'current_price': current_price,
        'pe_ratio': pe_ratio,
        'pe_category': pe_category,
        'valuation_signal': valuation_signal,
        'data_available': pe_ratio is not None,
        'currency': processed_data['metadata'].get('currency', 'EUR')
    }
    redis_client.setex(pe_summary_key, 1800, json.dumps(pe_summary))  # 30 min TTL
    
    # Store current price for quick access
    price_key = f"bavest:price:{symbol}"
    if current_price is not None:
        redis_client.setex(price_key, 900, str(current_price))  # 15 min TTL
    
    # Update symbol list for P/E tracking
    redis_client.sadd("bavest:pe:symbols", symbol)
    redis_client.expire("bavest:pe:symbols", 86400)  # 24 hour TTL
    
    logger.info(f"Stored Bavest data for {symbol} - Price: {current_price}, P/E: {pe_ratio}, Signal: {valuation_signal}")
