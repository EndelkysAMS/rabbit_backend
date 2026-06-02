from django.urls import path
from .views import update, updateWithImage, get_user_by_id, get_all_users,update_notification_token
urlpatterns =  [
    path('<int:id_user>', update),
    path('get/<int:id_user>', get_user_by_id),
    path('all', get_all_users),
    path('upload/<id_user>', updateWithImage),
    path('/notification_token/<id_user>', update_notification_token),
    #path('/login', login )
]