"""Provider transport boundary. No adapters are installed in Stage 3."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass

from channels.exceptions import ProviderNotConfigured, UnsupportedChannel, UnsupportedProvider


@dataclass(frozen=True)
class OutboundMessage:
    recipient: str
    text: str


@dataclass(frozen=True)
class SentMessage:
    external_id: str


@dataclass(frozen=True)
class IncomingMessage:
    """Minimal normalized inbound text; provider envelopes stay inside the adapter."""

    external_id: str
    sender: str
    text: str


class ProviderAdapter(ABC):
    supported_channels: frozenset[str] = frozenset()

    @abstractmethod
    def validate_configuration(self, *, configuration: Mapping[str, object]) -> None:
        """Raise ProviderConfigurationError for invalid adapter-owned configuration."""

    @abstractmethod
    def send_message(
        self, *, message: OutboundMessage, configuration: Mapping[str, object]
    ) -> SentMessage:
        """Send or raise an explicit failure; never fabricate delivery success."""

    @abstractmethod
    def normalize_webhook_event(self, *, payload: Mapping[str, object]) -> list[IncomingMessage]:
        """Translate verified payloads; webhook authentication belongs to the adapter ingress."""


# Explicit code registration only, never a client-controlled import path or fallback.
PROVIDERS: dict[str, type[ProviderAdapter]] = {}


def resolve_provider(provider: str, channel: str) -> type[ProviderAdapter]:
    if not provider:
        raise ProviderNotConfigured("Configure a provider for this channel account before sending.")
    adapter = PROVIDERS.get(provider)
    if adapter is None:
        raise UnsupportedProvider("The configured provider has no installed adapter.")
    if channel not in adapter.supported_channels:
        raise UnsupportedChannel("The configured provider does not support this channel.")
    return adapter
