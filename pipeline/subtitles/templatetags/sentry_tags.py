import sentry_sdk
from django import template

register = template.Library()


@register.simple_tag
def sentry_release():
    return sentry_sdk.client.get_options()['release'] or ''


@register.simple_tag
def sentry_environment():
    return sentry_sdk.client.get_options()['environment'] or ''
