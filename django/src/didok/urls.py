from django.conf.urls import *
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

from didok.mapview import views

import django.views.static

urlpatterns = [
        path('', views.route_map_view),
        path('didokstops/', include('didok.stopview.urls')),
]
# for development
urlpatterns += static(settings.MEDIA_URL, document_root = settings.MEDIA_ROOT)

