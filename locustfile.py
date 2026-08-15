# This Locust script is intentionally defensive.
# The supplied input contains no actual HTTP requests, only a devcontainer config.
# Therefore, it validates the configured host and can be extended once a real
# collection is provided. Do not invent endpoints or auth that are not in the source.

import os
import json
import base64
import uuid
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from locust import HttpUser, task, between, events

# Load environment variables from .env (if present)
load_dotenv()

ENABLE_LOGGING = os.getenv("ENABLE_LOGGING", "True").lower() in ("1", "true", "yes", "on")
TARGET_HOST = os.getenv("HOST_URL")
HEALTH_PATH = os.getenv("HEALTH_PATH", "/health")

if ENABLE_LOGGING:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def log_debug(message: str, **kwargs: Any):
    if ENABLE_LOGGING:
        logging.info(message)
        if kwargs:
            logging.info(json.dumps(kwargs, default=str, indent=2))

def required_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if value is None or value == "":
        raise RuntimeError(f"Missing required environment variable: {var_name}")
    return value

class ApiUser(HttpUser):
    wait_time = between(1, 3)
    timeout_duration = 90

    # Required by your spec: host must be set in ApiUser
    # The input collection does not contain a valid host, so read it from env
    host = TARGET_HOST or "https://example.invalid"

    # Instance variables for generated IDs; can be used later when a real collection exists
    created_resource_id: Optional[str] = None
    request_counter = 0

    def _build_auth_headers(self) -> Dict[str, str]:
        """
        Flexible auth handling:
        - API key: header using env API_KEY_HEADER (default: x-api-key) or query param
        - Bearer token: Authorization: Bearer <token>
        - Basic auth: Authorization: Basic <base64(username:password)>
        - No auth: return {}
        """
        headers: Dict[str, str] = {}

        api_key = os.getenv("API_KEY")
        api_key_header = os.getenv("API_KEY_HEADER", "x-api-key")

        if api_key:
            headers[api_key_header] = api_key

        bearer_token = os.getenv("BEARER_TOKEN")
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"

        username = os.getenv("USERNAME")
        password = os.getenv("PASSWORD")
        if username and password and "Authorization" not in headers:
            basic = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {basic}"

        return headers

    def _safe_json(self, payload: Any) -> Any:
        return payload

    def _log_request(self, method: str, url: str, headers: Optional[Dict[str, str]] = None, payload: Optional[Any] = None, error: Optional[str] = None):
        if not ENABLE_LOGGING:
            return
        log_debug(f"Request: {method} {url}", headers=headers, payload=payload, error=error)

    def _handle_response(self, response, operation_name: str, expected_statuses: set):
        """
        Proper Locust response handling:
        - Response must be marked as success/failure explicitly via catch_response
        - Supports common 2xx success patterns
        """
        if response.status_code in expected_statuses:
            response.success()
            log_debug(f"Success: {operation_name}", status_code=response.status_code, url=response.url)
            return True
        else:
            response.failure(
                f"{operation_name} failed with HTTP {response.status_code}. "
                f"URL={response.url}. "
                f"Body={response.text[:1000]}"
            )
            log_debug(
                f"Failure: {operation_name}",
                status_code=response.status_code,
                url=response.url,
                headers=dict(response.request.headers),
                body=response.text[:2000],
                request_body=getattr(response.request, "body", None),
            )
            return False

    def on_start(self):
        """
        Called once per user before scenario runs.
        We do not fabricate auth or operations because the supplied file does not define them.
        """
        if not self.host or self.host == "https://example.invalid":
            raise RuntimeError(
                "HOST_URL environment variable is required. "
                "The supplied Postman Collection does not include a host or API path."
            )

        # The collection contains no real operations, so we run a safe connectivity check.
        self.headers = self._build_auth_headers()
        self.headers.setdefault("Accept", "application/json")

        log_debug("Starting user session", host=self.host, headers=self.headers)

    @task
    def run_scenario(self):
        """
        Sequence of operations:
        - The input collection does not contain any actual HTTP operations.
        - This method performs a single health/connectivity check only.
        - Once a valid API collection is provided, replace this with the exact request flow.
        """
        self.request_counter += 1
        url = f"{self.host.rstrip('/')}{HEALTH_PATH}"
        headers = dict(self.headers)

        self._log_request("GET", url, headers=headers)

        with self.client.get(
            url,
            headers=headers,
            name="GET /health (connectivity check)",
            catch_response=True,
            timeout=self.timeout_duration
        ) as response:
            # Accept common successful responses: 200-299
            success = self._handle_response(response, "GET /health", {200, 201, 202, 204})
            if not success:
                # This is the only run available without actual API definitions.
                # In a real collection, this would be followed by other operations in sequence.
                log_debug("Health check failed; no further operations can be generated without a valid Postman API collection", url=url)

    def on_stop(self):
        """
        Cleanup logic.
        There are no created resources in the supplied input, so no API cleanup is possible.
        When a valid collection is provided, add DELETE/PATCH calls for resources created during test.
        """
        log_debug("Stopping user", created_resource_id=self.created_resource_id)

# Example local execution:
# 1) export HOST_URL=https://api.example.com
# 2) export HEALTH_PATH=/health
# 3) export ENABLE_LOGGING=True
# 4) locust -f locustfile.py -u 200 -r 10 --run-time 120s
#
# For a valid API collection, the run_scenario method should be replaced with the exact
# sequence from the Postman collection and each request should use:
#   - name="..."
#   - catch_response=True
#   - timeout=self.timeout_duration
#   - response.success()/failure() with meaningful messages