import bcrypt
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from roles.models import Role
from roles.serializers import RoleSerializer
from users.models import User, UserHasRoles
from django.conf import settings
from driver_position.models import DriverPosition
from driver_bike_info.models import DriverBikeInfo

ADMIN_LINE_ROLE_ID = 'ADMIN_LINEA'
DRIVER_ROLE_ID = 'DRIVER'


def _image_url(image_path):
    if not image_path:
        return None
    if str(image_path).startswith('http://') or str(image_path).startswith('https://'):
        return image_path
    return f"http://{settings.GLOBAL_IP}:{settings.GLOBAL_HOST}{image_path}"


def _is_admin_linea(user):
    return UserHasRoles.objects.filter(id_user=user, id_rol_id=ADMIN_LINE_ROLE_ID).exists()


def _admin_or_403(request):
    admin = User.objects.filter(id=request.user.id).first()
    if not admin:
        return None, Response({'message': 'Usuario no encontrado'}, status=status.HTTP_401_UNAUTHORIZED)
    if not _is_admin_linea(admin):
        return None, Response({'message': 'No tienes permisos de ADMIN_LINEA'}, status=status.HTTP_403_FORBIDDEN)
    if not admin.line_id:
        return None, Response({'message': 'El admin no tiene línea asignada'}, status=status.HTTP_400_BAD_REQUEST)
    if not admin.is_active:
        return None, Response({'message': 'Usuario inactivo'}, status=status.HTTP_403_FORBIDDEN)
    return admin, None


def _user_payload(user):
    roles = Role.objects.filter(userhasroles__id_user=user)
    return {
        'id': user.id,
        'name': user.name,
        'lastname': user.lastname,
        'email': user.email,
        'phone': user.phone,
        'image': _image_url(user.image),
        'is_active': user.is_active,
        'line': {
            'id': user.line.id if user.line else None,
            'name': user.line.name if user.line else None,
        },
        'roles': RoleSerializer(roles, many=True).data,
        'created_at': user.created_at,
        'updated_at': user.updated_at,
    }


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_driver_by_admin_linea(request):
    return _create_driver_by_admin_linea(request)


