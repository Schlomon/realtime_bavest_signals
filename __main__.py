"""An AWS Python Pulumi program for real-time Bavest signals processing"""

import pulumi
import pulumi_aws as aws
import json

# Get configuration
config = pulumi.Config()                    # Default namespace
config_bavest = pulumi.Config("bavest")      # Bavest API configuration
config_lambda = pulumi.Config("lambda")      # Lambda configuration
config_kinesis = pulumi.Config("kinesis")    # Kinesis configuration
config_elasticache = pulumi.Config("elasticache")  # ElastiCache configuration
config_ingestion = pulumi.Config("ingestion")      # Ingestion schedule configuration

# Create IAM role for Lambda functions
lambda_role = aws.iam.Role("lambda-role",
    assume_role_policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "lambda.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    })
)

# Attach basic execution policy to Lambda role
aws.iam.RolePolicyAttachment("lambda-basic-execution",
    role=lambda_role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
)

# Create Kinesis stream
kinesis_stream = aws.kinesis.Stream("bavest-data-stream",
    name="bavest-data-stream",
    shard_count=config_kinesis.get_int("shard_count") or 1,
    retention_period=config_kinesis.get_int("retention_period") or 24,
    tags={
        "Environment": config.get("environment") or "dev",
        "Purpose": "bavest-signals"
    }
)

# IAM policy for Kinesis access
kinesis_policy = aws.iam.Policy("kinesis-policy",
    policy=pulumi.Output.all(kinesis_stream.arn).apply(lambda args: json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "kinesis:PutRecord",
                    "kinesis:PutRecords",
                    "kinesis:GetRecords",
                    "kinesis:GetShardIterator",
                    "kinesis:DescribeStream",
                    "kinesis:ListStreams"
                ],
                "Resource": args[0]
            }
        ]
    }))
)

# Attach Kinesis policy to Lambda role
aws.iam.RolePolicyAttachment("lambda-kinesis-policy",
    role=lambda_role.name,
    policy_arn=kinesis_policy.arn
)

# Get default VPC
default_vpc = aws.ec2.get_vpc(default=True)

# Get subnets from default VPC
default_subnets = aws.ec2.get_subnets(filters=[
    {
        "name": "vpc-id",
        "values": [default_vpc.id]
    }
])

# Create ElastiCache subnet group with default subnets
elasticache_subnet_group = aws.elasticache.SubnetGroup("bavest-cache-subnet-group",
    name="bavest-cache-subnet-group",
    description="Subnet group for Bavest ElastiCache",
    subnet_ids=default_subnets.ids
)

# Security group for ElastiCache
elasticache_security_group = aws.ec2.SecurityGroup("elasticache-sg",
    name="elasticache-sg",
    description="Security group for ElastiCache",
    vpc_id=default_vpc.id,
    ingress=[
        {
            "from_port": 6379,
            "to_port": 6379,
            "protocol": "tcp",
            "cidr_blocks": [default_vpc.cidr_block]
        }
    ],
    egress=[
        {
            "from_port": 0,
            "to_port": 0,
            "protocol": "-1",
            "cidr_blocks": ["0.0.0.0/0"]
        }
    ]
)

# ElastiCache Redis cluster
redis_cluster = aws.elasticache.ReplicationGroup("bavest-redis-cluster",
    description="Redis cluster for Bavest financial data",
    replication_group_id="bavest-redis",
    node_type=config_elasticache.get("node_type") or "cache.t3.micro",
    port=6379,
    parameter_group_name="default.redis7",
    num_cache_clusters=config_elasticache.get_int("num_cache_clusters") or 1,
    subnet_group_name=elasticache_subnet_group.name,
    security_group_ids=[elasticache_security_group.id],
    tags={
        "Environment": config.get("environment") or "dev",
        "Purpose": "bavest-signals"
    }
)

