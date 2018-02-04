# vim: set fileencoding=utf-8
from django.conf import settings
from django.shortcuts import render
import django.contrib.gis.geos as geos
from django.db import connection, transaction
from django.contrib.gis.db.models import Extent
from django.db.models import Count,Q
from django.http import HttpResponse

import time
import re
from models import *

def getBBox(request):
    errormsg = "No valid bbox specified."
    
    coords = request.GET.get('bbox', '').split(',')
    if len(coords) == 4:
        try:
            coords = tuple([float(x) for x in coords])
        except ValueError:
            errormsg = "Invalid coordinates in bbox."
        
        return geos.GEOSGeometry('SRID=4326;MULTIPOINT(%f %f, %f %f)' % coords)

def didok_state(didok, default):
    if DIDOKAnnotation.objects.filter(dstnr = didok.dstnr).count() > 0:
        return 'VI'
    else:
        return default

def listconnected(request):
    bbox=getBBox(request)
    clustering='false'
    objs = []
    lines = []
    
    qs = StopMatch.objects
    qs = qs.filter(Q(osm_id__osm_geom__bboverlaps=bbox) | Q(didok_id__import_geom__bboverlaps=bbox))
    qs = qs.select_related()
    
    if (qs[:500]).count() > 499:
        qs = qs.extra(order_by = ['-dist'])[:100]
        clustering = 'true'
    for pt in qs:
        objs.append({'geom' : pt.osm.osm_geom,
                        'prop' : [
                        ('id', 'o%d' % pt.osm_id),
                        ('name', pt.osm.osm_name),
                        ('state', 'OY'),
                        ]})
        objs.append({'geom' : pt.didok.import_geom,
                        'prop' : [
                        ('id' , 'd' + str(pt.didok_id)),
                        ('name', pt.didok.name.strip().replace('\\','')),
                        ('state', didok_state(pt.didok, 'VY')),
                        ]})
        lines.append({'geom1' : pt.didok.import_geom,
                        'geom2' : pt.osm.osm_geom,
                        'prop' : [
                        ('id', 'c%d-%d' % (pt.osm_id, pt.didok_id)),
                        ('name', '%.2fm' % pt.dist),
                        ('state', ''),
                        ]})
    
    return render(request, "vector/points.json",
                                {'objs' : objs,
                                    'lines' : lines,
                                    'clustering' : clustering},
                                content_type='text/plain')

