"""Azure clients (Entra ID auth via az login) with an optional corporate-proxy TLS workaround."""

import os
import ssl
from functools import lru_cache

from azure.ai.contentunderstanding import ContentUnderstandingClient
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import DefaultHttpx2Client, OpenAI

from .config import get_settings

COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"


def _tls_context() -> ssl.SSLContext:
    # Netskope's root CA lacks keyUsage, which strict X.509 verification (Py3.13 default) rejects
    ctx = ssl.create_default_context(cafile=os.getenv("REQUESTS_CA_BUNDLE") or None)
    ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return ctx


def _requests_transport():
    import requests
    from azure.core.pipeline.transport import RequestsTransport
    from requests.adapters import HTTPAdapter

    ctx = _tls_context()

    class _Adapter(HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            kwargs["ssl_context"] = ctx
            return super().init_poolmanager(*args, **kwargs)

    session = requests.Session()
    session.mount("https://", _Adapter())
    return RequestsTransport(session=session, session_owner=False)


@lru_cache
def credential() -> DefaultAzureCredential:
    # Local prototype: skip the managed-identity (IMDS) probe, which adds ~10s on dev machines
    return DefaultAzureCredential(exclude_interactive_browser_credential=True, exclude_managed_identity_credential=True)


@lru_cache
def cu_client() -> ContentUnderstandingClient:
    settings = get_settings()
    kwargs = {"transport": _requests_transport()} if settings.relax_x509_strict else {}
    cred = AzureKeyCredential(settings.cu_api_key) if settings.cu_api_key else credential()
    return ContentUnderstandingClient(endpoint=settings.cu_endpoint, credential=cred, **kwargs)


@lru_cache
def openai_client() -> OpenAI:
    settings = get_settings()
    http_client = DefaultHttpx2Client(verify=_tls_context()) if settings.relax_x509_strict else None
    return OpenAI(
        base_url=f"{settings.aoai_endpoint.rstrip('/')}/openai/v1/",
        api_key=settings.aoai_api_key or get_bearer_token_provider(credential(), COGNITIVE_SCOPE),
        http_client=http_client,
        max_retries=3,
        timeout=300,
    )
