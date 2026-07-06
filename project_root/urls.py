
from django.contrib import admin
from django.urls import path , include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

from django.apps import apps
try:
    class UniversalModelAdmin(admin.ModelAdmin):
        def get_list_display(self, request):
            # Display all standard fields in the admin list view
            return [field.name for field in self.model._meta.fields]

    models = apps.get_models()
    for model in models:
        try:
            admin.site.register(model, UniversalModelAdmin)
        except admin.sites.AlreadyRegistered:
            pass
except Exception:
    pass

urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),

    path('api/', include('api.urls')),
]

# Serve media and static files in development
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)