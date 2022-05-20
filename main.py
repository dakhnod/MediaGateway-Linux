import os
import random
import pydbus
import pydbus.timeout
from gi.repository import GLib

import dotenv
dotenv.load_dotenv()

import fcm_xmpp

FCM_TOKEN = os.environ['FCM_TOKEN']
FCM_RECIPIENT = os.environ['FCM_RECIPIENT']

old_playback_data = None
ignore_meta_messages = False
last_media_address = None

session_bus = pydbus.SessionBus()
fcm = fcm_xmpp.FCMXMPPConnection()


def signal_handler(sender, object, iface, signal, params):
    global old_playback_data, ignore_meta_messages, last_media_address#

    can_play = params[1].get('CanPlay')
    if can_play is not None:
        ignore_meta_messages = not can_play
        if can_play:
            print('unignoring messages')
        else:
            print('ignoring messages')
        return

    if ignore_meta_messages:
        return

    last_media_address = sender

    playback_state = get_player_attribute(sender, 'PlaybackStatus')
    if playback_state == 'Stopped':
        ignore_meta_messages = True
        return
    meta_data = get_player_attribute(sender, 'Metadata')

    playback_data = {
        'playbackState': playback_state,
        'artist': meta_data['xesam:artist'][0],
        'title': meta_data['xesam:title']
    }
    if playback_data == old_playback_data:
        return
    old_playback_data = playback_data
    send_fcm_message(FCM_RECIPIENT, playback_data)
    print(playback_data)


def call_player_func(address, function):
    session_bus.con.call_sync(
        address,
        '/org/mpris/MediaPlayer2',
        'org.mpris.MediaPlayer2.Player',
        function,
        None,
        None,
        0,
        pydbus.timeout.timeout_to_glib(1000),
        None
    )


def get_player_attribute(address, attribute):
    res = session_bus.con.call_sync(
        address,
        '/org/mpris/MediaPlayer2',
        'org.freedesktop.DBus.Properties',
        'Get',
        GLib.Variant('(ss)', ('org.mpris.MediaPlayer2.Player', attribute)),
        GLib.VariantType.new('(v)'),
        0,
        pydbus.timeout.timeout_to_glib(1000),
        None
    )
    return res[0]


def send_fcm_message(recipient: str, data: dict):
    fcm.send_message({
        'to': recipient,
        'data': data,
        'message_id': ''.join(random.choices("abcdefghijklmnopqrstuvwxyz", k=20))
    })
    """
    response = requests.post(
        'https://fcm.googleapis.com/fcm/send',
        json={
            'to': recipient,
            'data': data
        },
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'key={FCM_TOKEN}'
        }
    )
    """


def main():
    session_bus.subscribe(
        object='/org/mpris/MediaPlayer2',
        signal='PropertiesChanged',
        iface='org.freedesktop.DBus.Properties',
        signal_fired=signal_handler
    )

    def handle_app_message(message):
        command = message['media_command']
        print(f'received command {command}')
        if command and last_media_address:
            call_player_func(last_media_address, command.title())

    fcm.start_in_background(handle_app_message)
    loop = GLib.MainLoop()
    loop.run()


if __name__ == '__main__':
    main()
