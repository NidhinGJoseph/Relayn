from django.db import IntegrityError, transaction
from django.test import TestCase

from billing.definitions import Capability, Limit
from billing.models import OrganizationEntitlement
from billing.services import (
    CapabilityUnavailable,
    get_limit,
    has_capability,
    require_capability,
    set_capability,
    set_limit,
)
from core.models import Organization


class EntitlementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(name="One")
        cls.other = Organization.objects.create(name="Other")

    def test_enabled_capability(self):
        for key in Capability:
            with self.subTest(key=key):
                set_capability(self.organization, key, enabled=True)
                self.assertTrue(has_capability(self.organization, key))
                self.assertIsNone(require_capability(self.organization, key))

    def test_disabled_capability_and_update(self):
        set_capability(self.organization, Capability.CRM, enabled=True)
        set_capability(self.organization, Capability.CRM, enabled=False)
        self.assertEqual(OrganizationEntitlement.objects.count(), 1)
        self.assertFalse(has_capability(self.organization, Capability.CRM))
        with self.assertRaises(CapabilityUnavailable) as failure:
            require_capability(self.organization, Capability.CRM)
        self.assertEqual(failure.exception.status_code, 403)
        self.assertEqual(failure.exception.get_codes(), "capability_unavailable")

    def test_missing_capability_fails_closed_without_creating_assignment(self):
        self.assertFalse(has_capability(self.organization, Capability.SHARED_INBOX))
        with self.assertRaises(CapabilityUnavailable):
            require_capability(self.organization, Capability.SHARED_INBOX)
        self.assertFalse(OrganizationEntitlement.objects.exists())

    def test_numeric_limits(self):
        self.assertIsNone(get_limit(self.organization, Limit.AGENT_LIMIT))
        for key, value in [(Limit.AGENT_LIMIT, 5), (Limit.WHATSAPP_NUMBER_LIMIT, 1)]:
            set_limit(self.organization, key, value=value)
            self.assertEqual(get_limit(self.organization, key), value)
        set_limit(self.organization, Limit.AGENT_LIMIT, value=0)
        self.assertEqual(get_limit(self.organization, Limit.AGENT_LIMIT), 0)
        self.assertEqual(OrganizationEntitlement.objects.count(), 2)

    def test_organization_isolation(self):
        set_capability(self.organization, Capability.CRM, enabled=True)
        set_limit(self.organization, Limit.AGENT_LIMIT, value=5)
        self.assertFalse(has_capability(self.other, Capability.CRM))
        self.assertIsNone(get_limit(self.other, Limit.AGENT_LIMIT))
        with self.assertRaises(CapabilityUnavailable):
            require_capability(self.other, Capability.CRM)
        set_capability(self.other, Capability.CRM, enabled=False)
        set_limit(self.other, Limit.AGENT_LIMIT, value=1)
        self.assertTrue(has_capability(self.organization, Capability.CRM))
        self.assertEqual(get_limit(self.organization, Limit.AGENT_LIMIT), 5)
        self.assertEqual(get_limit(self.other, Limit.AGENT_LIMIT), 1)

    def test_invalid_keys_and_types_are_explicit_errors(self):
        for key in ["UNKNOWN", Limit.AGENT_LIMIT]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                has_capability(self.organization, key)
            with self.assertRaises(ValueError):
                set_capability(self.organization, key, enabled=True)
        with self.assertRaises(ValueError):
            get_limit(self.organization, Capability.CRM)
        for value in [-1, True, 1.5, "5", None, 2**63]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                set_limit(self.organization, Limit.AGENT_LIMIT, value=value)
        for enabled in [1, "true", None]:
            with self.subTest(enabled=enabled), self.assertRaises(ValueError):
                set_capability(self.organization, Capability.CRM, enabled=enabled)
        with self.assertRaises(ValueError):
            has_capability(Organization(name="Unsaved"), Capability.CRM)
        with self.assertRaises(ValueError):
            has_capability(self.organization.pk, Capability.CRM)
        self.assertFalse(OrganizationEntitlement.objects.exists())

    def test_database_enforces_unique_organization_key(self):
        set_capability(self.organization, Capability.CRM, enabled=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            OrganizationEntitlement.objects.create(
                organization=self.organization, key=Capability.CRM, enabled=False
            )

    def test_database_enforces_typed_values_and_known_keys(self):
        for values in [
            {"key": "UNKNOWN", "enabled": True},
            {"key": Capability.CRM},
            {"key": Capability.CRM, "enabled": True, "limit": 1},
            {"key": Capability.CRM, "limit": 1},
            {"key": Limit.AGENT_LIMIT},
            {"key": Limit.AGENT_LIMIT, "enabled": True, "limit": 1},
            {"key": Limit.AGENT_LIMIT, "limit": -1},
        ]:
            with self.subTest(values=values):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    OrganizationEntitlement.objects.create(organization=self.organization, **values)
