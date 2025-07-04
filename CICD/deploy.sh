#!/bin/bash
# deploy.sh - Complete deployment script

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Navigate to the project root (parent of CICD directory)
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
FUNCTION_NAME="${FUNCTION_NAME:-creole-creamery-scraper}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${FUNCTION_NAME}"

echo "Starting deployment for ${FUNCTION_NAME}"
echo "Working directory: $(pwd)"

# Check required environment variables
if [[ -z "$NEON_DATABASE_URL" ]]; then
    echo "Error: NEON_DATABASE_URL environment variable is required"
    exit 1
fi

if [[ -z "$OPENAI_API_KEY" ]]; then
    echo "Error: OPENAI_API_KEY environment variable is required"
    exit 1
fi

# Step 1: Install dependencies if not already done
echo "Installing dependencies with Poetry..."
if ! command -v poetry &> /dev/null; then
    echo "Installing Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
fi

poetry install --only=main

# Step 2: Set up Terraform infrastructure
echo "Setting up infrastructure with Terraform..."
cd terraform

# Initialize Terraform
terraform init

# Plan the deployment
terraform plan \
    -var="neon_database_url=$NEON_DATABASE_URL" \
    -var="openai_api_key=$OPENAI_API_KEY" \
    -var="aws_region=$AWS_REGION" \
    -var="function_name=$FUNCTION_NAME"

# Apply the infrastructure
terraform apply -auto-approve \
    -var="neon_database_url=$NEON_DATABASE_URL" \
    -var="openai_api_key=$OPENAI_API_KEY" \
    -var="aws_region=$AWS_REGION" \
    -var="function_name=$FUNCTION_NAME"

cd ..

# Step 3: Build and push Docker image
echo "Building and pushing Docker image..."

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REPO_URI

# Build the image (using project root as context)
docker build -t $FUNCTION_NAME .

# Tag for ECR
docker tag $FUNCTION_NAME:latest $ECR_REPO_URI:latest

# Push to ECR
docker push $ECR_REPO_URI:latest

# Step 4: Update Lambda function
echo "Updating Lambda function..."
aws lambda update-function-code \
    --function-name $FUNCTION_NAME \
    --image-uri $ECR_REPO_URI:latest \
    --region $AWS_REGION

# Wait for the update to complete
echo "Waiting for function update to complete..."
aws lambda wait function-updated --function-name $FUNCTION_NAME --region $AWS_REGION

# Step 5: Test the function
echo "Testing the function..."
aws lambda invoke \
    --function-name $FUNCTION_NAME \
    --region $AWS_REGION \
    --payload '{}' \
    response.json

echo "Function response:"
cat response.json
echo ""

# Clean up response file
rm response.json

echo "Deployment completed successfully!"
echo ""
echo "Function details:"
echo "  Name: $FUNCTION_NAME"
echo "  Region: $AWS_REGION"
echo "  ECR URI: $ECR_REPO_URI"
echo ""
echo "The function is scheduled to run daily at 6 AM UTC"
echo "You can manually invoke it using:"
echo "   aws lambda invoke --function-name $FUNCTION_NAME response.json"
