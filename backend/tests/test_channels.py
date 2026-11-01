import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.http import Http404
from django.test import SimpleTestCase, TestCase, override_settings

from channels.exceptions import (
    AccountUnavailable,
    ProviderConfigurationError,
    ProviderNotConfigured,
    UnsupportedChannel,
    UnsupportedProvider,
)
from channels.models import Channel, ChannelAccount
from channels.providers import PROVIDERS, OutboundMessage, ProviderAdapter, resolve_provider
from channels.secrets import load_provider_configuration
from channels.services import get_channel_account, send_message
from core.models import Organization, OrganizationMembership, User


class ChannelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(name="One")
        cls.other = Organization.objects.create(name="Other")
        cls.user = User.objects.create_user(username="member")
        cls.outsider = User.objects.create_user(
            username="outsider", is_staff=True, is_superuser=True
        )
        OrganizationMembership.objects.create(
            user=cls.user, organization=cls.organization, role="OWNER"
        )
        OrganizationMembership.objects.create(
            user=cls.outsider, organization=cls.other, role="OWNER"
        )
        cls.channel, _ = Channel.objects.get_or_create(code=Channel.Type.WHATSAPP)
        cls.account = ChannelAccount.objects.create(
            organization=cls.organization, channel=cls.channel, name="Support"
        )
        cls.foreign = ChannelAccount.objects.create(
            organization=cls.other, channel=cls.channel, name="Other"
        )

    def dispatch(self):
        return send_message(
            user=self.user,
            organization_id=self.organization.pk,
            account_id=self.account.pk,
            message=OutboundMessage(recipient="recipient", text="hello"),
        )

    def test_organization_ownership_and_scoped_lookup(self):
        account = get_channel_account(
            user=self.user, organization_id=self.organization.pk, account_id=self.account.pk
        )
        self.assertEqual(account.organization, self.organization)
        self.assertEqual(list(self.organization.channel_accounts.all()), [self.account])
        with self.assertRaises(IntegrityError), transaction.atomic():
            ChannelAccount.objects.create(channel=self.channel, name="Missing tenant")

    def test_cross_tenant_account_ids_and_staff_have_no_bypass(self):
        for user, organization_id, account_id in [
            (self.user, self.organization.pk, self.foreign.pk),
            (self.user, self.other.pk, self.foreign.pk),
            (self.outsider, self.organization.pk, self.account.pk),
        ]:
            with self.subTest(user=user.pk, organization_id=organization_id):
                with self.assertRaises(Http404):
                    send_message(
                        user=user,
                        organization_id=organization_id,
                        account_id=account_id,
                        message=OutboundMessage(recipient="recipient", text="hello"),
                    )

    def test_inactive_member_cannot_access_accounts(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        with self.assertRaises(Http404):
            self.dispatch()

    def test_default_and_disabled_status_block_sending(self):
        self.assertEqual(self.account.status, ChannelAccount.Status.INACTIVE)
        for status in [ChannelAccount.Status.INACTIVE, ChannelAccount.Status.DISABLED]:
            self.account.status = status
            self.account.save(update_fields=["status"])
            with self.assertRaises(AccountUnavailable):
                self.dispatch()

    def test_active_account_without_provider_fails_explicitly(self):
        self.account.status = ChannelAccount.Status.ACTIVE
        self.account.save(update_fields=["status"])
        with self.assertRaises(ProviderNotConfigured):
            self.dispatch()
        self.account.provider = "meta"
        self.account.save(update_fields=["provider"])
        with self.assertRaises(UnsupportedProvider):
            self.dispatch()

    def test_database_rejects_invalid_status_and_channel(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            ChannelAccount.objects.filter(pk=self.account.pk).update(status="UNKNOWN")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Channel.objects.create(code="UNKNOWN")

    def test_secret_boundary_has_no_database_credentials(self):
        self.assertEqual(
            {field.name for field in ChannelAccount._meta.fields},
            {
                "id",
                "organization",
                "channel",
                "name",
                "provider",
                "status",
                "created_at",
                "updated_at",
            },
        )
        with override_settings(CHANNEL_SECRETS_DIR=""):
            with self.assertRaises(ProviderConfigurationError):
                load_provider_configuration(self.account)
        with tempfile.TemporaryDirectory() as directory:
            with override_settings(CHANNEL_SECRETS_DIR=directory):
                own_path = Path(directory) / str(self.organization.pk)
                own_path.mkdir()
                config_path = own_path / f"{self.account.pk}.json"
                config_path.write_text(json.dumps({"token": "test-only-secret"}), encoding="utf-8")
                self.assertEqual(
                    load_provider_configuration(self.account), {"token": "test-only-secret"}
                )
                with self.assertRaises(ProviderConfigurationError):
                    load_provider_configuration(self.foreign)
                for content in ["invalid", "[]", "{}"]:
                    config_path.write_text(content, encoding="utf-8")
                    with self.assertRaises(ProviderConfigurationError) as failure:
                        load_provider_configuration(self.account)
                    self.assertNotIn(content, str(failure.exception))


class ProviderResolutionTests(SimpleTestCase):
    def test_no_production_provider_or_fallback(self):
        self.assertEqual(PROVIDERS, {})
        with self.assertRaises(ProviderNotConfigured):
            resolve_provider("", "WHATSAPP")
        with self.assertRaises(UnsupportedProvider):
            resolve_provider("meta", "WHATSAPP")

    def test_resolution_and_channel_support_use_explicit_registry(self):
        # Register the abstract contract as metadata only; no fake adapter is implemented.
        with patch.dict(PROVIDERS, {"contract": ProviderAdapter}, clear=True):
            with self.assertRaises(UnsupportedChannel):
                resolve_provider("contract", "WHATSAPP")
            with patch.object(ProviderAdapter, "supported_channels", frozenset({"WHATSAPP"})):
                self.assertIs(resolve_provider("contract", "WHATSAPP"), ProviderAdapter)
                for channel in ["INSTAGRAM", "MESSENGER", "WEBCHAT", "UNKNOWN"]:
                    with self.subTest(channel=channel), self.assertRaises(UnsupportedChannel):
                        resolve_provider("contract", channel)

    def test_provider_contract_cannot_send_without_implementation(self):
        with self.assertRaises(TypeError):
            ProviderAdapter()
