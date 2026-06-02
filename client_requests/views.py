import requests
import json
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from client_requests.serializers import ClientRequestsSerializer
from time_and_distance_values.models import TimeAndDistanceValues
from django.db import connection
from datetime import datetime
from django.conf import settings
from firebase_admin import messaging
from firebase_notification.views import send_push_notification_to_multiple_device

GOOGLE_API_KEY = 'AIzaSyCsYS3XlL5usbYBKduvSEpoMWUDsjx56ds'



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create(request):
    serializer = ClientRequestsSerializer(data=request.data)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if not serializer.is_valid():
        error_messages = []
        for field, errors in serializer.errors.items():  
            for error in errors:
                error_messages.append(f"{field}: {error} ")

        error_response = {
            "message": error_messages,
            "statusCode": status.HTTP_400_BAD_REQUEST
        }
        return Response(error_response, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    id_client = data['id_client']
    fare_offered = data['fare_offered']
    pickup_description = data['pickup_description']
    destination_description = data['destination_description']
    pickup_lat = data['pickup_lat']
    pickup_lng = data['pickup_lng']
    destination_lat = data['destination_lat']
    destination_lng = data['destination_lng']

    sql = """
    INSERT INTO client_requests (
      id_client,
      fare_offered,
      pickup_description,
      destination_description,
      pickup_position,
      destination_position,
      status,
      created_at,
      updated_at
    )
    VALUES(
        %s,
        %s,
        %s,
        %s,
        ST_GeomFromText('POINT(%s %s)',4326),
        ST_GeomFromText('POINT(%s %s)',4326),
        'CREATED',
        %s,
        %s
    )
    """



    nearby_drivers_sql = """
        SELECT 
           U.id,
           U.notification_token,
           DP.position,
           ST_Distance_Sphere(
	       DP.position,
          ST_GeomFromText('POINT(%s %s)', 4326)
          ) AS distance
       FROM 
           users AS U
     LEFT JOIN
	       drivers_position AS DP
       ON 
           U.id = DP.id_driver
    HAVING
            distance < 5000

"""
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                sql,
                [
                    id_client,
                    fare_offered,
                    pickup_description,
                    destination_description,
                    pickup_lng,
                    pickup_lat,
                    destination_lng,
                    destination_lat,
                    now,
                    now
                ]
            )
            cursor.execute("SELECT LAST_INSERT_ID()")
            id_client_request = cursor.fetchone()[0]

            cursor.execute(nearby_drivers_sql, [pickup_lng, pickup_lat])
            nearby_drivers = cursor.fetchall()

        notification_tokens = list({
            driver[1]  for driver in nearby_drivers
            if driver[1] is not None and driver[1] != ''
        })
        send_push_notification_to_multiple_device(
            notification_tokens,
            title="Solicitud de viaje",
            body=pickup_description,
            data={
                'id_client_request': str(id_client_request),
                'type': 'CLIENT_REQUEST'
            }
        )
        
        return Response({id_client_request}, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'message': f'Error al crear la solicitud de viaje: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_driver_assigned(request):
    id = request.data.get('id')
    id_driver_assigned = request.data.get('id_driver_assigned')
    fare_assigned = request.data.get('fare_assigned')

    sql = """
        UPDATE client_requests
        SET 
           id_driver_assigned = %s,
           status = 'ACCEPTED',
           updated_at = NOW(),
           fare_assigned = %s
        WHERE id = %s   
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, [id_driver_assigned, fare_assigned, id])
            return Response({'success': True}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'message': f'Error al asignar el conductor : {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_nearby_trip_request(request, driver_lat, driver_lng):
    try:
        query = """
            SELECT
                CR.id,
                CR.id_client,
                CR.fare_offered,
                CR.pickup_description,
                CR.destination_description,
                CR.status,
                CR.updated_at,
                JSON_OBJECT(
                    "x", ST_X(pickup_position),
                    "y", ST_Y(pickup_position)
                ) AS pickup_position,
                JSON_OBJECT(
                    "x", ST_X(destination_position),
                    "y", ST_Y(destination_position)
                ) AS destination_position,
                ST_Distance_Sphere(CR.pickup_position, ST_GeomFromText('POINT(%s %s)', 4326)) AS distance,
                timestampdiff(MINUTE, CR.updated_at, NOW()) AS time_difference,
                JSON_OBJECT(
                    "name", U.name,
                    "lastname", U.lastname,
                    "phone", U.phone,
                    "image", U.image
                ) AS client
            FROM
                client_requests AS CR
            INNER JOIN
                users AS U
            ON
                U.id = CR.id_client
            WHERE
                timestampdiff(MINUTE, CR.updated_at, NOW()) < 1000 AND status = "CREATED"
            HAVING
                distance < 5000;
        """

        with connection.cursor() as cursor:
            cursor.execute(query, [float(driver_lng), float(driver_lat)])
            columns = [col[0] for col in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]

        if not results:
            return Response([], status=status.HTTP_200_OK)

        results_json = []
        pickup_positions = []
        for result in results:
            result['pickup_position'] = json.loads(result['pickup_position'])
            result['destination_position'] = json.loads(result['destination_position'])
            if result.get('client'):
                result['client'] = json.loads(result['client'])

            if result['client'].get('image'):
                result['client']['image'] = f"http://{settings.GLOBAL_IP}:{settings.GLOBAL_HOST}{result['client']['image']}"

            results_json.append(result)
            pickup_positions.append(
                f"{result['pickup_position']['y']},{result['pickup_position']['x']}"
            )

        origins = f"{driver_lat},{driver_lng}"
        destinations = "|".join(pickup_positions)
        url = 'https://maps.googleapis.com/maps/api/distancematrix/json'
        params = {
            'destinations': destinations,
            'origins': origins,
            'units': 'metric',
            'key': GOOGLE_API_KEY,
            'mode': 'driving'
        }
        response = requests.get(url, params=params)

        if response.status_code != 200:
            return Response({'message': f"Error en el API de Google Distance Matrix: {response.status_code}"}, status=response.status_code)

        google_data = response.json()
        if google_data.get('status') != 'OK':
            return Response({'message': f"Error en la respuesta del API de Google Distance Matrix: {google_data.get('status')}"}, status=status.HTTP_400_BAD_REQUEST)

        elements = google_data['rows'][0]['elements']
        for index, element in enumerate(elements):
            results_json[index]['google_distance_matrix'] = element

        return Response(results_json, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_by_client_request(request, id_client_request):
    try:
        query = """
            SELECT
                CR.id,
                CR.id_client,
                CR.fare_offered,
                CR.pickup_description,
                CR.destination_description,
                CR.status,
                CR.updated_at,
                CR.id_driver_assigned,
                CR.fare_assigned,
                ST_X(pickup_position) AS pickup_lng,
                ST_Y(pickup_position) AS pickup_lat,
                ST_X(destination_position) AS destination_lng,
                ST_Y(destination_position) AS destination_lat,
                JSON_OBJECT(
                    "x", ST_X(pickup_position),
                    "y", ST_Y(pickup_position)
                ) AS pickup_position,
                JSON_OBJECT(
                    "x", ST_X(destination_position),
                    "y", ST_Y(destination_position)
                ) AS destination_position,
                JSON_OBJECT(
                    "name", U.name,
                    "lastname", U.lastname,
                    "phone", U.phone,
                    "image", U.image
                ) AS client,
                JSON_OBJECT(
                    "name", D.name,
                    "lastname", D.lastname,
                    "phone", D.phone,
                    "image", D.image
                ) AS driver,
                 JSON_OBJECT(
                    "brand", DBI.brand,
                    "color", DBI.color,
                    "plate", DBI.plate
                ) AS bike
            FROM
                client_requests AS CR
            INNER JOIN
                users AS U
            ON
                U.id = CR.id_client
            LEFT JOIN
                 users AS D
            ON 
               D.id = CR.id_driver_assigned
            LEFT JOIN 
                  driver_bike_info AS DBI
            ON 
                 DBI.id_driver = CR.id_driver_assigned
            WHERE
              CR.id = %s  AND status = "ACCEPTED"
        """

        with connection.cursor() as cursor:
            cursor.execute(query, [int(id_client_request)])
            columns = [col[0] for col in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]

        if not results:
            return Response([], status=status.HTTP_200_OK)

        results_json = []
        for result in results:
            if result.get('client'):
                result['client'] = json.loads(result['client'])
                result['driver'] = json.loads(result['driver']) 
                result['pickup_position'] = json.loads(result['pickup_position'])
                result['destination_position'] = json.loads(result['destination_position'])
                result['bike'] = json.loads(result['bike'])

            if result['client'].get('image'):
                result['client']['image'] = f"http://{settings.GLOBAL_IP}:{settings.GLOBAL_HOST}{result['client']['image']}"
            
            if result['driver'].get('image'):
                result['driver']['image'] = f"http://{settings.GLOBAL_IP}:{settings.GLOBAL_HOST}{result['driver']['image']}"

            results_json.append(result)

        return Response(results_json[0], status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_by_client_assigned(request, id_client):
    try:
        query = """
            SELECT
                CR.id,
                CR.id_client,
                CR.fare_offered,
                CR.pickup_description,
                CR.destination_description,
                CR.status,
                CR.updated_at,
                CR.created_at,
                CR.id_driver_assigned,
                CR.fare_assigned,
                CR.client_rating,
                CR.driver_rating,
                ST_X(pickup_position) AS pickup_lng,
                ST_Y(pickup_position) AS pickup_lat,
                ST_X(destination_position) AS destination_lng,
                ST_Y(destination_position) AS destination_lat,
                JSON_OBJECT(
                    "x", ST_X(pickup_position),
                    "y", ST_Y(pickup_position)
                ) AS pickup_position,
                JSON_OBJECT(
                    "x", ST_X(destination_position),
                    "y", ST_Y(destination_position)
                ) AS destination_position,
                JSON_OBJECT(
                    "name", U.name,
                    "lastname", U.lastname,
                    "phone", U.phone,
                    "image", U.image
                ) AS client,
                JSON_OBJECT(
                    "name", D.name,
                    "lastname", D.lastname,
                    "phone", D.phone,
                    "image", D.image
                ) AS driver,
                 JSON_OBJECT(
                    "brand", DBI.brand,
                    "color", DBI.color,
                    "plate", DBI.plate
                ) AS bike
            FROM
                client_requests AS CR
            INNER JOIN
                users AS U
            ON
                U.id = CR.id_client
            LEFT JOIN
                 users AS D
            ON 
               D.id = CR.id_driver_assigned
            LEFT JOIN 
                  driver_bike_info AS DBI
            ON 
                 DBI.id_driver = CR.id_driver_assigned
            WHERE
              CR.id_client = %s  AND status = "FINISHED"
        """

        with connection.cursor() as cursor:
            cursor.execute(query, [int(id_client)])
            columns = [col[0] for col in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]

        if not results:
            return Response([], status=status.HTTP_200_OK)

        results_json = []
        for result in results:
            if result.get('client'):
                result['client'] = json.loads(result['client'])
                result['driver'] = json.loads(result['driver']) 
                result['pickup_position'] = json.loads(result['pickup_position'])
                result['destination_position'] = json.loads(result['destination_position'])
                result['bike'] = json.loads(result['bike'])

            if result['client'].get('image'):
                result['client']['image'] = f"http://{settings.GLOBAL_IP}:{settings.GLOBAL_HOST}{result['client']['image']}"
            
            if result['driver'].get('image'):
                result['driver']['image'] = f"http://{settings.GLOBAL_IP}:{settings.GLOBAL_HOST}{result['driver']['image']}"

            results_json.append(result)

        return Response(results_json, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_by_driver_assigned(request, id_driver):
    try:
        query = """
            SELECT
                CR.id,
                CR.id_client,
                CR.fare_offered,
                CR.pickup_description,
                CR.destination_description,
                CR.status,
                CR.updated_at,
                CR.created_at,
                CR.id_driver_assigned,
                CR.fare_assigned,
                CR.client_rating,
                CR.driver_rating,
                ST_X(pickup_position) AS pickup_lng,
                ST_Y(pickup_position) AS pickup_lat,
                ST_X(destination_position) AS destination_lng,
                ST_Y(destination_position) AS destination_lat,
                JSON_OBJECT(
                    "x", ST_X(pickup_position),
                    "y", ST_Y(pickup_position)
                ) AS pickup_position,
                JSON_OBJECT(
                    "x", ST_X(destination_position),
                    "y", ST_Y(destination_position)
                ) AS destination_position,
                JSON_OBJECT(
                    "name", U.name,
                    "lastname", U.lastname,
                    "phone", U.phone,
                    "image", U.image
                ) AS client,
                JSON_OBJECT(
                    "name", D.name,
                    "lastname", D.lastname,
                    "phone", D.phone,
                    "image", D.image
                ) AS driver,
                 JSON_OBJECT(
                    "brand", DBI.brand,
                    "color", DBI.color,
                    "plate", DBI.plate
                ) AS bike
            FROM
                client_requests AS CR
            INNER JOIN
                users AS U
            ON
                U.id = CR.id_client
            LEFT JOIN
                 users AS D
            ON 
               D.id = CR.id_driver_assigned
            LEFT JOIN 
                  driver_bike_info AS DBI
            ON 
                 DBI.id_driver = CR.id_driver_assigned
            WHERE
              CR.id_driver_assigned = %s  AND status = "FINISHED"
        """

        with connection.cursor() as cursor:
            cursor.execute(query, [int(id_driver)])
            columns = [col[0] for col in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]

        if not results:
            return Response([], status=status.HTTP_200_OK)

        results_json = []
        for result in results:
            if result.get('client'):
                result['client'] = json.loads(result['client'])
                result['driver'] = json.loads(result['driver']) 
                result['pickup_position'] = json.loads(result['pickup_position'])
                result['destination_position'] = json.loads(result['destination_position'])
                result['bike'] = json.loads(result['bike'])

            if result['client'].get('image'):
                result['client']['image'] = f"http://{settings.GLOBAL_IP}:{settings.GLOBAL_HOST}{result['client']['image']}"
            
            if result['driver'].get('image'):
                result['driver']['image'] = f"http://{settings.GLOBAL_IP}:{settings.GLOBAL_HOST}{result['driver']['image']}"

            results_json.append(result)

        return Response(results_json, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_time_and_distance_client_request(request, origin_lat, origin_lng, destination_lat, destination_lng):
    try:
        time_and_distance_values = TimeAndDistanceValues.objects.get(id=1)
        km_value = time_and_distance_values.km_value
        min_value = time_and_distance_values.min_value

        origins = f"{origin_lat},{origin_lng}"
        destinations = f"{destination_lat},{destination_lng}"
        url = 'https://maps.googleapis.com/maps/api/distancematrix/json'
        params = {
            'destinations': destinations,
            'origins': origins,
            'units': 'metric',
            'key': GOOGLE_API_KEY
        }
        response = requests.get(url, params=params)

        if response.status_code != 200:
            return Response({'message': f"Error en el API de Google Distance Matrix: {response.status_code}"}, status=response.status_code)

        data = response.json()
        if data.get('status') != 'OK':
            return Response({'message': f"Error en la respuesta del API de Google Distance Matrix: {data.get('status')}"}, status=status.HTTP_400_BAD_REQUEST)

        elements = data.get('rows')[0]['elements'][0]
        distance_value = elements['distance']['value']
        distance_text = elements['distance']['text']
        duration_value = elements['duration']['value']
        duration_text = elements['duration']['text']

        recommended_value = (km_value * (distance_value / 1000) + min_value * (duration_value / 60))
        
        response_data = {
            'recommended_value': recommended_value,
            'destination_addresses': data.get('destination_addresses')[0],
            'origin_addresses': data.get('origin_addresses')[0],
            'distance': {
                'text': distance_text,
                'value': (distance_value / 1000)
            },
            'duration': {
                'text': duration_text,
                'value': (duration_value / 60)
            },
        }

        return Response(response_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_status(request):
    id_client_request = request.data.get('id_client_request')
    status_data = request.data.get('status')

    sql = """
        UPDATE client_requests
        SET 
           status = %s,
           updated_at = NOW()
        WHERE id = %s   
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, [status_data, id_client_request])
            return Response({'success': True}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'message': f'Error al actualizar el viaje: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_client_rating(request):
    id_client_request = request.data.get('id_client_request')
    client_rating = request.data.get('client_rating')

    sql = """
        UPDATE client_requests
        SET 
           client_rating = %s,
           updated_at = NOW()
        WHERE id = %s   
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, [client_rating, id_client_request])
            return Response({'success': True}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'message': f'Error al actualizar la calificación: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_driver_rating(request):
    id_client_request = request.data.get('id_client_request')
    driver_rating = request.data.get('driver_rating')

    sql = """
        UPDATE client_requests
        SET 
           driver_rating = %s,
           updated_at = NOW()
        WHERE id = %s   
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, [driver_rating, id_client_request])
            return Response({'success': True}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'message': f'Error al actualizar la calificación: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)