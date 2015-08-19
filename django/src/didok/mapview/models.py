from django.db import models

# Create your models here.
class OSMLastUpdate(models.Model):
    time = models.DateTimeField(primary_key=True)

    class Meta:
        db_table = u'osm_stops_update_time'
