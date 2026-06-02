from django.db import models


class TimeAndDistanceValues(models.Model):
    id = models.AutoField(primary_key=True)
    km_value = models.FloatField()
    min_value = models.FloatField()

    class Meta:
        db_table = 'time_and_distance_values'