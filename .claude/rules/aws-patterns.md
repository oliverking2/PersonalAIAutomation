# AWS Patterns

Rules for working with AWS services via boto3.

## Type Stubs

Use typed stubs from `boto3-stubs` for type safety:

```bash
poetry add --group dev boto3-stubs[bedrock-runtime,s3,ssm]
```

## Client Typing

Always use explicit client types:

```python
from mypy_boto3_bedrock_runtime import BedrockRuntimeClient
from mypy_boto3_s3 import S3Client
from mypy_boto3_ssm import SSMClient
import boto3


def get_bedrock_client() -> BedrockRuntimeClient:
    """Get typed Bedrock Runtime client."""
    return boto3.client("bedrock-runtime")


def get_s3_client() -> S3Client:
    """Get typed S3 client."""
    return boto3.client("s3")
```

## Exception Handling

Handle AWS exceptions specifically:

```python
from botocore.exceptions import ClientError, BotoCoreError


def invoke_model(client: BedrockRuntimeClient, body: dict) -> dict:
    """Invoke a Bedrock model with proper error handling."""
    try:
        response = client.invoke_model(
            modelId="anthropic.claude-3-sonnet",
            body=json.dumps(body),
        )
        return json.loads(response["body"].read())

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        if error_code == "ThrottlingException":
            raise RateLimitError(f"Rate limited: {error_message}") from e
        elif error_code == "ValidationException":
            raise ValidationError(f"Invalid request: {error_message}") from e
        elif error_code == "AccessDeniedException":
            raise PermissionError(f"Access denied: {error_message}") from e
        else:
            raise ServiceError(f"AWS error: {error_code} - {error_message}") from e

    except BotoCoreError as e:
        raise ServiceError(f"AWS client error: {e}") from e
```

## Bedrock Converse API

Use the Converse API for multi-turn conversations:

```python
from mypy_boto3_bedrock_runtime import BedrockRuntimeClient
from mypy_boto3_bedrock_runtime.type_defs import (
    ContentBlockTypeDef,
    ConverseResponseTypeDef,
    MessageTypeDef,
    ToolConfigurationTypeDef,
)


def converse(
    client: BedrockRuntimeClient,
    messages: list[MessageTypeDef],
    system_prompt: str,
    tools: ToolConfigurationTypeDef | None = None,
) -> ConverseResponseTypeDef:
    """Send a conversation to Bedrock."""
    kwargs: dict = {
        "modelId": "anthropic.claude-3-sonnet-20240229-v1:0",
        "messages": messages,
        "system": [{"text": system_prompt}],
    }

    if tools:
        kwargs["toolConfig"] = tools

    return client.converse(**kwargs)
```

## S3 Operations

```python
from mypy_boto3_s3 import S3Client
from botocore.exceptions import ClientError


def upload_file(client: S3Client, bucket: str, key: str, data: bytes) -> str:
    """Upload data to S3.

    :param client: S3 client.
    :param bucket: Bucket name.
    :param key: Object key.
    :param data: File contents.
    :returns: S3 URI.
    :raises ServiceError: If upload fails.
    """
    try:
        client.put_object(Bucket=bucket, Key=key, Body=data)
        return f"s3://{bucket}/{key}"
    except ClientError as e:
        raise ServiceError(f"Failed to upload to S3: {e}") from e


def download_file(client: S3Client, bucket: str, key: str) -> bytes:
    """Download data from S3.

    :param client: S3 client.
    :param bucket: Bucket name.
    :param key: Object key.
    :returns: File contents.
    :raises FileNotFoundError: If object doesn't exist.
    :raises ServiceError: If download fails.
    """
    try:
        response = client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            raise FileNotFoundError(f"S3 object not found: s3://{bucket}/{key}") from e
        raise ServiceError(f"Failed to download from S3: {e}") from e
```

## SSM Parameter Store

For configuration and secrets:

```python
from mypy_boto3_ssm import SSMClient
from botocore.exceptions import ClientError


def get_parameter(client: SSMClient, name: str, decrypt: bool = True) -> str:
    """Get a parameter from SSM Parameter Store.

    :param client: SSM client.
    :param name: Parameter name.
    :param decrypt: Whether to decrypt SecureString parameters.
    :returns: Parameter value.
    :raises KeyError: If parameter doesn't exist.
    """
    try:
        response = client.get_parameter(Name=name, WithDecryption=decrypt)
        return response["Parameter"]["Value"]
    except ClientError as e:
        if e.response["Error"]["Code"] == "ParameterNotFound":
            raise KeyError(f"SSM parameter not found: {name}") from e
        raise
```

## Timeouts and Retries

Configure timeouts and retries explicitly:

```python
from botocore.config import Config

# Configure with custom timeouts and retries
config = Config(
    connect_timeout=5,
    read_timeout=60,
    retries={"max_attempts": 3, "mode": "adaptive"},
)

client = boto3.client("bedrock-runtime", config=config)
```

## Region Configuration

Use environment variables for region:

```python
import os
import boto3

# Let boto3 use standard AWS_REGION or AWS_DEFAULT_REGION env vars
client = boto3.client("bedrock-runtime")

# Or explicit region from config
region = os.environ.get("AWS_REGION", "eu-west-2")
client = boto3.client("bedrock-runtime", region_name=region)
```

## Testing with Mocks

Mock AWS clients in tests:

```python
from unittest.mock import MagicMock, patch


class TestBedrockClient(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_client = MagicMock()

    @patch("src.agent.bedrock_client.boto3.client")
    def test_invoke_model_returns_response(self, mock_boto3: MagicMock) -> None:
        mock_boto3.return_value = self.mock_client
        self.mock_client.converse.return_value = {
            "output": {"message": {"content": [{"text": "Hello"}]}},
            "usage": {"inputTokens": 10, "outputTokens": 5},
        }

        client = BedrockClient()
        result = client.converse(messages=[{"role": "user", "content": "Hi"}])

        self.assertEqual(result["output"]["message"]["content"][0]["text"], "Hello")
```
