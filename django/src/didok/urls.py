from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('didok.mapview.views',
    (r'^$', 'route_map_view', {}, 'simplemap'),
)

urlpatterns += patterns('',
    (r'^didokstops/', include('didok.stopview.urls')),
)

# for development
if settings.DEBUG:
    urlpatterns += patterns('',
        (r'^media/static/(?P<path>.*)$', 'django.views.static.serve',
        {'document_root': settings.MEDIA_ROOT})
)
