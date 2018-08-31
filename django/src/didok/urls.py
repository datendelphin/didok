from django.conf.urls import *
from django.conf import settings

from didok.mapview import views

import django.views.static

urlpatterns = [
        url(r'^$', views.route_map_view),
        url(r'^didokstops/', include('didok.stopview.urls')),
]

# for development
if settings.DEBUG:
    urlpatterns += [
        url(r'^media/static/(?P<path>.*)$', django.views.static.serve,
        {'document_root': settings.MEDIA_ROOT})
]
