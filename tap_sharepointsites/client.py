"""REST client handling, including sharepointsitesStream base class."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from urllib.parse import parse_qsl

import requests
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential, ClientSecretCredential
from singer_sdk.authenticators import BearerTokenAuthenticator
from singer_sdk.helpers.jsonpath import extract_jsonpath
from singer_sdk.pagination import BaseHATEOASPaginator
from singer_sdk.streams import RESTStream

SCHEMAS_DIR = Path(__file__).parent / Path("./schemas")
LOGGER = logging.getLogger("Some logger")


class GraphHATEOASPaginator(BaseHATEOASPaginator):
    """Basic paginator."""

    def get_next_url(self, response):
        """Return the URL for next page."""
        return response.json().get("@odata.nextLink")


class sharepointsitesStream(RESTStream):
    """sharepointsites stream class."""

    # OR use a dynamic url_base:

    @property
    def authenticator(self) -> BearerTokenAuthenticator:
        """Return a new authenticator object."""
        ad_scope = "https://graph.microsoft.com/.default"
        client_id = self.config.get("client_id")
        client_secret = self.config.get("client_secret")
        tenant_id = self.config.get("tenant_id")

        # Choose the credential based on the available config parameters
        if client_id and client_secret and tenant_id:
            # Use ClientSecretCredential for client credentials flow
            creds = ClientSecretCredential(client_id=client_id, client_secret=client_secret, tenant_id=tenant_id)
        elif client_id:
            # Use ManagedIdentityCredential if only client_id is provided (for Managed Identity)
            creds = ManagedIdentityCredential(client_id=client_id)
        else:
            # Use DefaultAzureCredential as a fallback
            creds = DefaultAzureCredential()

        # Get the token for the specified scope
        token = creds.get_token(ad_scope)

        # Return a BearerTokenAuthenticator with the acquired token
        return BearerTokenAuthenticator.create_for_stream(self, token=token.token)

    @property
    def http_headers(self) -> dict:
        """Return the http headers needed."""
        headers = {}
        if "user_agent" in self.config:
            headers["User-Agent"] = self.config.get("user_agent")
        # If not using an authenticator, you may also provide inline auth headers:
        # headers["Private-Token"] = self.config.get("auth_token")
        return headers

    def get_new_paginator(self):
        """Return paginator class."""
        return GraphHATEOASPaginator()

    def get_url_params(
        self, context: Optional[dict], next_page_token: Optional[Any]
    ) -> Dict[str, Any]:
        """Return next page link or None."""
        if next_page_token:
            return dict(parse_qsl(next_page_token.query))
        return {}

    def parse_response(self, response: requests.Response) -> Iterable[dict]:
        """Parse the response and return an iterator of result records."""
        # TODO: Parse response body and return a set of records.
        yield from extract_jsonpath(self.records_jsonpath, input=response.json())

    def post_process(self, row: dict, context: Optional[dict]) -> dict:
        """As needed, append or transform raw data to match expected structure."""
        row["_loaded_at"] = datetime.utcnow()
        return row
