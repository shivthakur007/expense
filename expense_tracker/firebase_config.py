import json
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

def get_db():
    if not firebase_admin._apps:
        if "firebase" in st.secrets:
            cred = credentials.Certificate(dict(st.secrets["firebase"]))
        else:
            with open("firebase_key.json", "r", encoding="utf-8") as f:
                cred = credentials.Certificate(json.load(f))

        firebase_admin.initialize_app(cred)

    return firestore.client()
