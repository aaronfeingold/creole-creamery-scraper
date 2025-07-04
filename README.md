# Creole Creamery Hall of Fame Scraper

An LLM-powered web scraper that extracts Hall of Fame entries from the Creole Creamery website and stores them in a PostgreSQL database. The scraper runs daily on AWS Lambda and uses OpenAI's GPT-4 for intelligent data extraction.

## Features

- **LLM-powered extraction**: Uses OpenAI GPT-4 to parse HTML content intelligently
- **Automatic scheduling**: Runs daily at 6 AM UTC via AWS EventBridge
- **Incremental updates**: Only saves new entries to avoid duplicates
- **Fallback parsing**: Regex fallback if LLM parsing fails
- **Containerized deployment**: Uses Docker for consistent Lambda execution
- **Infrastructure as Code**: Terraform manages all AWS resources

## Architecture

- **AWS Lambda**: Serverless function execution
- **Amazon ECR**: Container image storage
- **AWS EventBridge**: Daily scheduling
- **Neon PostgreSQL**: Database storage
- **OpenAI API**: Intelligent text extraction

## Prerequisites

Before deploying this project, ensure you have:

### Local Development
- Python 3.11+
- Poetry (Python dependency management)
- Docker
- Git

### AWS Account Setup
- AWS CLI installed and configured
- AWS account with appropriate permissions
- AWS CLI profile configured with credentials

### External Services
- **Neon Database**: PostgreSQL database instance
- **OpenAI API**: API key for GPT-4 access

## Installation

### 1. Clone the Repository
```bash
git clone <repository-url>
cd creole-creamery-scraper
```

### 2. Install Dependencies
```bash
# Install Poetry if not already installed
curl -sSL https://install.python-poetry.org | python3 -

# Install project dependencies
poetry install
```

### 3. Set Up Environment Variables
Create a `.env` file in the project root:
```bash
cp terraform/terraform.tfvars.example .env
```

Edit `.env` with your actual values:
```env
NEON_DATABASE_URL=postgresql://username:password@hostname:port/database
OPENAI_API_KEY=sk-your-openai-api-key-here
AWS_REGION=us-east-1
FUNCTION_NAME=creole-creamery-scraper
```

## AWS Setup and Deployment

### Step 1: Configure AWS CLI
```bash
# Install AWS CLI if not already installed
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Configure AWS credentials
aws configure
```

### Step 2: Set Required IAM Permissions
Your AWS user/role needs the following permissions:
- ECR: Create and manage repositories
- Lambda: Create and manage functions
- IAM: Create roles and policies
- EventBridge: Create rules and targets
- CloudWatch: Create log groups

### Step 3: Prepare Terraform Configuration
```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your values:
```hcl
aws_region = "us-east-1"
function_name = "creole-creamery-scraper"
neon_database_url = "postgresql://username:password@hostname:port/database"
openai_api_key = "sk-your-openai-api-key-here"
```

### Step 4: Deploy Infrastructure
```bash
# Initialize Terraform
terraform init

# Review the deployment plan
terraform plan

# Deploy infrastructure
terraform apply
```

### Step 5: Build and Deploy the Application
```bash
# Return to project root
cd ..

# Make deploy script executable
chmod +x CICD/deploy.sh

# Set environment variables and deploy
export NEON_DATABASE_URL="your-database-url"
export OPENAI_API_KEY="your-openai-key"
export AWS_REGION="us-east-1"
export FUNCTION_NAME="creole-creamery-scraper"

# Run deployment
./CICD/deploy.sh
```

## Local Testing

Before deploying, test the scraper locally:

```bash
# Ensure .env file is configured
poetry shell
python tests/test_scraper.py
```

The test script will:
- Validate environment variables
- Run the scraper logic
- Display results and statistics

## Project Structure

```
creole-creamery-scraper/
├── lambda_function.py          # Main Lambda handler and scraper logic
├── Dockerfile                 # Container image definition
├── pyproject.toml            # Python dependencies and config
├── .env                      # Environment variables (create from example)
├── CICD/
│   └── deploy.sh             # Complete deployment script
└─── tests/
   ├── test_scraper.py            # Local testing script
└── terraform/
    ├── main.tf               # Terraform infrastructure definition
    ├── terraform.tfvars.example  # Example configuration
    └── terraform.tfvars      # Your configuration (create from example)
```

## Database Schema

The scraper creates a table with the following structure:

```sql
CREATE TABLE hall_of_fame_entries (
    id SERIAL PRIMARY KEY,
    participant_number INTEGER UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    date_str VARCHAR(50) NOT NULL,
    parsed_date TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Monitoring and Logs

### CloudWatch Logs
View execution logs:
```bash
aws logs tail /aws/lambda/creole-creamery-scraper --follow
```

### Manual Invocation
Test the function manually:
```bash
aws lambda invoke \
    --function-name creole-creamery-scraper \
    --payload '{}' \
    response.json && cat response.json
```

## Configuration

### Scheduling
The function runs daily at 6 AM UTC. To modify the schedule, update the `schedule_expression` in `terraform/main.tf`:
```hcl
schedule_expression = "cron(0 6 * * ? *)"  # 6 AM UTC daily
```

### Function Settings
Adjust Lambda configuration in `terraform/main.tf`:
- `timeout`: Function execution timeout (default: 300 seconds)
- `memory_size`: Memory allocation (default: 512 MB)

## Troubleshooting

### Common Issues

**1. Permission Denied**
- Ensure AWS CLI is configured with appropriate permissions
- Check IAM policies include ECR, Lambda, and EventBridge access

**2. Docker Build Failures**
- Ensure Docker is running
- Check available disk space

**3. Database Connection Issues**
- Verify Neon database URL format and credentials
- Ensure database accepts connections from Lambda IPs

**4. OpenAI API Failures**
- Verify API key is valid and has sufficient credits
- Check rate limits haven't been exceeded

### Getting Help

Check the following for debugging:
1. CloudWatch logs: `/aws/lambda/creole-creamery-scraper`
2. Test locally: `python tests/test_scraper.py`
3. Verify environment variables are set correctly

## Cost Considerations

Estimated monthly costs (may vary):
- Lambda: ~$0.20 (daily execution, 30 seconds runtime)
- ECR: ~$0.10 (image storage)
- CloudWatch: ~$0.50 (logs retention)
- OpenAI API: Variable based on usage
- Neon Database: Based on your plan (currently free tier YAY)
