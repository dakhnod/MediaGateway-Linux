import asyncio
import json
import time
import os

import aioxmpp
import aioxmpp.dispatcher
import aioxmpp.connector
import aioxmpp.xso
import logging
import threading

logging.basicConfig(level=logging.DEBUG)

ID = f"{os.environ['FCM_SENDER_ID']}@fcm.googleapis.com"
PASSWORD = os.environ['FCM_TOKEN']


class FCMMessage(aioxmpp.xso.XSO):
    TAG = ('google:mobile:data', 'gcm')
    text = aioxmpp.xso.Text(default=None)


aioxmpp.stanza.Message.fcm_payload = aioxmpp.xso.Child([FCMMessage])


class FCMXMPPConnection:
    def __init__(self) -> None:
        self.client = None
        self.event_loop = None

    async def main(self, message_callback):
        def message_handler(message):
            body = json.loads(message.fcm_payload.text)
            sender = body['from']
            message_id = body['message_id']
            message_type = body.get('message_type')
            if message_type and message_type in ['ack', 'nack']:
                return
            self.send_message({
                'message_type': 'ack',
                'message_id': message_id,
                'to': sender
            })
            message_callback(body['data'])

        self.client = aioxmpp.PresenceManagedClient(
            aioxmpp.JID.fromstr(ID),
            aioxmpp.make_security_layer(PASSWORD),
            override_peer=[('fcm-xmpp.googleapis.com', 5236, aioxmpp.connector.XMPPOverTLSConnector())]
        )
        self.event_loop = asyncio.get_event_loop()

        print('connecting...')
        await self.client.connected().__aenter__()
        print('in context manager')
        message_dispatcher = self.client.summon(
            aioxmpp.dispatcher.SimpleMessageDispatcher
        )

        message_dispatcher.register_callback(
            aioxmpp.MessageType.NORMAL,
            None,
            message_handler
        )

        await asyncio.sleep(999999)

    def start_loop(self, message_callback):
        asyncio.run(self.main(message_callback))

    def send_message(self, payload):
        fcm_data = FCMMessage()
        fcm_data.text = json.dumps(payload)
        message = aioxmpp.Message(
            type_=aioxmpp.MessageType.NORMAL
        )
        message.fcm_payload = fcm_data
        print('call_soon')
        self.event_loop.call_soon_threadsafe(self.client.enqueue(message))

    def start_in_background(self, message_callback):
        t = threading.Thread(target=self.start_loop, args=[message_callback])
        t.start()
