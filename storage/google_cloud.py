"""Google cloud communication bridge."""

import cloudstorage
import httplib2
import json
import mimetypes
import os

from googleapiclient import http
from googleapiclient.discovery import build
from django.conf import settings
from oauth2client.client import SignedJwtAssertionCredentials

from django.core.files.base import ContentFile
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

    def _open(self, name):
        """Return given name content."""
        filename = self.bucket + "/" + name
        gcs_file = cloudstorage.open(filename, mode='r')
        content = ContentFile(gcs_file.read())
        gcs_file.close()
        return content

    def _save(self, name, content):
        """Save to google storage"""
        filename = self.bucket + "/" + name
        filename = os.path.normpath(filename)
        mime_type, _ = mimetypes.guess_type(name)
        # files are stored with public-read permissions. Check out the google
        # acl options if you need to alter this.
        gss_file = cloudstorage.open(
            filename,
            mode='w',
            content_type=mime_type,
            options={
                'x-goog-acl': 'public-read',
                'cache-control': (
                    settings.GOOGLE_CLOUD_STORAGE_DEFAULT_CACHE_CONTROL)
            }
        )
        content.open()
        gss_file.write(content.read())
        content.close()
        gss_file.close()
        return name

    def delete(self, name):
        filename = self.bucket + "/" + name
        try:
            cloudstorage.delete(filename)
        except cloudstorage.NotFoundError:
            pass

    def exists(self, name):
        try:
            self.stat_file(name)
            return True
        except http.HttpError:
            return False

    def listdir(self, path=None):
        directories, files = [], []
        bucket_contents = cloudstorage.listbucket(self.bucket, prefix=path)
        for entry in bucket_contents:
            file_path = entry.filename
            head, tail = os.path.split(file_path)
            sub_path = os.path.join(self.bucket, path)
            head = head.replace(sub_path, '', 1)
            if head == "":
                head = None
            if not head and tail:
                files.append(tail)
            if head:
                if not head.startswith("/"):
                    head = "/" + head
                directory = head.split("/")[1]
                if not directory in directories:
                    directories.append(directory)
        return directories, files

    def size(self, name):
        stats = self.stat_file(name)
        return stats.st_size

    def accessed_time(self, name):
        raise NotImplementedError

    def created_time(self, name):
        stats = self.stat_file(name)
        return stats.st_ctime

    def modified_time(self, name):
        return self.created_time(name)

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

    def stat_file(self, name):
        """Return file status."""
        return self.service.objects().get(
            bucket=self.bucket, object=name).execute()
