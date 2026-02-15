import json
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

def get_db():
    if not firebase_admin._apps:
        firebase_dict = json.loads(st.secrets["firebase"]["credentials"])
        cred = credentials.Certificate(firebase_dict)
        firebase_admin.initialize_app(cred)

    return firestore.client()
