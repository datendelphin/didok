from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponse
from django.shortcuts import render
import re

def route_map_view(request):

    try:
        stateF = open('state.txt', 'r')
    except:
        return render(request, 'basemap.html', {'dataTime':None})

    for line in stateF.readlines():
        lastline = line

    dateRe = re.compile('timestamp=(\d{4})-(\d{2})-(\d{2})T(\d{2})\\\\?:(\d{2})\\\\?:\d{2}Z')
    dateTime = re.sub(dateRe, '\\3.\\2.\\1 \\4:\\5', lastline)

    context = {'dataTime' : dateTime}

    return render(request, 'basemap.html', context)
