This is a fork from https://github.com/c3r34lk1ll3r/weebase

⚠️ *_In heavy development. No support provided. There is an high chance
that this will crash weechat and/or it doesn't work_* ⚠️

# weebase
Plugin for integrate _keybase_ in _weechat_.

## Installation
Copy the python file in weechat plugin folder (for example `~/.weechat/python/`) and load it from weechat (`/python load keybase.py`)

## Requirements
- `kebase`: This plugin is simply a wrapper for `keybase` CLI.

## Options
- `plugin.var.python.weebase.nickname`: Your nickname
- `plugin.var.python.weebase.server_name`: Displayed name for server (default KeyBase)
- `plugin.var.python.weebase.debug`: Activate debugging information

## Commands:
- `\msg <sendto> <body>`: Sends a message to a nick
- `\download <msgID> <output>`: Download an attachment.
- `\open <msgID>`: Download and open an attachment (with `xdg-open`)

## NOTE
This plugin is in really alpha stage. Can crash or hang weechat. There
are a lot of work to do and a lot of testing. There are a lot of
missing features (like storing history, delete messages, upload
attacchment, all the teams management, ecc.) and a lot of bugs. Use it
at your risk.
