#!/usr/bin/env python3
"""
Test script to verify AWS Bedrock connectivity.

Tests three layers:
  1. boto3 direct   — raw AWS SDK call (proves credentials work)
  2. litellm        — LiteLLM routing (proves bedrock/ prefix works)
  3. docling-graph  — actual LiteLLMClient code path (proves our integration works)

Uses your local AWS CLI credentials (profile/env vars) — no IAM role ARN needed.
In Lambda, boto3 auto-detects the execution role; locally it uses ~/.aws/credentials.

Usage:
    python scripts/test_bedrock.py
"""

import json
import sys

# ---------- config ----------
REGION = "eu-west-1"
MODEL_ID = "eu.anthropic.claude-sonnet-4-6"
# -----------------------------


def test_boto3_direct():
    """Test Bedrock directly via boto3 (no LiteLLM)."""
    print("─── Test 1: boto3 direct ───")
    import boto3

    client = boto3.client("bedrock-runtime", region_name=REGION)

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 64,
        "messages": [{"role": "user", "content": "Say hello in one sentence."}],
    })

    print(f"  Region : {REGION}")
    print(f"  Model  : {MODEL_ID}")
    print(f"  Calling bedrock-runtime invoke_model ...")

    resp = client.invoke_model(modelId=MODEL_ID, body=body, contentType="application/json")
    result = json.loads(resp["body"].read())
    text = result["content"][0]["text"]
    print(f"  ✅ Response: {text}\n")
    return True


def test_litellm():
    """Test Bedrock via LiteLLM (same path the package uses)."""
    print("─── Test 2: litellm completion ───")
    import litellm

    model_name = f"bedrock/{MODEL_ID}"
    print(f"  Model  : {model_name}")
    print(f"  Region : {REGION}")
    print(f"  Calling litellm.completion ...")

    resp = litellm.completion(
        model=model_name,
        messages=[{"role": "user", "content": "Say hello in one sentence."}],
        max_tokens=64,
        aws_region_name=REGION,
    )
    text = resp.choices[0].message.content
    print(f"  ✅ Response: {text}\n")
    return True


def test_docling_graph_client():
    """Test Bedrock through the actual docling-graph LiteLLMClient code path.

    This exercises:
      - resolve_effective_model_config() → provider registry lookup
      - build_litellm_model_name()       → "bedrock/" prefix
      - _resolve_connection()            → AWS region resolution
      - LiteLLMClient._build_request()   → aws_region_name injection
      - LiteLLMClient.get_json_response()→ full request/response cycle
    """
    print("─── Test 3: docling-graph LiteLLMClient ───")
    import os

    # Set the AWS region env var so _resolve_connection() picks it up
    os.environ["AWS_REGION_NAME"] = REGION

    from docling_graph.llm_clients import get_client
    from docling_graph.llm_clients.config import resolve_effective_model_config

    # Resolve config through docling-graph's registry (same as pipeline does)
    effective_config = resolve_effective_model_config(
        provider_id="bedrock",
        model_id=MODEL_ID,
    )

    print(f"  Provider    : {effective_config.provider_id}")
    print(f"  Model       : {effective_config.model_id}")
    print(f"  LiteLLM ID  : {effective_config.litellm_model}")
    print(f"  AWS Region  : {effective_config.connection.aws_region}")
    print(f"  API Key     : {'(none — using IAM)' if not effective_config.connection.api_key else '***'}")

    # Instantiate the actual client class
    client_class = get_client("bedrock")
    client = client_class(model_config=effective_config)

    # Use get_json_response — the real extraction interface
    schema = json.dumps({
        "type": "object",
        "properties": {
            "greeting": {"type": "string", "description": "A short greeting"}
        },
        "required": ["greeting"],
    })

    print(f"  Calling LiteLLMClient.get_json_response() ...")
    result = client.get_json_response(
        prompt={
            "system": "You are a helpful assistant. Always respond with valid JSON only, no markdown fences.",
            "user": 'Return a JSON object like {"greeting": "Hello!"} with a short greeting message.',
        },
        schema_json=schema,
        structured_output=False,  # Bedrock doesn't support strict structured output
    )

    print(f"  ✅ Response: {result}")
    assert isinstance(result, (dict, list)), f"Expected dict/list, got {type(result)}"
    print(f"  ✅ get_json_response() returned valid JSON via the full docling-graph code path\n")
    return True


def main():
    tests = [test_boto3_direct, test_litellm, test_docling_graph_client]
    ok = True
    for test_fn in tests:
        try:
            test_fn()
        except Exception as e:
            print(f"  ❌ Failed: {e}\n")
            ok = False

    if ok:
        print("All tests passed ✅")
    else:
        print("Some tests failed ❌")
        sys.exit(1)


if __name__ == "__main__":
    main()
