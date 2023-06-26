from dataclasses import dataclass
import datetime
import os
import re
from typing import Optional, List
from urllib.parse import urljoin

import requests


_UID_URL = re.compile(r'\A.*/profile/users/(\d+)/\Z')

@dataclass(frozen=True)
class PinryUser:
    link: str
    id: int
    username: str
    token: Optional[str] # may be unknown
    email: str
    gravatar: str

    @classmethod
    def from_api(cls, data):
        link = data['resource_link']
        m = _UID_URL.match(link)
        assert m
        user_id = int(m.group(1))
        return cls(
            link=link,
            id=user_id,
            username=data['username'],
            token=data['token'],
            email=data['email'],
            # XXX: bug??? gravatar disappears in the
            # submitter field when POSTing a new pin
            gravatar=data.get('gravatar', None),
        )

    def __str__(self):
        return f'{self.username} <{self.email}>'


@dataclass(frozen=True)
class Image:
    url: int
    width: int
    height: int


@dataclass(frozen=True)
class PinryImage:
    id: int
    original: Image
    standard: Image
    thumbnail: Image
    square: Image

    @classmethod
    def from_api(cls, data):
        std = data['standard']
        thm = data['standard']
        sq = data['square']

        return cls(
            id=data['id'],
            original=Image(data['image'], data['width'], data['height']),
            standard=Image(std['image'], std['width'], std['height']),
            thumbnail=Image(thm['image'], thm['width'], thm['height']),
            square=Image(sq['image'], sq['width'], sq['height']),
        )


#
# please be noted that just because i didn't set this to
# frozen doesn't mean changes in the attributes will be
# reflected in pinry...
#
# for pins, you may only change PRIVATE, DESCRIPTION, URL,
# SOURCE, and TAGS.
#
# for boards, you may only change PRIVATE and NAME.
#
# to update your changes, use edit_pin() or edit_panel();
# the client will send the respective PATCH calls to the server.
#
@dataclass
class PinryPin:
    link: str  # resource_link
    id: int
    private: bool
    submitter: PinryUser
    url: Optional[str]
    description: str
    source: str  # referer
    image: PinryImage
    tags: List[str]

    @classmethod
    def from_api(cls, data):
        return cls(
            link=data['resource_link'],
            id=data['id'],
            private=data['private'],
            submitter=PinryUser.from_api(data['submitter']),
            url=data['url'],
            description=data['description'],
            source=data['referer'],
            image=PinryImage.from_api(data['image']),
            tags=data['tags'],
        )


@dataclass
class PinryBoard:
    link: str
    id: int
    name: str
    private: bool
    total_pins: int
    cover: Optional[PinryPin]
    published: datetime.datetime
    submitter: PinryUser

    @classmethod
    def from_api(cls, data):
        pubstr = data['published'].replace('Z', '+00:00')
        pubdate = datetime.datetime.fromisoformat(pubstr)
        submitter = PinryUser.from_api(data['submitter'])
        if data['cover'] is None:
            cover = None
        else:
            cover = PinryPin.from_api(data['cover'])
        return cls(
            link=data['resource_link'],
            id=data['id'],
            name=data['name'],
            private=data['private'],
            total_pins=data['total_pins'],
            cover=cover,
            published=pubdate,
            submitter=submitter,
        )


