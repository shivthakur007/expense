import firebase_admin
from firebase_admin import credentials, firestore
import os

def get_db():
    if not firebase_admin._apps:
        cred = credentials.Certificate("firebase_key.json")
        firebase_admin.initialize_app(cred)
    return firestore.client()