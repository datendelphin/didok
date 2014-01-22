from django.conf.urls.defaults import *
#from stopview.models import *
from didok.stopview.models import *

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns('didok.stopview.views',
    (r'^list$', 'listconnected' ),
    (r'^onlydidok$', 'listonlydidok'),
    (r'^onlyosm$', 'listonlyosm'),
    (r'^badname$', 'listbadname'),
    (r'^clustering', 'clustering'),
    (r'^v1', 'listv1'),
    (r'^statistiken.html', 'stats'),
    (r'^contributors.html', 'ranking'),
    (r'^edit/inexistentStop/(?P<in_id>\d+)$', 'inexistentStop'),
    (r'^edit/existentStop/(?P<in_id>\d+)$', 'existentStop')
)

urlpatterns += patterns('',
    (r'^info/d(?P<object_id>\d+)$', 'django.views.generic.list_detail.object_detail',
         {'queryset' : DIDOKStops.objects.all(),
          'template_name' : 'vector/didok_info.html'}),
    (r'^info/o(?P<object_id>\d+)$', 'django.views.generic.list_detail.object_detail',
         {'queryset' : OSMStops.objects.all(),
          'template_name' : 'vector/osm_info.html'}),
)
