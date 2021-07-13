import logging
from asyncio import ensure_future, get_event_loop
from time import time
from sys import argv

from pyipv8.ipv8.bootstrapping.dispersy.bootstrapper import DispersyBootstrapper
from pyipv8.ipv8.bootstrapping.udpbroadcast.bootstrapper import UDPBroadcastBootstrapper
from pyipv8.ipv8.configuration import ConfigBuilder, DISPERSY_BOOTSTRAPPER
from pyipv8.ipv8.peerdiscovery.churn import RandomChurn
from pyipv8.ipv8.peerdiscovery.discovery import RandomWalk, DiscoveryStrategy

from pyipv8.ipv8_service import IPv8

from community import produce_community, IPv8ChatCommunity
from ws_server import create_server, message_event, send, users_event


class PollPeers(DiscoveryStrategy):

    def __init__(self, overlay, ws_server):
        super(PollPeers, self).__init__(overlay)
        self.ws_server = ws_server
        self.last_check = 0

    def take_step(self):
        with self.walk_lock:
            if time()-self.last_check > 5.0:
                self.last_check = time()
                ensure_future(send(self.ws_server, users_event(len(self.overlay.get_peers()))))


class WSIPv8(IPv8):

    def __init__(self, *args, **kwargs):
        port = kwargs.pop("wsport", 6789)
        super().__init__(*args, **kwargs)

        self.ws_server = create_server(self.on_ws_data, self.on_ws_exit, port)

    def send_ws_message(self, pk, data):
        ensure_future(send(self.ws_server, message_event(pk, data)))

    async def _join_community(self, data):
        community = await produce_community(self, data["communityid"])
        community.set_message_callback(self.send_ws_message)
        community.bootstrappers = [
            DispersyBootstrapper(**DISPERSY_BOOTSTRAPPER["init"]),
            UDPBroadcastBootstrapper()
        ]
        community.bootstrap()
        self.add_strategy(community, RandomWalk(community), 200)
        self.add_strategy(community, RandomChurn(community), -1)
        self.add_strategy(community, PollPeers(community, self.ws_server), -1)

    def on_ws_data(self, data):
        action = data.get("action")
        if action == "join":
            self.on_ws_exit()
            ensure_future(self._join_community(data))
        elif action == "send":
            overlay = self.get_overlay(IPv8ChatCommunity)
            if overlay:
                overlay.send_message(data["message"])
            else:
                logging.error("Attempt to send message without being part of an overlay.")
        else:
            print("Dropping garbage data", data)

    def on_ws_exit(self):
        for overlay in self.overlays[:]:
            ensure_future(self.unload_overlay(overlay))


def create_ipv8():
    builder = ConfigBuilder().clear_keys().clear_overlays()
    builder.set_address("0.0.0.0")
    kwargs = {}
    if len(argv) > 1:
        kwargs["wsport"] = int(argv[1])
    ipv8 = WSIPv8(builder.finalize(), **kwargs)
    return ipv8


ipv8 = create_ipv8()
get_event_loop().run_until_complete(ipv8.ws_server)
ensure_future(ipv8.start())
get_event_loop().run_forever()