# IAM policy for ElastiCache access
elasticache_policy = aws.iam.Policy("elasticache-policy",
    policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "elasticache:DescribeReplicationGroups",
                    "elasticache:DescribeCacheClusters"
                ],
                "Resource": "*"
            }
        ]
    })
)

# Attach ElastiCache policy to Lambda role
aws.iam.RolePolicyAttachment("lambda-elasticache-policy",
    role=lambda_role.name,
    policy_arn=elasticache_policy.arn
)

# Attach VPC execution policy to Lambda role
aws.iam.RolePolicyAttachment("lambda-vpc-execution",
    role=lambda_role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
)

# Lambda function 1: Bavest API Ingestion
ingestion_lambda = aws.lambda_.Function("bavest-ingestion-lambda",
    name="bavest-ingestion-lambda",
    role=lambda_role.arn,
    handler="handler.handler",
    runtime="python3.11",
    code=pulumi.AssetArchive({
        ".": pulumi.FileArchive("./lambda_functions/ingestion")
    }),
    environment={
        "variables": {
            "KINESIS_STREAM_NAME": kinesis_stream.name,
            "BAVEST_API_URL": config_bavest.get("api_url") or "https://api.bavest.co/v0/",
            "BAVEST_API_KEY": config_bavest.require("api_key")
        }
    },
    timeout=config_lambda.get_int("timeout") or 30,
    tags={
        "Environment": config.get("environment") or "dev",
        "Purpose": "bavest-ingestion"
    }
)

# EventBridge rule to trigger ingestion lambda periodically
ingestion_schedule_rule = aws.cloudwatch.EventRule("bavest-ingestion-schedule",
    name="bavest-ingestion-schedule",
    description="Trigger Bavest ingestion every 5 minutes",
    schedule_expression=config_ingestion.get("schedule") or "rate(5 minutes)"
)

# Permission for EventBridge to invoke the ingestion lambda
aws.lambda_.Permission("ingestion-lambda-eventbridge-permission",
    statement_id="AllowExecutionFromCloudWatch",
    action="lambda:InvokeFunction",
    function=ingestion_lambda.name,
    principal="events.amazonaws.com",
    source_arn=ingestion_schedule_rule.arn
)

# EventBridge target
aws.cloudwatch.EventTarget("ingestion-lambda-target",
    rule=ingestion_schedule_rule.name,
    target_id="IngestionLambdaTarget",
    arn=ingestion_lambda.arn
)

# Lambda function 2: Data Science Processing
processing_lambda = aws.lambda_.Function("bavest-processing-lambda",
    name="bavest-processing-lambda",
    role=lambda_role.arn,
    handler="handler.handler",
    runtime="python3.11",
    code=pulumi.AssetArchive({
        ".": pulumi.FileArchive("./lambda_functions/processing")
    }),
    environment={
        "variables": {
            "REDIS_HOST": redis_cluster.primary_endpoint_address,
            "REDIS_PORT": "6379"
        }
    },
    vpc_config={
        "subnet_ids": default_subnets.ids,
        "security_group_ids": [elasticache_security_group.id]
    },
    timeout=config_lambda.get_int("processing_timeout") or 60,
    tags={
        "Environment": config.get("environment") or "dev",
        "Purpose": "bavest-processing"
    }
)

# Event source mapping for Kinesis to Lambda
aws.lambda_.EventSourceMapping("kinesis-lambda-mapping",
    event_source_arn=kinesis_stream.arn,
    function_name=processing_lambda.arn,
    starting_position="LATEST"
)

# Export important values
pulumi.export("kinesis_stream_name", kinesis_stream.name)
pulumi.export("kinesis_stream_arn", kinesis_stream.arn)
pulumi.export("redis_primary_endpoint", redis_cluster.primary_endpoint_address)
pulumi.export("ingestion_lambda_name", ingestion_lambda.name)
pulumi.export("processing_lambda_name", processing_lambda.name)