def clustering(request):
    objs = []
    w_didok = request.GET.get('didok', 'false')
    w_osm = request.GET.get('osm', 'false')
    w_badname = request.GET.get('badname', 'false')
    
    errormsg = "No valid bbox specified."
    
    coords = request.GET.get('bbox', '').split(',')
    if len(coords) == 4:
        try:
            coords = tuple([float(x) for x in coords])
        except ValueError:
            errormsg = "Invalid coordinates in bbox."
    
    bbox=geos.GEOSGeometry('SRID=4326;MULTIPOINT(%f %f, %f %f)' % coords)
    group = (coords[2] - coords[0])/10.
    
    groups = {}
    
    # DIDOK
    if w_didok != 'false':
        qs = DIDOKStops.objects.filter(import_geom__bboverlaps=bbox)
        qs = qs.extra(select={'xrnd' : 'round(st_x(import_geom)/%g)' % group,
                            'yrnd' : 'round(st_y(import_geom)/%g)' % group})
        qs = qs.values('xrnd','yrnd').annotate(Extent('import_geom'), Count('import_geom'))
        for pt in qs:
            #print pt
            extent = pt['import_geom__extent']
            x = (extent[0] + extent[2])/2
            y = (extent[1] + extent[3])/2
            xrnd = pt['xrnd']
            yrnd = pt['yrnd']
            if xrnd not in groups.keys():
                groups[xrnd] = {}
            if yrnd not in groups[xrnd].keys():
                groups[xrnd][yrnd] = []
            groups[xrnd][yrnd] += [(x, y, ('nr_didok', pt['import_geom__count']))]
    
    #OSM
    if w_osm != 'false':
        qs = OSMStops.objects.filter(osm_geom__bboverlaps=bbox)
        qs = qs.extra(select={'xrnd' : 'round(st_x(osm_geom)/%g)' % group,
                            'yrnd' : 'round(st_y(osm_geom)/%g)' % group})
        qs = qs.values('xrnd','yrnd').annotate(Extent('osm_geom'), Count('osm_geom'))
        for pt in qs:
            #print pt
            extent = pt['osm_geom__extent']
            x = (extent[0] + extent[2])/2
            y = (extent[1] + extent[3])/2
            xrnd = pt['xrnd']
            yrnd = pt['yrnd']
            if xrnd not in groups.keys():
                groups[xrnd] = {}
            if yrnd not in groups[xrnd].keys():
                groups[xrnd][yrnd] = []
            groups[xrnd][yrnd] += [(x, y, ('nr_osm', pt['osm_geom__count']))]
    
    #badname
    if w_badname != 'false':
        qs = StopMatch.objects.filter(Q(osm_id__osm_geom__bboverlaps=bbox) | Q(didok_id__import_geom__bboverlaps=bbox))
        qs.extra(where=["tags->'uic_name' != name"])
        qs = qs.extra(where  = ["tags->'uic_name' != name"],
                      select = {'xrnd' : 'round(st_x(osm_geom)/%g)' % group,
                                'yrnd' : 'round(st_y(osm_geom)/%g)' % group})
        qs = qs.values('xrnd','yrnd').annotate(Extent('osm__osm_geom'), Count('osm__osm_geom'))
        for pt in qs:
            #print pt
            extent = pt['osm__osm_geom__extent']
            x = (extent[0] + extent[2])/2
            y = (extent[1] + extent[3])/2
            xrnd = pt['xrnd']
            yrnd = pt['yrnd']
            if xrnd not in groups.keys():
                groups[xrnd] = {}
            if yrnd not in groups[xrnd].keys():
                groups[xrnd][yrnd] = []
            groups[xrnd][yrnd] += [(x, y, ('nr_badname', pt['osm__osm_geom__count']))]
    
    for xrnd in groups.keys():
        for yrnd in groups[xrnd].keys():
            x = 0
            y = 0
            props = [('xrnd', xrnd), ('yrnd', yrnd)]
            for e in groups[xrnd][yrnd]:
                x += e[0]
                y += e[1]
                props += [e[2]]
            x /= len(groups[xrnd][yrnd])
            y /= len(groups[xrnd][yrnd])
            objs.append({'geom' : geos.Point(x, y),
                        'prop' : props})
    
    
    return render(request, "vector/points.json",
                                {'objs' : objs,
                                 'lines' : [],
                                 'clustering' : 'false'},
                                 content_type='text/plain')


def listonlydidok(request):
    
    bbox=getBBox(request)
    clustering='false'
    objs = []
    
    qs = DIDOKStops.objects.filter(import_geom__bboverlaps=bbox)
    qs = qs.exclude(verkehrsmittel__startswith="(")
    qs = qs.extra(where=["dstnr NOT IN (SELECT uic_ref FROM osm_stops WHERE uic_ref IS NOT NULL)"])
    
    if (qs[:500]).count() > 499:
        clustering='true'
    else:
        objs = []
        
        for pt in qs:
            objs.append({'geom' : pt.import_geom,
                        'prop' : [
                        ('id' , 'd' + str(pt.id)),
                        ('name', pt.name.strip().replace('\\','')),
                        ('state', didok_state(pt,'VN')),
                        ]})
    return render(request, "vector/points.json",
                                    {'objs' : objs,
                                        'lines' : [],
                                        'clustering' : clustering},
                                    content_type='text/plain')

