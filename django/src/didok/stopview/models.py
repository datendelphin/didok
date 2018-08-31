from django.contrib.gis.db import models
from django.contrib.postgres.fields import HStoreField
from django.db.models import BigIntegerField
from django.db import connection

class DIDOKStops(models.Model):
    """Table with information about didok stops.
    """
    id = models.IntegerField(primary_key=True)
    dstnr = models.IntegerField()
    xkoord = models.TextField(null=True)
    ykoord = models.TextField(null=True)
    goabk = models.TextField(null=True)
    name = models.TextField(null=True)
    gemeinde_nr = models.TextField(null=True)
    gemeinde = models.TextField(null=True)
    verkehrsmittel = models.TextField(null=True)
    hoehe = models.TextField(null=True)
    import_geom = models.GeometryField(srid=4326)

    objects = models.GeoManager()

    def connected_with(self):
        cursor = connection.cursor()

        cursor.execute("SELECT id, osm_name FROM osm_stops WHERE uic_ref = %s" % (self.dstnr))

        return [c for c in cursor]

    def existent(self):
        return DIDOKAnnotation.objects.filter(dstnr = self.dstnr, text='inexistent').count() == 0

    class Meta:
        db_table = u'didok_stops'

class OSMUsers(models.Model):
    id = models.IntegerField(primary_key = True)
    name = models.TextField()

    class Meta:
        db_table = u'osm_usernames'

class OSMStops(models.Model):
    """Table that holds the OSM PT nodes.
    """
    id = BigIntegerField(primary_key=True)
    parent = BigIntegerField()
    osm_name = models.TextField()
    osm_type = models.TextField()
    tags = HStoreField()
    osm_geom = models.GeometryField(srid=4326)
    uic_ref = models.IntegerField()
    user = models.ForeignKey(OSMUsers)
    version = models.IntegerField()

    objects = models.GeoManager()

    def connected_with(self):
        if self.uic_ref is None:
            return []
        else:
            cursor = connection.cursor()

            cursor.execute("SELECT dstnr, name FROM didok_stops WHERE dstnr = %s" % (self.uic_ref))

            return [c for c in cursor]

    class Meta:
        db_table = u'osm_stops'

class StopMatch(models.Model):
    osm = models.ForeignKey(OSMStops)
    didok = models.ForeignKey(DIDOKStops)
    dist = models.FloatField(primary_key = True)
    objects = models.GeoManager()

    class Meta:
        db_table = u'match'


class DIDOKAnnotation(models.Model):
    dstnr = models.IntegerField()
    text = models.TextField()

    class Meta:
        db_table = u'didok_annotation'
