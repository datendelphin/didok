from django.conf.urls import *
#from stopview.models import *
from didok.stopview.models import *

from django.views.generic.detail import DetailView

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
    (r'^info/d(?P<pk>\d+)$', DetailView.as_view(
           queryset = DIDOKStops.objects.all(),
           template_name = 'vector/didok_info.html')),
    (r'^info/o(?P<pk>\d+)$', DetailView.as_view(
           queryset = OSMStops.objects.all(),
           template_name = 'vector/osm_info.html')),
    (r'^info/d(?P<pk>\d+).osm$', DetailView.as_view(
           queryset = DIDOKStops.objects.all(),
           template_name = 'vector/didok_osm.osm')),
)
