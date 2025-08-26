# Lambda Functions Documentation

This directory contains the Lambda functions for the Bavest signals processing infrastructure.

## Structure

```
lambda_functions/
├── ingestion/
│   ├── handler.py           # Main ingestion Lambda function
│   └── requirements.txt     # Dependencies for ingestion function
├── processing/
│   ├── handler.py           # Main processing Lambda function
│   └── requirements.txt     # Dependencies for processing function
├── shared_utils.py          # Shared utilities across Lambda functions
├── package_lambdas.py       # Deployment packaging script
└── README.md               # This file
```

## Functions Overview

### 1. Ingestion Lambda (`ingestion/handler.py`)

**Purpose**: Fetches financial signals from the Bavest API and sends them to Kinesis stream.

**Trigger**: EventBridge (scheduled every 5 minutes)

**Key Features**:
- Robust API error handling with retries
- Data validation and enrichment
- Kinesis partitioning by symbol
- Comprehensive logging
- Environment variable validation

**Environment Variables**:
- `KINESIS_STREAM_NAME`: Target Kinesis stream
- `BAVEST_API_URL`: Bavest API endpoint
- `BAVEST_API_KEY`: Authentication key

**Dependencies**:
- `boto3`: AWS SDK
- `requests`: HTTP client for API calls

### 2. Processing Lambda (`processing/handler.py`)

**Purpose**: Processes financial data from Kinesis, performs data science operations, and stores results in Redis.

**Trigger**: Kinesis stream events

**Key Features**:
- Advanced statistical analysis (mean, median, volatility, etc.)
- Signal strength categorization
- Technical indicator calculations
- Structured Redis storage with TTL
- Batch processing with error handling
- Type hints for better code maintainability

**Environment Variables**:
- `REDIS_HOST`: ElastiCache Redis endpoint
- `REDIS_PORT`: Redis port (default: 6379)

**Dependencies**:
- `boto3`: AWS SDK
- `redis`: Redis client
- `statistics`: Built-in Python statistics module

## Data Science Operations

The processing Lambda performs several analytical operations:

### Price Analysis
- **Mean Price**: Average price across the dataset
- **Median Price**: Middle value of price distribution
- **Price Volatility**: Standard deviation of prices
- **Price Range**: Difference between max and min prices
- **Price Change %**: Percentage change from first to last price

### Signal Analysis
- **Signal Strength Categorization**: 
  - `very_strong` (≥0.8)
  - `strong` (≥0.6)
  - `moderate` (≥0.4)
  - `weak` (≥0.2)
  - `very_weak` (<0.2)
- **Confidence Level**: High/Medium/Low based on strength
- **Signal Direction**: Buy/Sell/Hold recommendations

### Volume Analysis
- **Volume Statistics**: Mean, median, total volume
- **Volume Volatility**: Trading volume variations

### Technical Indicators
- **Simple Moving Averages**: SMA-5, SMA-10
- **Momentum Indicators**: Price momentum calculations

## Redis Data Storage

### Key Patterns

1. **Individual Records**: `bavest:{symbol}:{timestamp}`
   - TTL: 1 hour
   - Contains: Full processed data with analytics

2. **Latest Data**: `bavest:latest:{symbol}`
   - TTL: 1 hour
   - Contains: Most recent data for quick access

3. **Analytics Summary**: `bavest:analytics:{symbol}`
   - TTL: 30 minutes
   - Contains: Analytics and signals only

4. **Symbol Tracking**: `bavest:symbols`
   - TTL: 24 hours
   - Contains: Set of all processed symbols

## Development and Testing

### Local Development

1. **Install dependencies**:
```bash
# For ingestion function
cd ingestion
pip install -r requirements.txt

# For processing function
cd ../processing
pip install -r requirements.txt
```

2. **Environment setup**:
Create a `.env` file with required environment variables for local testing.

3. **Testing**:
Each function can be tested independently with mock events.

### Packaging for Deployment

Use the packaging script to prepare Lambda deployment packages:

```bash
# Package all functions
python package_lambdas.py

# Package specific function
python package_lambdas.py --function ingestion

# Clean all packages
python package_lambdas.py --clean
```

## Error Handling

Both Lambda functions implement comprehensive error handling:

### Ingestion Lambda
- **API Timeouts**: 25-second timeout with retry logic
- **Authentication Errors**: Clear logging for API key issues
- **Network Issues**: Graceful handling of connection problems
- **Data Validation**: Checks for valid JSON responses

### Processing Lambda
- **Redis Connection**: Connection pooling and retry logic
- **Data Parsing**: Safe JSON parsing with fallbacks
- **Statistical Calculations**: Handle edge cases (empty data, single values)
- **Individual Record Failures**: Continue processing other records

## Monitoring and Logging

### CloudWatch Metrics

Key metrics to monitor:
- **Lambda Duration**: Function execution time
- **Lambda Errors**: Error rate and types
- **Lambda Throttles**: Concurrent execution limits
- **Kinesis Records**: Throughput and processing lag

### Log Analysis

Both functions use structured logging with:
- Timestamp and request ID correlation
- Error classification and context
- Performance metrics
- Data processing statistics

### Alerts

Recommended CloudWatch alarms:
- Lambda error rate > 5%
- Lambda duration > 80% of timeout
- Kinesis processing lag > 1 minute
- Redis connection failures

## Performance Optimization

### Memory and Timeout Settings

**Ingestion Lambda**:
- Memory: 256 MB (sufficient for API calls)
- Timeout: 30 seconds (API calls + Kinesis write)

**Processing Lambda**:
- Memory: 512 MB (data science calculations)
- Timeout: 60 seconds (batch processing)

### Scaling Considerations

- **Ingestion**: Single concurrent execution (scheduled trigger)
- **Processing**: Scales with Kinesis shard count
- **Redis**: Connection pooling for high throughput

## Security Best Practices

1. **IAM Roles**: Minimal required permissions
2. **API Keys**: Stored as environment variables (consider AWS Secrets Manager for production)
3. **VPC**: ElastiCache in private subnets
4. **Encryption**: In-transit and at-rest encryption enabled
5. **Input Validation**: All external data validated before processing

## Troubleshooting

### Common Issues

1. **"Import could not be resolved"**: Install dependencies locally for IDE support
2. **Redis connection timeout**: Check VPC security groups and network ACLs
3. **API rate limiting**: Implement exponential backoff in ingestion function
4. **Memory issues**: Monitor CloudWatch metrics and adjust memory allocation

### Debug Commands

```bash
# Check Lambda logs
aws logs tail /aws/lambda/bavest-ingestion-lambda --follow

# Monitor Kinesis stream
aws kinesis describe-stream --stream-name bavest-data-stream

# Check Redis connectivity
redis-cli -h <redis-endpoint> ping
```
