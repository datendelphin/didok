from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponse
from django.shortcuts import render
from models import *

def route_map_view(request):

    timestamp = OSMLastUpdate.objects.all()[0]
    try:
        timestamp = OSMLastUpdate.objects.all()[0].time
    except:
        return render(request, 'basemap.html', {'dataTime':None})

    dateTime = timestamp.strftime('%d.%m.%Y %H:%M')

    context = {'dataTime' : dateTime}

    return render(request, 'basemap.html', context)
