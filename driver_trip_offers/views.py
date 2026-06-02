from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db import connection
from driver_trip_offers.serializers import DriverTripOfferSerializer
import json
from django.conf import settings
# Create your views here.



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def find_by_client_request(request, id_client_request):
    try:
        query = """
           SELECT
              DTO.id,
              DTO.id_client_request,
              DTO.id_driver,
              DTO.fare_offered,
              DTO.time,
              DTO.distance,
              DTO.created_at,
              DTO.updated_at,
              JSON_OBJECT(
                   "name", U.name,
                   "lastname", U.lastname,
                   "phone", U.phone,
                   "image", U.image
              ) AS driver,
              JSON_OBJECT(
                   "brand", DBI.brand,
                   "color", DBI.color,
                   "plate", DBI.plate
              ) AS bike
            FROM 
                driver_trip_offers AS  DTO
            INNER JOIN
                users AS U
            ON
                U.id = DTO.id_driver
            LEFT JOIN 
                driver_bike_info AS DBI
            ON 
                DTO.id_driver = DBI.id_driver
            WHERE 
                DTO.id_client_request = %s             
         """
        
        with connection.cursor() as cursor:
            cursor.execute(query, [int(id_client_request)])
            columns = [col[0] for col in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]

        if not results:
            return Response([], status=status.HTTP_200_OK)
        

        results_json = []
        for result in results:
         result['driver'] = json.loads(result['driver'])
         result['bike'] = json.loads(result['bike'])
        
         if result['driver'].get('image'):
            result['driver']['image'] = f"http://{settings.GLOBAL_IP}:{settings.GLOBAL_HOST}{result['driver']['image']}"

            results_json.append(result)
            return Response(results_json, status=status.HTTP_200_OK)

    except Exception as e:
       return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
   

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create(request):
    serializer = DriverTripOfferSerializer(data = request.data)
    if serializer.is_valid():
        driver_trip_offer = serializer.save()
        return Response(serializer.data, status = status.HTTP_201_CREATED)
    error_messages = []
    for field, errors in serializer._errors.items():
        for error in errors:
            error_messages.append(f"{field}: {error} ")

    error_response = {
        "message": error_messages,
        "statusCode": status.HTTP_400_BAD_REQUEST
    }

    return Response(error_response, status=status.HTTP_400_BAD_REQUEST)