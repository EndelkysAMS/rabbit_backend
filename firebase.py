import firebase_admin 
from firebase_admin import credentials, messaging

cred = credentials.Certificate('./firebase-service-account.json')

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)