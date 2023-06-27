import pinry_api

pinry_url = 'http://localhost'
token = open('.venv/secret').read().strip()

with pinry_api.PinryClient(pinry_url, token) as cli:
    print('I am', cli.get_current_user().username)
    assert cli.get_current_user().token == token
    for board in cli.list_boards(username='yizmeng'):
        print(board)

with pinry_api.PinryClient(pinry_url, token) as api:
    # get the unique board called "among us"
    (board,) = api.list_boards(search='among us', username='yizmeng')
    for pin in api.list_pins(board=board, username='yizmeng', ordering='id'):
        tags = ', '.join(f'#{tag}' for tag in pin.tags) or 'N/A'
        print(f'pin {pin.id}: {pin.description} (tagged {tags})')
    #for pin in list(api.list_pins(board=board, username='yizmeng', ordering='id')):
    #    if 'yellow' not in pin.tags:
    #        pin.tags.append('yellow')
    #    api.edit_pin(pin)
