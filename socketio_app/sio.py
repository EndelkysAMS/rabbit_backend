import socketio
import json

sio = socketio.AsyncServer(async_mode='asgi')


@sio.event
async def connect(sid, environ):
    print(f'Cliente conectado: {sid}')
    await sio.emit('message', {'data': 'conexión exitosa'}, to=sid)

@sio.event
async def disconnect(sid):
    print(f'Cliente desconectado: {sid}')
    await sio.emit('driver_disconnected', {'id_socket': sid})

@sio.event
async def message(sid, data):
    print(f'Datos del Cliente en socket: {sid}: {data}')
    await sio.emit('new_message', data, to=sid)

@sio.event
async def change_driver_position(sid, data):
    try:
        if isinstance(data, dict):
            json_data = data
        elif isinstance(data, str):
            json_data = json.loads(data)
        else:
            print(f'Hay un error en el tipo de dato: {type(data)}')
            return  
        
        print(f'Emitió nueva posición en socket: {sid}: {data}')
        await sio.emit('new_driver_position', {
            'id_socket': sid,
            'id': json_data['id'],
            'lat': json_data['lat'],
            'lng': json_data['lng']
        })
    except json.JSONDecodeError as e:
        print(f'Error al parsear JSON {e}')
    except KeyError as e:
        print(f'Falta algún dato en la petición {e}')

@sio.event
async def new_client_request(sid, data):
    try:
        if isinstance(data, dict):
            json_data = data
        elif isinstance(data, str):
            json_data = json.loads(data)
        else:
            print(f'Hay un error en el tipo de dato: {type(data)}')
            return  
        
        print(f'Se emitió  una nueva solicitud en socket: {sid}: {data}')
        await sio.emit('created_client_request', {
            'id_socket': sid,
            'id_client_request': json_data['id_client_request'],
        })
    except json.JSONDecodeError as e:
        print(f'Error al parsear JSON {e}')
    except KeyError as e:
        print(f'Falta algún dato en la petición {e}')



@sio.event
async def new_driver_offer(sid, data):
    try:
        if isinstance(data, dict):
            json_data = data
        elif isinstance(data, str):
            json_data = json.loads(data)
        else:
            print(f'Hay un error en el tipo de dato: {type(data)}')
            return  
        
        print(f'El conductor  emitió  una nueva oferta en socket: {sid}: {data}')
        await sio.emit(
            f"created_driver_offer/{json_data['id_client_request']}",
             {
            'id_socket': sid
        })
    except json.JSONDecodeError as e:
        print(f'Error al parsear JSON {e}')
    except KeyError as e:
        print(f'Falta algún dato en la petición {e}')


@sio.event
async def new_driver_assigned(sid, data):
    try:
        if isinstance(data, dict):
            json_data = data
        elif isinstance(data, str):
            json_data = json.loads(data)
        else:
            print(f'Hay un error en el tipo de dato: {type(data)}')
            return  
        
        print(f'Emitió  una asignación de conductor en socket: {sid}: {data}')
        await sio.emit(
            f"driver_assigned/{json_data['id_driver']}",
             {
            'id_socket': sid,
            'id_client_request': json_data['id_driver']
        })
    except json.JSONDecodeError as e:
        print(f'Error al parsear JSON {e}')
    except KeyError as e:
        print(f'Falta algún dato en la petición {e}')


@sio.event
async def trip_change_driver_position(sid, data):
    try:
        if isinstance(data, dict):
            json_data = data
        elif isinstance(data, str):
            json_data = json.loads(data)
        else:
            print(f'Hay un error en el tipo de dato: {type(data)}')
            return  
        
        print(f'Emitió  una asignación de conductor en socket: {sid}: {data}')
        await sio.emit(
            f"trip_new_driver_position/{json_data['id_client']}",
             {
            'id_socket': sid,
            'lat': json_data['lat'],
            'lng': json_data['lng']
        })
    except json.JSONDecodeError as e:
        print(f'Error al parsear JSON {e}')
    except KeyError as e:
        print(f'Falta algún dato en la petición {e}')


@sio.event
async def update_status_trip(sid, data):
    try:
        if isinstance(data, dict):
            json_data = data
        elif isinstance(data, str):
            json_data = json.loads(data)
        else:
            print(f'Hay un error en el tipo de dato: {type(data)}')
            return  
        
        print(f'Emitió  una asignación de conductor en socket: {sid}: {data}')
        await sio.emit(
            f"new_status_trip/{json_data['id_client_request']}",
             {
            'id_socket': sid,
            'status': json_data['status'],
            'id_client_request': json_data['id_client_request']
        })
    except json.JSONDecodeError as e:
        print(f'Error al parsear JSON {e}')
    except KeyError as e:
        print(f'Falta algún dato en la petición {e}')        