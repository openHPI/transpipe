from django import template
from django.template import TemplateSyntaxError
from django.template.defaulttags import url
from django.urls import reverse, NoReverseMatch

register = template.Library()


@register.simple_tag
def call_method(obj, method_name, *args):
    method = getattr(obj, method_name)
    return method(*args)


@register.filter
def get_subtitle(obj, language):
    return obj.get_subtitle(language)


css_map = {
    0: "bg-success",
    1: "table-success",
    2: "table-primary",
    3: "table-warning",
    4: "bg-warning",
    5: "bg-secondary",
    6: "table-danger",
    -1: "table-secondary",
}

css_map = {
    0: "bg-color-green",
    1: "bg-color-blue",
    2: "bg-color-light-blue",
    3: "bg-color-orange",
    4: "bg-color-pink",
    5: "bg-color-dark-grey",
    6: "bg-color-dark-orange",
    -1: "table-secondary",
}


@register.filter
def get_color(value):
    return css_map[value]


@register.filter
def dict_key(d, k):
    """Returns the given key from a dictionary."""
    return d[k]


@register.simple_tag(takes_context=True)
def tenant_url(context, viewname, *args, **kwargs):
    if args:
        raise TemplateSyntaxError("Parameters have to be explicitly named for tenant_url")

    tenant = None

    if 'tenant' in kwargs:
        # first use provided tenant
        tenant = kwargs.pop('tenant')
    else:
        raise TemplateSyntaxError("Tenant has to be provided")

    # elif 'request' in context:
    #     # if not provided, then try to extract and use the tenant of current user
    #     request = context['request']
    #
    #     if request.user.is_authenticated:
    #         tenant = request.tenant

    # if tenant set, then inject slug of tenant to url
    if tenant:
        kwargs['tenant_slug'] = tenant.slug

    try:
        return reverse(viewname, args=args, kwargs=kwargs)
    except NoReverseMatch:
        del kwargs['tenant_slug']
        return reverse(viewname, args=args, kwargs=kwargs)
