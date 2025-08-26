# Real-time Bavest Signals Processing Infrastructure

A production-ready AWS infrastructure for processing real-time financial signals from the Bavest API using Pulumi, AWS Lambda, Kinesis, and Redis.

## 🏗️ Architecture

```
📥 Bavest API → 🔄 Lambda Ingestion → 🌊 Kinesis Stream → 🔄 Lambda Processing → 📊 Redis Storage
```

The infrastructure consists of:

1. **Ingestion Lambda**: Fetches data from Bavest API and sends it to Kinesis
2. **Kinesis Stream**: Streams the financial data in real-time  
3. **Processing Lambda**: Performs P/E ratio analysis on the streamed data
4. **ElastiCache (Redis)**: Stores processed financial signals

## 🧩 Components

### 1. Bavest API Ingestion Lambda
- **Trigger**: Every 5 minutes via EventBridge scheduled rule
- **Function**: Fetches financial signals from Bavest API
- **Output**: Sends data to Kinesis stream
- **Runtime**: Python 3.11

### 2. Kinesis Data Stream  
- **Configuration**: 1 shard (scalable)
- **Retention**: 24 hours
- **Function**: Real-time data streaming with automatic Lambda triggering

### 3. Data Processing Lambda
- **Trigger**: Kinesis stream events (automatic)
- **Analysis**: P/E ratio calculation and financial signal processing
- **Output**: Stores results in Redis
- **VPC**: Configured for Redis access

### 4. ElastiCache Redis Cluster
- **Type**: Single-node replication group (t3.micro)
- **Purpose**: Stores processed financial data with structured keys
- **Access**: VPC-only for security

## 📁 Project Structure

```
realtime_bavest_signals/
├── __main__.py                    # Main Pulumi infrastructure code
├── Pulumi.yaml                   # Project configuration
├── Pulumi.dev.yaml.template     # Configuration template
├── requirements.txt             # Pulumi dependencies
├── lambda_functions/           # Lambda function source code
│   ├── ingestion/             # Bavest API ingestion function
│   │   ├── handler.py         # Main ingestion logic
│   │   └── requirements.txt   # boto3, requests dependencies
│   ├── processing/            # Data processing function  
│   │   ├── handler.py         # P/E ratio analysis logic
│   │   └── requirements.txt   # boto3, redis dependencies
│   └── README.md             # Lambda functions documentation
└── README.md                  # This file
```

## 🚀 Setup

### Prerequisites
- AWS CLI configured with appropriate credentials
- Pulumi CLI installed (`npm install -g @pulumi/cli`)
- Python 3.11+ installed

### Configuration

1. **Copy configuration template**:
```bash
cp Pulumi.dev.yaml.template Pulumi.dev.yaml
```

2. **Set your Bavest API credentials**:
```yaml
config:
  bavest:api_key: "your-bavest-api-key-here"
  bavest:api_url: "https://api.bavest.co/v0/"
  aws:region: "eu-central-1"  # or your preferred region
```

3. **Optionally modify other settings** like instance types, timeouts, etc.

### Deployment

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Initialize Pulumi stack**:
```bash
pulumi stack init dev
```

3. **Preview the infrastructure**:
```bash
pulumi preview
```

4. **Deploy the infrastructure**:
```bash
pulumi up
```

This will create **18 AWS resources** including Lambda functions, Kinesis stream, Redis cluster, IAM roles, and VPC configurations.

## 🔧 Environment Variables

### Ingestion Lambda:
- `KINESIS_STREAM_NAME`: Kinesis stream name (auto-configured)
- `BAVEST_API_URL`: Bavest API endpoint
- `BAVEST_API_KEY`: Your Bavest API key

### Processing Lambda:
- `REDIS_HOST`: ElastiCache Redis primary endpoint (auto-configured)
- `REDIS_PORT`: Redis port (6379)

## 📊 Data Flow

1. **Scheduled Ingestion**: EventBridge triggers ingestion Lambda every 5 minutes
2. **API Fetch**: Lambda calls Bavest API for financial signals
3. **Stream Publishing**: Data sent to Kinesis with automatic partitioning
4. **Event Processing**: Processing Lambda automatically triggered by Kinesis events
5. **Analysis**: P/E ratio calculation and financial signal processing
6. **Storage**: Results stored in Redis with structured keys:
   - `bavest:pe_ratio:{symbol}:{timestamp}` - P/E ratio data
   - `bavest:latest:{symbol}` - Latest analysis for each symbol

## 📈 Monitoring

**Key metrics to monitor**:
- Lambda function errors and duration (CloudWatch)
- Kinesis stream throughput and iterator age
- ElastiCache memory usage and connections
- EventBridge rule execution success rate

**Available outputs after deployment**:
```bash
pulumi stack output
```
- `ingestion_lambda_name`
- `processing_lambda_name` 
- `kinesis_stream_name`
- `redis_primary_endpoint`

## ⚡ Testing

**Test ingestion function**:
```bash
aws lambda invoke --function-name $(pulumi stack output ingestion_lambda_name) --payload '{}' response.json
```

**Test processing function**:
```bash
aws lambda invoke --function-name $(pulumi stack output processing_lambda_name) --payload '{"Records":[{"kinesis":{"data":"base64-encoded-test-data"}}]}' response.json
```

## 🔄 Scaling

**To scale the infrastructure**:
- **Kinesis**: Increase `kinesis:shard_count` in config
- **Redis**: Change `elasticache:node_type` to larger instance
- **Lambda**: Adjust `lambda:timeout` and memory settings
- **Frequency**: Modify `ingestion:schedule` for different intervals

## 💰 Cost Optimization

- **Kinesis**: ~$0.0075/hour per shard + data throughput
- **Lambda**: Pay per execution (~288 executions/day)
- **ElastiCache**: ~$0.0058/hour for t3.micro
- **Data Storage**: 24h Kinesis retention, automatic Redis TTL

**Estimated monthly cost**: $15-25 for development workload

## 🔒 Security

- **IAM**: Least-privilege roles for each service
- **VPC**: Processing Lambda in VPC for Redis access
- **Security Groups**: Redis accessible only from Lambda
- **API Keys**: Environment variables (consider AWS Secrets Manager for production)

## 🧹 Cleanup

**To destroy the infrastructure**:
```bash
pulumi destroy
```

This will remove all 18 AWS resources and stop all charges.

## 🛠️ Development

**Lambda function dependencies are managed locally**:
- Dependencies installed in function directories
- Pulumi uses `FileArchive` for deployment
- `.gitignore` excludes dependency directories

**For development**:
```bash
# Install dependencies in Lambda directories
pip install -r lambda_functions/ingestion/requirements.txt -t lambda_functions/ingestion/
pip install -r lambda_functions/processing/requirements.txt -t lambda_functions/processing/
```

## 📋 License

This project is open source. Please ensure you comply with Bavest API terms of service.
