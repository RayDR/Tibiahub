"""Typed, bounded, credential-safe failure classification."""

from __future__ import annotations

import socket
from dataclasses import dataclass

from sqlalchemy.exc import OperationalError


class KnowledgeWorkerFailure(Exception):
    code = "knowledge_worker_failure"
    retryable = False
    safe_message = "Knowledge processing could not continue safely."


class ProviderTimeoutError(KnowledgeWorkerFailure):
    code = "provider_timeout"
    retryable = True
    safe_message = "The provider request timed out."


class ProviderConnectionError(KnowledgeWorkerFailure):
    code = "provider_connection"
    retryable = True
    safe_message = "The provider connection was temporarily unavailable."


class ProviderHTTPError(KnowledgeWorkerFailure):
    def __init__(self, status_code: int, retry_after_seconds: int | None = None):
        super().__init__(status_code)
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds


class InvalidProviderConfigurationError(KnowledgeWorkerFailure):
    code = "invalid_provider_configuration"
    safe_message = "The provider configuration is invalid."


class UnsupportedKnowledgeJobError(KnowledgeWorkerFailure):
    code = "unsupported_knowledge_job"
    safe_message = "The provider does not support this knowledge job."


class MalformedProviderPayloadError(KnowledgeWorkerFailure):
    code = "malformed_provider_payload"
    safe_message = "The provider response did not match the required contract."


class EmptyProviderResponseError(KnowledgeWorkerFailure):
    code = "empty_provider_response"
    safe_message = "The provider returned no usable knowledge records."


class ProviderResponseEnvelopeError(KnowledgeWorkerFailure):
    code = "provider_error_envelope"
    safe_message = "The provider returned an error response."


class UnsafeProviderTextError(KnowledgeWorkerFailure):
    code = "unsafe_provider_text"
    safe_message = "The provider response contained unsafe text."


class OversizedProviderResponseError(KnowledgeWorkerFailure):
    code = "oversized_provider_response"
    safe_message = "The provider response exceeded the safe size limit."


class MissingProviderAuthorizationError(KnowledgeWorkerFailure):
    code = "provider_authorization_missing"
    safe_message = "Provider authorization is not configured."


class InvalidNormalizationContractError(KnowledgeWorkerFailure):
    code = "invalid_normalization_contract"
    safe_message = "The normalization result was invalid."


class JobCancelledError(KnowledgeWorkerFailure):
    code = "job_cancelled"
    safe_message = "The knowledge job was cancelled."


class ExpiredLeaseError(KnowledgeWorkerFailure):
    code = "expired_lease"
    retryable = True
    safe_message = "The prior worker lease expired."


@dataclass(frozen=True, slots=True)
class ClassifiedFailure:
    code: str
    retryable: bool
    safe_message: str
    retry_after_seconds: int | None = None


def classify_failure(error: BaseException) -> ClassifiedFailure:
    if isinstance(error, ProviderHTTPError):
        retryable = error.status_code in {429, 502, 503, 504}
        return ClassifiedFailure(
            code=f"provider_http_{error.status_code}",
            retryable=retryable,
            safe_message=(
                "The provider asked TibiaHub to retry later."
                if error.status_code == 429
                else "The provider returned a temporary service error."
                if retryable
                else "The provider rejected the request permanently."
            ),
            retry_after_seconds=error.retry_after_seconds if error.status_code == 429 else None,
        )
    if isinstance(error, KnowledgeWorkerFailure):
        return ClassifiedFailure(error.code, error.retryable, error.safe_message)
    if isinstance(error, (TimeoutError, socket.timeout)):
        return ClassifiedFailure("provider_timeout", True, "The provider request timed out.")
    if isinstance(error, (ConnectionError, socket.gaierror)):
        return ClassifiedFailure("provider_connection", True, "The provider connection was temporarily unavailable.")
    if isinstance(error, OperationalError):
        return ClassifiedFailure(
            "database_connection_interrupted",
            True,
            "The database connection was interrupted before completion.",
        )
    return ClassifiedFailure("unexpected_worker_failure", False, "Knowledge processing failed safely.")


def retry_delay_seconds(
    attempt_number: int,
    *,
    retry_after_seconds: int | None = None,
    jitter_fraction: float = 0.0,
    base_seconds: int = 5,
    maximum_seconds: int = 3600,
) -> int:
    bounded_attempt = max(1, min(attempt_number, 20))
    exponential = min(maximum_seconds, base_seconds * (2 ** (bounded_attempt - 1)))
    jitter = int(exponential * 0.25 * max(0.0, min(jitter_fraction, 1.0)))
    requested = max(0, min(retry_after_seconds or 0, maximum_seconds))
    return min(maximum_seconds, max(exponential + jitter, requested))
