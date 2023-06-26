# Unofficial Python API for Pinry

pinry is a self-hosted Pinterest-like tiling image board system
where you can put images and whatnot you like on an infinite
bulletin board

it's like, well, a barely functional version of Pinterest, except you
can actually credit your sources (which is VERY hard to do in
Pinterest) and everything you put in is actually yours (unlike SOME
services that just LOVE charging their APIs..... i'm looking at you
Twitter and Reddit >:c)

angry rant aside, i have nothing against you if you love
pinterest..... i just find it frustrating how okay it is to "steal",
or even profit off of art there without giving credit where it's due?
(seriously i just want to collect art for myself that's it.....)

## Dependencies

you need [requests][]. in case you didn't know it, requests is a very
nice library to have when you just want to make HTTP requests (like
what cURL does, but P Y T H O N Y)

also for dataclasses & f-strings & [`fromisoformat()`][iso] to make
sense you need at least Python 3.7 :v

## What can it do

LOTS of cool things (i'll show you in a minute!)

first grab your API key from [My -> Profile][key]

then you're good to go!!!!

the `PinryClient` class takes two arguments: the base URL of your
Pinry site (try appending `api/v2/` to its end) and your API key
(described above). to test if your token works, see if this gives
you the right user:

```python
with pinry_api.PinryClient(pinry_url, token) as api:
    print('I am', api.get_current_user().username)
    assert api.get_current_user().token == token
```

ok boring stuff aside, here's some fun things that you can do!

say if i want to get all the panels there are posted by me!
then you can use `list_boards()`:

```python
with pinry_api.PinryClient(pinry_url, token) as api:
    # replace yizmeng with your username of course
    for board in api.list_boards(username='yizmeng'):
        print(f'{board.name} ({board.id}): {board.total_pins} pin(s)')
```

for me this prints:

```
undertale (15): 2 pin(s)
among us (5): 4 pin(s)
bfdi & ii (4): 1 pin(s)
sussy (3): 2 pin(s)
isaac (2): 2 pin(s)
silly (1): 5 pin(s)
```

(ignore the gaps, i was testing POST api/v2/boards/ and it took
me a while to figure out how it worked =n= --- i did notice that
Pinry doesn't seem to reuse IDs even if you delete stuff? and
that's probably for the better...)

you might have guessed that we can do a similar thing for pins using
`list_pins()`, but it doesn't seem so helpful to simply gather all
pins i ever posted.... it would be nice if we could be a little more
specific and just, say, get pins from the "among us" board only.

once again, you can do that too!

```python
with pinry_api.PinryClient(pinry_url, token) as api:
    # get the unique board whose name matches "among us"
    (board,) = api.list_boards(search='among us', username='yizmeng')
    for pin in api.list_pins(board=board, username='yizmeng', ordering='id'):
        tags = ', '.join(f'#{tag}' for tag in pin.tags) or 'N/A'
        print(f'pin {pin.id}: {pin.description} (tagged {tags})')
```

and this gives me...

```
pin 38: "i'm really not an impostor..." (tagged N/A)
pin 36: yellow!!!! (tagged #colors, #drawing)
pin 10: serious man 2 (tagged #drawing, #smol)
pin 9: serious man 1 (tagged #drawing)
```

and ooh, yeah... i seem to have forgotten tagging that first entry.
AND YELLOW!!! i seem to have grown pretty fond of the yellow crewmate
in particular, so i wanna tag every pin with #yellow!

well `edit_pin()` lets you do that:

```python
# feeding the generator to list() so that
# we are iterating over a fixed set of pins
for pin in list(api.list_pins(board=board, username='yizmeng', ordering='id')):
    if 'yellow' not in pin.tags:
        pin.tags.append('yellow')
    api.edit_pin(pin)
```

in general you can edit the following attributes (i've tried most, but
let me know if any of these doesn't work):

*  `PinryPin`: description, url, source (referer), tags
*  `PinryBoard`: name, private


## Okay but how does it *actually* work?

i kind of reverse-engineered Pinry's API (and also shamelessly stole
from the [official python CLI][cli])

basically you make GET requests for querying stuff, POST requests to
create new stuff (and get what you just created), PATCH requests to
update (or "edit") existing stuff (with an ID you already acquired in
some way), and finally DELETE requests to... you guessed it, delete
stuff.

(and if you haven't already, add [JSONView][] to your browser, it's
rlly rlly good :>)

so let's go back to our original example, shall we? the one where we
printed out all the boards we have with `list_boards()`. well it's
essentially this:

```http
GET /api/v2/boards/?submitter__username=yizmeng&offset=0&limit=50
```

so as you can see, the arguments you gave (as well as some specific
parameters to work with pagination) are passed in as queries in the
form `?param1=value1&param2=value2`. for these you can pass into [the
`params` keyword argument][params] of request's any method, which is
really handy compared to manually concatenating & worrying about
escapes.

but wait, you might say, it still feels quite different.... like if
you actually went ahead and made that GET request, you get this whole
JSON thingy (very simplified):

```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "resource_link": "http://localhost/api/v2/boards/15/",
      "id": 15,
      "name": "undertale"
    },
    {
      "resource_link": "http://localhost/api/v2/boards/5/",
      "id": 5,
      "name": "among us"
    },
    {
      "resource_link": "http://localhost/api/v2/boards/4/",
      "id": 4,
      "name": "bfdi & ii",
    },
    {
      "resource_link": "http://localhost/api/v2/boards/2/",
      "id": 2,
      "name": "isaac",
    },
    {
      "resource_link": "http://localhost/api/v2/boards/1/",
      "id": 1,
      "name": "silly",
    }
  ]
}
```

but if you compare this to what you would've gotten from printing out
the repr of each board:

```
PinryBoard(link='http://localhost/api/v2/boards/15/', id=15, name='undertale')
PinryBoard(link='http://localhost/api/v2/boards/5/', id=5, name='among us')
PinryBoard(link='http://localhost/api/v2/boards/4/', id=4, name='bfdi & ii')
PinryBoard(link='http://localhost/api/v2/boards/3/', id=3, name='sussy')
PinryBoard(link='http://localhost/api/v2/boards/2/', id=2, name='isaac')
PinryBoard(link='http://localhost/api/v2/boards/1/', id=1, name='silly')
```

yeah... it's the same thing. just wrapped up in a fancy way
(recursively too! so expect the `submitter` field to be of `PinryUser`
type and the `cover` field to be of `PinryPin` type!)


## Bugs?

i wrote ~~all~~ most of this in a day so don't expect much

(PRs are welcome! though i doubt people will actually find this...)


[cli]: https://github.com/pinry/pinry-cli-py/
[key]: https://docs.getpinry.com/api/
[iso]: https://docs.python.org/3/library/datetime.html#datetime.datetime.fromisoformat
[requests]: https://requests.rtfd.io
[JSONView]: https://jsonview.com/
[params]: https://requests.readthedocs.io/en/latest/user/quickstart/#passing-parameters-in-urls
