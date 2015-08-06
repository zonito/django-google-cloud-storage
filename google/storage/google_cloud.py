"""Google cloud communication bridge."""

import mimetypes
import os
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from google.appengine.api.blobstore import create_gs_key
import cloudstorage as gcs


class GoogleCloudStorage(Storage):

    def __init__(self, location=None, base_url=None):
        if location is None:
            location = settings.GOOGLE_CLOUD_STORAGE_BUCKET
        self.location = location
        if base_url is None:
            base_url = settings.GOOGLE_CLOUD_STORAGE_URL
        self.base_url = base_url

    def _open(self, name):
        """Return given name content."""
        filename = self.location + "/" + name
        gcs_file = gcs.open(filename, mode='r')
        content = ContentFile(gcs_file.read())
        gcs_file.close()
        return content

    def _save(self, name, content):
        """Save to google storage"""
        filename = self.location + "/" + name
        filename = os.path.normpath(filename)
        mime_type, _ = mimetypes.guess_type(name)
        # files are stored with public-read permissions. Check out the google
        # acl options if you need to alter this.
        gss_file = gcs.open(
            filename,
            mode='w',
            content_type=mime_type,
            options={
                'x-goog-acl': 'public-read',
                'cache-control': settings.GOOGLE_CLOUD_STORAGE_DEFAULT_CACHE_CONTROL
            }
        )
        content.open()
        gss_file.write(content.read())
        content.close()
        gss_file.close()
        return name

    def delete(self, name):
        filename = self.location + "/" + name
        try:
            gcs.delete(filename)
        except gcs.NotFoundError:
            pass

    def exists(self, name):
        try:
            self.stat_file(name)
            return True
        except gcs.NotFoundError:
            return False

    def listdir(self, path=None):
        directories, files = [], []
        bucket_contents = gcs.listbucket(self.location, prefix=path)
        for entry in bucket_contents:
            file_path = entry.filename
            head, tail = os.path.split(file_path)
            sub_path = os.path.join(self.location, path)
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
            filename = "/gs" + self.location + "/" + name
            key = create_gs_key(filename)
            return "http://localhost:8000/blobstore/blob/" + key + "?display=inline"
        return self.base_url + "/" + name

    def stat_file(self, name):
        """Return file status."""
        filename = self.location + "/" + name
        return gcs.stat(filename)