class PinryClient:
    #
    # yeah so basically, urljoin doesn't really work like '/'.join
    #
    #   *  if the first arg (base) doesn't end with a slash,
    #      then what comes AFTER the slash will be replaced by the
    #      second arg (url)
    #   *  if the second arg starts with a slash, then it'll
    #      think that you are starting from the root (netloc),
    #      and everything after that will be discarded
    #   *  if the second arg starts with TWO slashes, then
    #      everything after the schema usually (http:// or https://)
    #      is gone
    #   *  just imagine the second arg is a href and urljoin tells
    #      you where that href brings you...
    #
    # also see: https://stackoverflow.com/a/51555375
    #
    def __init__(self, url, token):
        self._api_prefix = urljoin(url, '/api/v2/')
        self._session = requests.Session()
        self._session.headers.update({'Authorization': f'Token {token}'})

    # nice context manager
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, tb):
        self.close()

    def close(self):
        self._session.close()

    # HTTP methods
    def get(self, url, **kwargs):
        api_url = urljoin(self._api_prefix, url)
        response = self._session.get(api_url, **kwargs)
        response.raise_for_status()
        return response.json()

    def post(self, url, **kwargs):
        api_url = urljoin(self._api_prefix, url)
        response = self._session.post(api_url, **kwargs)
        response.raise_for_status()
        return response.json()

    def patch(self, url, **kwargs):
        api_url = urljoin(self._api_prefix, url)
        response = self._session.patch(api_url, **kwargs)
        response.raise_for_status()
        return response.json()

    def delete(self, url):
        api_url = urljoin(self._api_prefix, url)
        response = self._session.delete(api_url)
        response.raise_for_status()
        return # None

    # user methods
    def get_user(self, username):
        queries = {'username': username}
        data = self.get('profile/public-users/', params=queries)
        return PinryUser.from_api(data[0])

    def get_current_user(self):
        data = self.get('profile/users/')
        return PinryUser.from_api(data[0])

    # board methods
    # limit 50 is API_LIMIT_PER_PAGE set in pinry/settings/base.py
    def get_board_info(self, *, username=None):
        if username is not None:
            queries = {'submitter__username': username}
        else:
            queries = {}
        return self.get('boards-auto-complete/', params=queries)

    def get_board(self, board_id):
        data = self.get(f'boards/{board_id}/')
        return PinryBoard.from_api(data)

    def get_boards(self, search=None, username=None, *, offset=0, limit=50):
        queries = {'limit': limit, 'offset': offset}
        if search is not None:
            queries['search'] = search
        if username is not None:
            queries['submitter__username'] = username
        return self.get('boards/', params=queries)

    def list_boards(self, search=None, username=None, *,
                    offset=0, limit=0, buffering=50):
        queried = 0
        while True:
            response = self.get_boards(
                search, username, offset=offset, limit=buffering)
            for data in response['results']:
                if limit and queried > limit:
                    return
                yield PinryBoard.from_api(data)
                queried += 1
            if response['next'] is None:
                return
            offset += limit

    def create_board(self, name, *, private=False):
        payload = {'name': name, 'private': private}
        data = self.post('boards/', json=payload)
        return PinryBoard.from_api(data)

    def delete_board(self, board_id):
        self.delete(f'boards/{board_id}')

    def edit_board(self, board: PinryBoard):
        payload = {'name': board.name, 'private': board.private}
        data = self.patch(f'boards/{board.id}/', json=payload)
        return PinryBoard.from_api(data)

    def add_pins_to_board(self, pin_ids, board_id):
        payload = {'pins_to_add': pin_ids}
        data = self.patch(f'boards/{board_id}/', json=payload)
        return PinryBoard.from_api(data)

    def remove_pins_from_board(self, pin_ids, board_id):
        payload = {'pins_to_remove': pin_ids}
        data = self.patch(f'boards/{board_id}/', json=payload)
        return PinryBoard.from_api(data)

    # pin methods
    def get_pin(self, pin_id):
        data = self.get(f'pins/{pin_id}/')
        return PinryPin.from_api(data)

    # ordering seems broken, ignore this
    def get_pins(self, board=None, username=None, tag=None,
                 *, offset=0, limit=50, ordering='-id'):
        queries = {'limit': limit, 'offset': offset,
                   'ordering': ordering}
        if board is not None:
            queries['pins__id'] = board.id
        if username is not None:
            queries['submitter__username'] = username
        if tag is not None:
            queries['tags__name'] = tag
        return self.get('pins/', params=queries)

    def list_pins(self, board=None, username=None, tag=None,
                  *, offset=0, limit=0, buffering=50,
                  ordering='-id'):
        queried = 0
        while True:
            response = self.get_pins(
                board, username, tag, offset=offset,
                limit=buffering, ordering=ordering)
            for data in response['results']:
                if limit and queried > limit:
                    return
                yield PinryPin.from_api(data)
                queried += 1
            if response['next'] is None:
                return
            offset += limit

    def delete_pin(self, pin_id):
        self.delete(f'pins/{pin_id}')

    # image can be a file object (opened in binary mode), but i guess
    # you can pass in (filename, file_object, content_type and headers)
    # explicitly too....
    # see: https://requests.readthedocs.io/en/latest/user/quickstart/#post-a-multipart-encoded-file
    def create_image(self, image):
        response = self.post('images', files={'image': image})
        return PinryImage.from_api(response)

    def create_pin(self, image, *, private=False, description=None,
                   source=None, tags=None, board=None):
        payload = {'private': private, 'description': description,
                   'referer': source, 'tags': tags}
        pinry_image = None
        # an existing image
        if isinstance(image, PinryImage):
            pinry_image = image
        # file system path
        elif os.path.exists(image):
            with open(url, 'rb') as file:
                pinry_image = self.create_image(file)
        # file object (i'm not sure if requests closes it...)
        elif hasattr(image, 'read'):
            pinry_image = self.create_image(image)
        if pinry_image is not None:
            payload['image_by_id'] = pinry_image.id
        else:
            payload['url'] = url
        data = self.post('pins/', json=payload)
        if board is not None:
            board = self.add_pins_to_board([data['id']], board.id)
        return PinryPin.from_api(data), board

    def edit_pin(self, pin: PinryPin):
        payload = {'private': pin.private, 'description': pin.description,
                   'url': pin.url, 'referer': pin.source, 'tags': pin.tags}
        data = self.patch(f'pins/{pin.id}/', json=payload)
        return PinryPin.from_api(data)

    # tag methods
    def get_tags_info(self):
        return self.get('tags-auto-complete/')