def listonlyosm(request):
    bbox=getBBox(request)
    clustering='false'
    objs = []
    
    qs = OSMStops.objects.filter(osm_geom__bboverlaps=bbox)
    qs = qs.extra(where=["(uic_ref NOT IN (SELECT dstnr FROM didok_stops) OR uic_ref IS NULL)"])
    
    if (qs[:500]).count() > 499:
        clustering='true'
    else:
        for pt in qs:
            objs.append({'geom' : pt.osm_geom,
                        'prop' : [
                        ('id' , 'o' + str(pt.id)),
                        ('name', pt.osm_name),
                        ('state', 'ON'),
                        ]})
    return render(request, "vector/points.json",
                                    {'objs' : objs,
                                        'lines' : [],
                                        'clustering' : clustering},
                                    content_type='text/plain')

def listbadname(request):
    #SELECT * FROM didok_stops, osm_stops WHERE uic_ref = dstnr AND tags->'uic_name' != name
    bbox=getBBox(request)
    clustering='false'
    objs = []
    lines = []
    
    qs = StopMatch.objects.filter(Q(osm_id__osm_geom__bboverlaps=bbox) | Q(didok_id__import_geom__bboverlaps=bbox))
    qs = qs.select_related().extra(where=["tags->'uic_name' != didok_stops.name"])
    
    if (qs[:500]).count() > 499:
        clustering='true'
    else:
        for pt in qs:
            if 'uic_name' in pt.osm.tags.keys():
                note = 'osm: ' + pt.osm.tags['uic_name']
            else:
                note = 'osm: (none)'
            note += '<br/> DIDOK: ' + pt.didok.name.strip().replace('\\','')
            objs.append({'geom' : pt.didok.import_geom,
                            'prop' : [
                            ('id' , 'd' + str(pt.didok_id)),
                            ('name', note),
                            ('state', didok_state(pt.didok,'VY')),
                            ]})
            objs.append({'geom' : pt.osm.osm_geom,
                            'prop' : [
                            ('id', 'o%d' % pt.osm_id),
                            ('name', note),
                            ('state', 'OB'),
                            ]})
            lines.append({'geom1' : pt.didok.import_geom,
                            'geom2' : pt.osm.osm_geom,
                            'prop' : [
                            ('id', 'c%d-%d' % (pt.osm_id, pt.didok_id)),
                            ('name', '%.2fm' % pt.dist),
                            ('state', ''),
                            ]})
    return render(request, "vector/points.json",
                                    {'objs' : objs,
                                     'lines' : lines,
                                     'clustering' : clustering},
                                    content_type='text/plain')

filter_unchecked_users = Q(user_id=368211) | Q(user_id=2680)

def listv1(request):
    bbox=getBBox(request)
    clustering='false'
    objs = []
    nMax = 500
    
    qs = OSMStops.objects.filter(osm_geom__bboverlaps=bbox)
    qs = qs.filter(filter_unchecked_users, version=1)[:nMax]

    nListed = qs.count()
    
    if True:
        for pt in qs:
            objs.append({'geom' : pt.osm_geom,
                        'prop' : [
                        ('id' , 'o' + str(pt.id)),
                        ('name', pt.osm_name),
                        ('state', 'O1'),
                        ]})
        qs = OSMStops.objects.filter(osm_geom__bboverlaps=bbox)
        qs = qs.filter(filter_unchecked_users, version__gt=1)[:(nMax - nListed)]
        nListed = nListed + qs.count()
        for pt in qs:
            objs.append({'geom' : pt.osm_geom,
                        'prop' : [
                        ('id' , 'o' + str(pt.id)),
                        ('name', pt.osm_name),
                        ('state', 'OX'),
                        ]})
        qs = OSMStops.objects.filter(osm_geom__bboverlaps=bbox)
        qs = qs.exclude(filter_unchecked_users)[:(nMax - nListed)]
        for pt in qs:
            objs.append({'geom' : pt.osm_geom,
                        'prop' : [
                        ('id' , 'o' + str(pt.id)),
                        ('name', pt.osm_name),
                        ('state', 'OC'),
                        ]})
        
    return render(request, "vector/points.json",
                                    {'objs' : objs,
                                        'lines' : [],
                                        'clustering' : clustering},
                                    content_type='text/plain')

