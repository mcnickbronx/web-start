from django.contrib import admin
from django.http import HttpResponse
from django.urls import path

admin.site.site_header = "Администрирование"
admin.site.site_title = "Администрирование"

urlpatterns = [
    path("admin/", admin.site.urls),
    # Бэкенд — админка и API, в поиске им не место (Swagger на /api/docs тоже)
    path("robots.txt", lambda request: HttpResponse("User-agent: *\nDisallow: /\n", content_type="text/plain")),
]
