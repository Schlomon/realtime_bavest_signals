"""
Shared utilities for Lambda functions
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional


def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    Setup standardized logging for Lambda functions
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        
    Returns:
        Logger instance
    """
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler with formatting
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger


def create_response(status_code: int, body: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict:
    """
    Create standardized Lambda response
    
    Args:
        status_code: HTTP status code
        body: Response body dictionary
        headers: Optional response headers
        
    Returns:
        Lambda response dictionary
    """
    response = {
        'statusCode': status_code,
        'body': json.dumps(body, default=str),
        'headers': headers or {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        }
    }
    
    return response


def validate_environment_variables(*required_vars: str) -> None:
    """
    Validate that required environment variables are set
    
    Args:
        *required_vars: Variable names to check
        
    Raises:
        ValueError: If any required variable is missing
    """
    import os
    
    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")


def safe_float_conversion(value: Any, default: float = 0.0) -> float:
    """
    Safely convert value to float with fallback
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Float value or default
    """
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def safe_int_conversion(value: Any, default: int = 0) -> int:
    """
    Safely convert value to int with fallback
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Integer value or default
    """
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def extract_symbol_from_data(data: Dict[str, Any]) -> str:
    """
    Extract trading symbol from various data formats
    
    Args:
        data: Financial data dictionary
        
    Returns:
        Trading symbol or 'UNKNOWN'
    """
    symbol_fields = ['symbol', 'ticker', 'instrument', 'asset', 'stock']
    
    for field in symbol_fields:
        if field in data and data[field]:
            return str(data[field]).upper()
    
    return 'UNKNOWN'


def add_timestamp_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add timestamp metadata to data
    
    Args:
        data: Original data dictionary
        
    Returns:
        Data with added timestamp metadata
    """
    timestamp = datetime.utcnow().isoformat()
    
    metadata = {
        'processed_at': timestamp,
        'processor_version': '1.0',
        'data_source': 'bavest_api'
    }
    
    if isinstance(data, dict):
        data['metadata'] = metadata
    
    return data


class DataValidator:
    """Helper class for data validation"""
    
    @staticmethod
    def is_valid_price_data(data: Dict[str, Any]) -> bool:
        """Validate price data structure"""
        price_fields = ['price', 'prices', 'close', 'last_price', 'current_price']
        return any(field in data for field in price_fields)
    
    @staticmethod
    def is_valid_signal_data(data: Dict[str, Any]) -> bool:
        """Validate signal data structure"""
        signal_fields = ['signal', 'signal_strength', 'signal_direction', 'recommendation']
        return any(field in data for field in signal_fields)
    
    @staticmethod
    def is_valid_volume_data(data: Dict[str, Any]) -> bool:
        """Validate volume data structure"""
        volume_fields = ['volume', 'volumes', 'trading_volume']
        return any(field in data for field in volume_fields)
