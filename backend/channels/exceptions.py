"""Internal domain failures; future APIs must translate these to safe responses."""


class ChannelError(Exception):
    pass


class AccountUnavailable(ChannelError):
    pass


class ProviderNotConfigured(ChannelError):
    pass


class UnsupportedProvider(ChannelError):
    pass


class UnsupportedChannel(ChannelError):
    pass


class ProviderConfigurationError(ChannelError):
    pass
