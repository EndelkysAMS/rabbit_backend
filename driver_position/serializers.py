from django.db import connection
from rest_framework import serializers

from driver_position.models import DriverPosition
from users.models import User

class DriverPositionSerializer(serializers.ModelSerializer):
    id_driver = serializers.IntegerField()
    lat = serializers.FloatField(write_only=True)
    lng = serializers.FloatField(write_only=True)

    class Meta:
        model = DriverPosition
        fields = ['id_driver','lat','lng']

    def create(self, validated_data):
        id_driver = validated_data.get('id_driver')  
        lat = validated_data.get('lat') 
        lng = validated_data.get('lng')   

        try:
            user_instance = User.objects.get(id=id_driver)
        except User.DoesNotExist:
            raise serializers.ValidationError({'message':'El usuario no existe'})
        
        query = """
            REPLACE INTO drivers_position (id_driver, position)
            VALUES (%s, ST_GeomFromText('POINT(%s %s)', 4326))
        """

        with connection.cursor() as cursor:
            cursor.execute(query, [id_driver, lng, lat])
            
        return {'id_driver': id_driver, 'lat': lat, 'lng': lng}    