import re
from django.db import connection
from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import status
from driver_position.models import DriverPosition
from driver_position.serializers import DriverPositionSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_driver_position(request, id_driver):
    try:
        query = """
        SELECT
            id_driver,
            ST_AsText(position) AS position
        FROM
            drivers_position
        WHERE
            id_driver = %s
        """
        with connection.cursor() as cursor:
            cursor.execute(query, [id_driver])
            row = cursor.fetchone()
        
    
        if not row:
            return Response({'message': 'El conductor no existe '}, status=status.HTTP_404_NOT_FOUND)
        
        position_text = row[1]
        match = re.match(r'POINT\(([-\d.]+) ([-\d.]+)\)', position_text)
        
        if match:
            lng = float(match.group(1))
            lat = float(match.group(2))
            driver_position = {
                "id_driver": row[0],
                "lat": lat,
                "lng": lng
            }
            return Response(driver_position, status=status.HTTP_200_OK)
            
        return Response({'message': 'Error al obtener la posición del conductor'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:

        return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_nearby_drivers(request, client_lat, client_lng):
    try:
        client_lat = float(client_lat)
        client_lng = float(client_lng)

        query = """
        SELECT
            id_driver,
            ST_AsText(position) AS position,
            ST_Distance_Sphere(position, ST_GeomFromText('POINT(%s %s)', 4326)) AS distance
        FROM
            drivers_position
        HAVING
            distance <= %s
        """
       
        with connection.cursor() as cursor:
            cursor.execute(query, [client_lng, client_lat, 5000])
            rows = cursor.fetchall()

        drivers = []
        for row in rows:
            position_text = row[1]
            match = re.match(r'POINT\(([-\d.]+) ([-\d.]+)\)', position_text)
            if match:
                lng = float(match.group(1))
                lat = float(match.group(2))
                drivers.append({
                    "id_driver": row[0],
                    "position": {'x': lng, 'y': lat},
                    "distance": row[2],
                })
       
        return Response(drivers, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create(request):
    serializer = DriverPositionSerializer(data=request.data)
    if serializer.is_valid():
        driver_position = serializer.save()
        return Response(True, status=status.HTTP_200_OK)
        
    error_messages = []
    for field, errors in serializer._errors.items():
        for error in errors:
            error_messages.append(f"{field}: {error} ")

    error_response = {
        "message": error_messages,
        "statusCode": status.HTTP_400_BAD_REQUEST
    }

    return Response(error_response, status=status.HTTP_400_BAD_REQUEST)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def  delete(request, id_driver):
    try:
        driver_position = DriverPosition.objects.filter(id_driver = id_driver).first()

        if not driver_position:
            return Response({'message': 'El conductor no existe'}, status=status.HTTP_404_NOT_FOUND)
        driver_position.delete()
        return Response({'message': 'El conductor se ha eliminado'}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)