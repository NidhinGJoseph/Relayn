"""Deployment-owned, per-account file boundary; never persist credentials in models."""

import json
from pathlib import Path

from django.conf import settings

from channels.exceptions import ProviderConfigurationError
from channels.models import ChannelAccount


def load_provider_configuration(account: ChannelAccount) -> dict[str, object]:
    """Trusted adapter/service use only, after tenant-scoped account resolution.

    Deployment must restrict directory/file ACLs to operators and the application
    identity. Never return this mapping from an API or log it.
    """
    if account._state.adding:
        raise ValueError("A persisted channel account is required.")
    if not settings.CHANNEL_SECRETS_DIR:
        raise ProviderConfigurationError("Configure CHANNEL_SECRETS_DIR before sending.")
    root = Path(settings.CHANNEL_SECRETS_DIR)
    if not root.is_absolute():
        raise ProviderConfigurationError("CHANNEL_SECRETS_DIR must be an absolute path.")
    path = root / str(account.organization_id) / f"{account.pk}.json"
    try:
        configuration = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ProviderConfigurationError(
            "Provision a readable, valid provider configuration file for this account."
        ) from None
    if not isinstance(configuration, dict) or not configuration:
        raise ProviderConfigurationError("Provider configuration must be a nonempty JSON object.")
    return configuration
