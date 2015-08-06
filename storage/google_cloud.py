"""Google cloud communication bridge."""

import httplib2
import json
import mimetypes
import os

from googleapiclient import http
from googleapiclient.discovery import build
from django.conf import settings
from oauth2client.client import SignedJwtAssertionCredentials

from django.core.files.storage import Storage
from google.appengine.api.blobstore import create_gs_key

_SCOPE = 'https://www.googleapis.com/auth/devstorage.full_control'


# pylint: disable=R0921
class GoogleCloudStorage(Storage):

    """Class to handle django filefield."""

    def __init__(self):
        self.private_info = self._get_private_info()
        credentials = SignedJwtAssertionCredentials(
            self.private_info['client_email'],
            self.private_info['private_key'],
            scope=_SCOPE
        )
        http_credential = credentials.authorize(httplib2.Http())
        self.service = build("storage", "v1", http=http_credential)
        self.bucket = settings.GOOGLE_CLOUD_STORAGE_BUCKET
        self.base_url = settings.GOOGLE_CLOUD_STORAGE_URL

    @classmethod
    def _get_private_info(cls):
        """Return json data private key file."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        file_pointer = file(
            os.path.join(base, settings.GOOGLE_PRIVATE_KEY_FILE), 'rb')
        private_info = json.loads(file_pointer.read())
        file_pointer.close()
        return private_info

    def _save(self, name, content):
        """Save to google storage"""
        mime_type, _ = mimetypes.guess_type(name)
        content.open()
        media = http.MediaIoBaseUpload(content, mime_type)
        content.close()
        try:
            response = self.service.objects().insert(
                bucket=self.bucket,
                name=name,
                predefinedAcl='publicRead',
                media_body=media)
            response.execute()
        except http.HttpError as http_error:
            print("[Error in objects access for GCS]: error: %s", http_error)
        else:
            return self.base_url + '/' + name

    def delete(self, name):
        try:
            self.service.objects().delete(
                bucket=self.bucket, object=name).execute()
        except http.HttpError:
            pass

    def exists(self, name):
        try:
            self.stat_file(name)
            return True
        except http.HttpError:
            return False

    def url(self, name):
        if settings.DEBUG:
            # we need this in order to display images, links to files, etc from
            # the local appengine server
            filename = "/gs" + self.bucket + "/" + name
            key = create_gs_key(filename)
            return (
                "http://localhost:8000/blobstore/blob/" + key +
                "?display=inline"
            )
        return self.base_url + "/" + name

    def size(self, name):
        stats = self.stat_file(name)
        return stats.get('size')

    def stat_file(self, name):
        """Return file status."""
        return self.service.objects().get(
            bucket=self.bucket, object=name).execute()
