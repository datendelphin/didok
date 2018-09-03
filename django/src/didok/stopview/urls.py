from django.conf.urls import *
#from stopview.models import *
from didok.stopview.models import *
from didok.stopview import views

from django.views.generic.detail import DetailView

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = [
    url(r'^list$', views.listconnected ),
    url(r'^onlydidok$', views.listonlydidok),
    url(r'^onlyosm$', views.listonlyosm),
    url(r'^badname$', views.listbadname),
    url(r'^clustering', views.clustering),
    url(r'^v1', views.listv1),
    url(r'^statistiken.html', views.stats),
    url(r'^contributors.html', views.ranking),
    url(r'^edit/inexistentStop/(?P<in_id>\d+)$', views.inexistentStop),
    url(r'^edit/existentStop/(?P<in_id>\d+)$', views.existentStop),
    url(r'^info/d(?P<in_id>\d+).osm$', views.infoDidok),
    url(r'^info/d(?P<pk>\d+)$', DetailView.as_view(
           queryset = DIDOKStops.objects.all(),
           template_name = 'vector/didok_info.html')),
    url(r'^info/o(?P<pk>\d+)$', DetailView.as_view(
           queryset = OSMStops.objects.all(),
           template_name = 'vector/osm_info.html')),
    url(r'^search', views.search),
]
