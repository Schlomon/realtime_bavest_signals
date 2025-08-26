#!/usr/bin/env python3
"""
Deployment helper script for Bavest Signals Infrastructure

This script helps deploy the Lambda dependencies and infrastructure.
"""

import os
import subprocess
import sys
from pathlib import Path

def run_command(command, cwd=None):
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error running command: {command}")
            print(f"Error output: {result.stderr}")
            return False
        return True
    except Exception as e:
        print(f"Exception running command: {command}")
        print(f"Exception: {e}")
        return False

def install_lambda_dependencies():
    """Install dependencies for Lambda functions."""
    lambda_dirs = [
        "lambda_functions/ingestion",
        "lambda_functions/processing"
    ]
    
    for lambda_dir in lambda_dirs:
        if os.path.exists(lambda_dir):
            print(f"Installing dependencies for {lambda_dir}...")
            requirements_file = os.path.join(lambda_dir, "requirements.txt")
            if os.path.exists(requirements_file):
                command = f"pip install -r requirements.txt -t ."
                if not run_command(command, cwd=lambda_dir):
                    print(f"Failed to install dependencies for {lambda_dir}")
                    return False
            else:
                print(f"No requirements.txt found in {lambda_dir}")
        else:
            print(f"Lambda directory {lambda_dir} does not exist")
            
    return True

def deploy_infrastructure():
    """Deploy the Pulumi infrastructure."""
    print("Deploying infrastructure...")
    if not run_command("pulumi up --yes"):
        print("Failed to deploy infrastructure")
        return False
    return True

def main():
    """Main deployment script."""
    print("=== Bavest Signals Infrastructure Deployment ===")
    
    # Check if we're in the right directory
    if not os.path.exists("__main__.py") or not os.path.exists("Pulumi.yaml"):
        print("Error: Please run this script from the project root directory")
        sys.exit(1)
    
    # Check if Pulumi.dev.yaml exists
    if not os.path.exists("Pulumi.dev.yaml"):
        print("Error: Pulumi.dev.yaml not found. Please copy from Pulumi.dev.yaml.template and configure your API key")
        sys.exit(1)
    
    # Install Lambda dependencies
    print("\n1. Installing Lambda dependencies...")
    if not install_lambda_dependencies():
        print("Failed to install Lambda dependencies")
        sys.exit(1)
    
    # Deploy infrastructure
    print("\n2. Deploying infrastructure...")
    if not deploy_infrastructure():
        print("Failed to deploy infrastructure")
        sys.exit(1)
    
    print("\n✅ Deployment completed successfully!")
    print("\nTo check the status of your deployment:")
    print("  pulumi stack output")
    print("\nTo test your Lambda functions:")
    print("  aws lambda invoke --function-name $(pulumi stack output ingestion_lambda_name) --payload '{}' response.json")

if __name__ == "__main__":
    main()
