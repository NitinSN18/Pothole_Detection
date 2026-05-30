"""Firebase utilities for AVISENS.

Provides lightweight wrappers for initializing Firebase Admin SDK, uploading
images to Firebase Storage, storing report documents in Firestore, fetching
reports, and updating repair status.

This module is optional — if `firebase_admin` is not installed or credentials
are not provided, functions will raise informative errors.
"""
from typing import Optional, Dict, Any, List
import io
import time
import traceback

try:
    import firebase_admin
    from firebase_admin import credentials, storage, firestore
except Exception:
    firebase_admin = None


_app = None
_bucket = None
_db = None


def init_firebase(cred_path: Optional[str] = None, storage_bucket: Optional[str] = None):
    """Initialize Firebase Admin SDK.

    cred_path: path to service account JSON. If None, will try application default.
    storage_bucket: name of Firebase Storage bucket (e.g. 'your-app.appspot.com').
    """
    global _app, _bucket, _db
    if firebase_admin is None:
        raise RuntimeError("firebase_admin not installed. Install 'firebase-admin' to use Firebase features.")

    if _app is not None:
        return _app

    try:
        if cred_path:
            cred = credentials.Certificate(cred_path)
            _app = firebase_admin.initialize_app(cred, {'storageBucket': storage_bucket} if storage_bucket else None)
        else:
            # Use ADC
            _app = firebase_admin.initialize_app(options={'storageBucket': storage_bucket} if storage_bucket else None)

        _db = firestore.client()
        if storage_bucket:
            _bucket = storage.bucket()

        return _app
    except Exception as e:
        raise RuntimeError(f"Failed to initialize Firebase: {e}\n{traceback.format_exc()}")


def upload_image_bytes(image_bytes: bytes, destination_path: str) -> str:
    """Upload raw image bytes to Firebase Storage and return a public URL (if possible).

    destination_path: path inside the bucket, e.g. 'potholes/img-123.png'
    """
    if firebase_admin is None:
        raise RuntimeError("firebase_admin not installed")
    if _bucket is None:
        raise RuntimeError("Firebase storage bucket not initialized. Call init_firebase() with storage_bucket.")

    blob = _bucket.blob(destination_path)
    blob.upload_from_string(image_bytes, content_type='image/png')
    try:
        # Make public (optional). In production, use signed URLs or proper rules.
        blob.make_public()
        return blob.public_url
    except Exception:
        # Fallback: return gs:// path
        return f"gs://{_bucket.name}/{destination_path}"


def save_report(report: Dict[str, Any]) -> str:
    """Save report dict to Firestore `potholes` collection. Returns document id."""
    if firebase_admin is None:
        raise RuntimeError("firebase_admin not installed")
    if _db is None:
        raise RuntimeError("Firestore not initialized. Call init_firebase() first.")

    coll = _db.collection('potholes')
    data = dict(report)
    data.setdefault('timestamp', int(time.time()))
    data.setdefault('status', 'Detected')
    doc_ref = coll.document()
    doc_ref.set(data)
    return doc_ref.id


def fetch_reports(limit: int = 100) -> List[Dict[str, Any]]:
    """Fetch recent reports from `potholes` collection.

    Returns list of documents with `id` included.
    """
    if firebase_admin is None:
        raise RuntimeError("firebase_admin not installed")
    if _db is None:
        raise RuntimeError("Firestore not initialized. Call init_firebase() first.")

    coll = _db.collection('potholes')
    docs = coll.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(limit).stream()
    out = []
    for d in docs:
        rec = d.to_dict()
        rec['id'] = d.id
        out.append(rec)
    return out


def update_status(doc_id: str, status: str) -> bool:
    """Update repair status for a report. Returns True on success."""
    if firebase_admin is None:
        raise RuntimeError("firebase_admin not installed")
    if _db is None:
        raise RuntimeError("Firestore not initialized. Call init_firebase() first.")

    doc_ref = _db.collection('potholes').document(doc_id)
    doc_ref.update({'status': status})
    return True


if __name__ == '__main__':
    print('firebase_utils: call init_firebase(cred_path, storage_bucket) before use')