def stats(request):
    infos = []


    infos.append(('OSM-stops with swiss UIC (85...)',
        OSMStops.objects.extra(where=["uic_ref BETWEEN 8500000 AND 8599999"]).count()))
    infos.append(('OSM-stops matched with DIDOK',
            OSMStops.objects.extra(where=["""id IN
               (SELECT DISTINCT osm_id FROM match)"""]).count()))  
    infos.append(('DIDOK-stops', DIDOKStops.objects.count()))
    infos.append(('DIDOK-stops with at least one counterpart in OSM',
            DIDOKStops.objects.extra(where=["""id IN
               (SELECT DISTINCT didok_id FROM match)"""]).count()))
    infos.append(('user=DidokImportCH, version=1',
        OSMStops.objects.extra(where=["uic_ref BETWEEN 8500000 AND 8599999"]).filter(filter_unchecked_users, version=1).count()))
    infos.append(('user=DidokImportCH, version>1',
        OSMStops.objects.extra(where=["uic_ref BETWEEN 8500000 AND 8599999"]).filter(filter_unchecked_users, version__gt=1).count()))
    infos.append(('user!=DidokImportCH',
        OSMStops.objects.extra(where=["uic_ref BETWEEN 8500000 AND 8599999"]).count()
        - OSMStops.objects.extra(where=["uic_ref BETWEEN 8500000 AND 8599999"]).filter(filter_unchecked_users).count()))

    return render(request, "vector/statistics.html", 
                               {'infos' : infos})

def ranking(request):
    table = []

    qs = OSMUsers.objects.annotate(num_stops=Count('osmstops'))
    qs = qs.extra(where = ['"osm_stops"."uic_ref" BETWEEN 8500000 AND 8599999']).filter(num_stops__gt=0).order_by('-num_stops')

    for line in qs:
        table.append({'username' : line.name, 'count' : line.num_stops})

    return render(request, "vector/contributors.html", 
                               {'table' : table})

def inexistentStop(request, in_id):
    dstnr = DIDOKStops.objects.get(pk=in_id).dstnr
    if DIDOKAnnotation.objects.filter(dstnr=dstnr, text="inexistent").count() > 0:
        return render(request, 'ok', {'text' : 'failed'})
    d = DIDOKAnnotation(dstnr=dstnr, text="inexistent")
    f = open('/var/log/didok/inexistent_stops.log', 'a')
    f.write('%d;inexistent;%s;%f\n' % (dstnr, request.META['REMOTE_ADDR'], time.time()))
    f.close()
    d.save()
    return render(request, 'ok', {'text' : 'OK'})

def existentStop(request, in_id):
    dstnr = DIDOKStops.objects.get(pk=in_id).dstnr
    if DIDOKAnnotation.objects.filter(dstnr=dstnr, text="inexistent").count() < 1:
        return render(request, 'ok', {'text' : 'failed'})
    f = open('/var/log/didok/inexistent_stops.log', 'a')
    f.write('%d;existent;%s;%f\n' % (dstnr, request.META['REMOTE_ADDR'], time.time()))
    f.close()
    qs = DIDOKAnnotation.objects.filter(dstnr=dstnr, text="inexistent")
    for d in qs:
        d.delete()
    return render(request, 'ok', {'text' : 'OK'})


def errorHttpResponse(msg):
    return HttpResponse(content='<xml><error>%s</error></xml>' % msg,
                        content_type='text/xml; charset=UTF-8')



def infoDidok(request, in_id):
    dstop = DIDOKStops.objects.get(pk=in_id)
    opshort = re.search('^[^-]+', dstop.goabk).group(0)

    return render(request, 'vector/didok_osm.osm',
            {'object' : dstop, 'opshort': opshort})
