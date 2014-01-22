from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponse
from django.views.generic.simple import direct_to_template
import re

def route_map_view(request):

    stateF = open('/home/spreng/updatescript/replication/state.txt', 'r')
    for line in stateF.readlines():
        lastline = line

    dateRe = re.compile('timestamp=(\d{4})-(\d{2})-(\d{2})T(\d{2})\\\\:(\d{2})\\\\:\d{2}Z')
    dateTime = re.sub(dateRe, '\\3.\\2.\\1 \\4:\\5', lastline)

    context = {'dataTime' : dateTime}

    return direct_to_template(request,
                              template='basemap.html', 
                              extra_context=context)
