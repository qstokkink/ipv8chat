"""
INCOMING JSON:

{
    "action": "join",
    "communityid": "<40 CHAR HEX>"
}

{
    "action": "send",
    "message": "<250 CHAR OR LESS UTF-8 MESSAGE>"
}

OUTGOING JSON:

{
    "type": "receive",
    "img": "<BASE-64 ENCODED PNG DATA>",
    "message": "<250 CHAR OR LESS UTF-8 MESSAGE>"
}

{
    "type": "users",
    "count": <INT>
}
"""

import json
import logging
import websockets

from keytoimg import ipv8_ec25519_toimg


WS_USER = None
WS_CALLBACK = None
WS_EXIT_CALLBACK = None


def users_event(connection_count):
    return json.dumps({"type": "users", "count": connection_count})
    

def message_event(public_key_bin, message):
    return json.dumps({"type": "receive", "img": ipv8_ec25519_toimg(public_key_bin).decode(), "message": message})


async def init_stream(websocket, path):
    global WS_USER
    if WS_USER is not None:
        await websocket.close(1013, "Another user already connected to the backend!")  # "try again later" code :-)
        return
    WS_USER = websocket
    try:
        await websocket.send(users_event(0))
        async for message in websocket:
            if WS_CALLBACK:
                try:
                    data = json.loads(message)
                    if WS_CALLBACK is not None:
                        WS_CALLBACK(data)
                except Exception:
                    import traceback
                    traceback.print_exc()
                    logging.error("unsupported event: %s", data)
            
    finally:
        WS_USER = None
        if WS_EXIT_CALLBACK is not None:
            WS_EXIT_CALLBACK()


def create_server(on_ws_data=None, on_ws_exit=None, port=6789):
    global WS_CALLBACK, WS_EXIT_CALLBACK
    WS_CALLBACK = on_ws_data
    WS_EXIT_CALLBACK = on_ws_exit
    return websockets.serve(init_stream, "localhost", port)
    

async def send(server, event):
    if WS_USER is not None:
        await WS_USER.send(event)


__all__ = ["create_server", "message_event", "send", "users_event"]
