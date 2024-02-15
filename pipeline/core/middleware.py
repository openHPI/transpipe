from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.utils.functional import SimpleLazyObject

from core.models import Tenant


class AuthenticationTenantMiddleware(MiddlewareMixin):
    @classmethod
    def get_tenant(cls, request):
        return request.user.tenant

    @classmethod
    def get_tenant_by_slug(cls, tenant_slug):
        try:
            tenant = Tenant.objects.get(slug=tenant_slug)
        except Tenant.DoesNotExist:
            tenant = None

        return tenant

    def process_request(self, request):
        assert hasattr(request, 'user'), (
            "This middleware requires request.user to be populated. "
            "Install django.contrib.auth.middleware.AuthenticationMiddleware in your MIDDLEWARE setting"
        )

        if request.user.is_authenticated:
            request.tenant = SimpleLazyObject(lambda: self.get_tenant(request))
        else:
            request.tenant = None

        if request.resolver_match and 'tenant_slug' in request.resolver_match.kwargs:
            tenant_slug = request.resolver_match.kwargs['tenant_slug']
            request.tenant = SimpleLazyObject(lambda: self.get_tenant_by_slug(tenant_slug))

    def process_response(self, request, response):
        # if request.resolver_match:
        #     if 'tenant_slug' in request.resolver_match.kwargs:
        #         tenant_slug = request.resolver_match.kwargs['tenant_slug']
        #         if request.tenant and tenant_slug != request.tenant.slug:
        #             return HttpResponse(f"The tenant in URL ({tenant_slug}) does not match to your assigned tenant "
        #                                 f"({request.tenant.slug})", status=400)

        return response