def _create_driver_by_admin_linea(request):
    admin, err = _admin_or_403(request)
    if err:
        return err

    name = request.data.get('name')
    lastname = request.data.get('lastname')
    email = request.data.get('email')
    phone = request.data.get('phone')
    password = request.data.get('password')
    image = request.data.get('image')

    if not all([name, lastname, email, phone, password]):
        return Response(
            {'message': 'name, lastname, email, phone y password son obligatorios'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if User.objects.filter(email=email).exists():
        return Response({'message': 'El email ya está registrado'}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(phone=phone).exists():
        return Response({'message': 'El teléfono ya está registrado'}, status=status.HTTP_400_BAD_REQUEST)

    driver_role = Role.objects.filter(id=DRIVER_ROLE_ID).first()
    if not driver_role:
        return Response({'message': 'No existe el rol DRIVER'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    with transaction.atomic():
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        driver = User.objects.create(
            name=name,
            lastname=lastname,
            email=email,
            phone=phone,
            image=image,
            password=hashed_password,
            notification_token=request.data.get('notification_token'),
            line_id=admin.line_id,
            is_active=True,
            created_by_admin_linea=admin,
        )
        UserHasRoles.objects.get_or_create(id_user=driver, id_rol=driver_role)

    return Response(_user_payload(driver), status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_drivers_by_admin_linea(request):
    return _list_drivers_by_admin_linea(request)


def _parse_is_active_filter(request):
    """Default: active only. Use ?is_active=false to list inactive drivers of the line."""
    raw = request.query_params.get('is_active')
    if raw is None or raw == '':
        return True, None
    normalized = str(raw).strip().lower()
    if normalized in ('true', '1', 'yes'):
        return True, None
    if normalized in ('false', '0', 'no'):
        return False, None
    return None, Response(
        {'message': 'is_active debe ser true o false'},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _list_drivers_by_admin_linea(request):
    admin, err = _admin_or_403(request)
    if err:
        return err

    is_active, parse_error = _parse_is_active_filter(request)
    if parse_error:
        return parse_error

    drivers = (
        User.objects.filter(
            line_id=admin.line_id,
            is_active=is_active,
            userhasroles__id_rol_id=DRIVER_ROLE_ID,
        )
        .order_by('-id')
        .distinct()
    )
    return Response([_user_payload(driver) for driver in drivers], status=status.HTTP_200_OK)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def admin_linea_drivers(request):
    if request.method == 'GET':
        return _list_drivers_by_admin_linea(request)
    return _create_driver_by_admin_linea(request)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def deactivate_driver_by_admin_linea(request, id_driver):
    admin, err = _admin_or_403(request)
    if err:
        return err

    driver = (
        User.objects.filter(id=id_driver, userhasroles__id_rol_id=DRIVER_ROLE_ID)
        .distinct()
        .first()
    )
    if not driver:
        return Response({'message': 'Conductor no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    if driver.line_id != admin.line_id:
        return Response({'message': 'No puedes operar conductores de otra línea'}, status=status.HTTP_403_FORBIDDEN)

    if not driver.is_active:
        return Response({'message': 'El conductor ya está desactivado'}, status=status.HTTP_200_OK)

    driver.is_active = False
    driver.deactivated_by_admin_linea = admin
    driver.deactivated_at = timezone.now()
    driver.save(update_fields=['is_active', 'deactivated_by_admin_linea', 'deactivated_at', 'updated_at'])
    return Response({'success': True, 'driver': _user_payload(driver)}, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_driver_by_admin_linea(request, id_driver):
    admin, err = _admin_or_403(request)
    if err:
        return err

    driver = (
        User.objects.filter(id=id_driver, userhasroles__id_rol_id=DRIVER_ROLE_ID)
        .distinct()
        .first()
    )
    if not driver:
        return Response({'message': 'Conductor no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    if driver.line_id != admin.line_id:
        return Response({'message': 'No puedes operar conductores de otra línea'}, status=status.HTTP_403_FORBIDDEN)

    if driver.is_active:
        return Response(
            {'message': 'Primero debes desactivar el conductor antes de eliminarlo definitivamente'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        # Keep historical trips/offers integrity by preserving the user record.
        # "Definitive delete" from line context means removing DRIVER capability and line linkage.
        DriverPosition.objects.filter(id_driver=driver).delete()
        DriverBikeInfo.objects.filter(id_driver=driver).delete()
        UserHasRoles.objects.filter(id_user=driver, id_rol_id=DRIVER_ROLE_ID).delete()

        driver.line = None
        driver.deactivated_by_admin_linea = admin
        driver.deactivated_at = timezone.now()
        driver.save(update_fields=['line', 'deactivated_by_admin_linea', 'deactivated_at', 'updated_at'])

    return Response(
        {
            'success': True,
            'message': 'Conductor eliminado definitivamente de la línea',
            'driver_id': driver.id,
        },
        status=status.HTTP_200_OK,
    )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_admin_linea_profile(request):
    admin, err = _admin_or_403(request)
    if err:
        return err

    name = request.data.get('name')
    lastname = request.data.get('lastname')
    phone = request.data.get('phone')
    image = request.data.get('image')
    password = request.data.get('password')

    if name is None and lastname is None and phone is None and image is None and password is None:
        return Response({'message': 'No se enviaron datos para actualizar'}, status=status.HTTP_400_BAD_REQUEST)

    if phone is not None:
        existing = User.objects.filter(phone=phone).exclude(id=admin.id).first()
        if existing:
            return Response({'message': 'El teléfono ya está registrado'}, status=status.HTTP_400_BAD_REQUEST)

    if name is not None:
        admin.name = name
    if lastname is not None:
        admin.lastname = lastname
    if phone is not None:
        admin.phone = phone
    if image is not None:
        admin.image = image
    if password is not None:
        if str(password).strip() == '':
            return Response({'message': 'password no puede ser vacío'}, status=status.HTTP_400_BAD_REQUEST)
        admin.password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    admin.save()
    return Response(_user_payload(admin), status=status.HTTP_200_OK)
