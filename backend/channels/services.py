from django.shortcuts import get_object_or_404

from channels.exceptions import AccountUnavailable
from channels.models import ChannelAccount
from channels.providers import OutboundMessage, SentMessage, resolve_provider
from channels.secrets import load_provider_configuration
from core.tenancy import resolve_membership


def get_channel_account(*, user, organization_id, account_id):
    membership = resolve_membership(user, organization_id)
    return get_object_or_404(
        ChannelAccount.objects.select_related("channel").filter(
            organization=membership.organization
        ),
        pk=account_id,
    )


def send_message(*, user, organization_id, account_id, message: OutboundMessage) -> SentMessage:
    """Internal dispatch seam, not a public sending API or delivery workflow.

    Future product callers must additionally enforce send permissions/entitlements.
    This stage establishes membership, tenant scope and transport availability only.
    """
    account = get_channel_account(user=user, organization_id=organization_id, account_id=account_id)
    if account.status != ChannelAccount.Status.ACTIVE:
        raise AccountUnavailable("The channel account must be active before sending.")
    adapter = resolve_provider(account.provider, account.channel_id)()
    configuration = load_provider_configuration(account)
    adapter.validate_configuration(configuration=configuration)
    return adapter.send_message(message=message, configuration=configuration)
