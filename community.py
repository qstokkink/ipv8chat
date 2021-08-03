from binascii import unhexlify
from collections import defaultdict

from pyipv8.ipv8.community import Community
from pyipv8.ipv8.keyvault.crypto import default_eccrypto
from pyipv8.ipv8.lazy_community import lazy_wrapper, lazy_wrapper_wd
from pyipv8.ipv8.messaging.lazy_payload import vp_compile, VariablePayload
from pyipv8.ipv8.messaging.payload_headers import BinMemberAuthenticationPayload
from pyipv8.ipv8.peer import Peer
from pyipv8.ipv8.peerdiscovery.network import Network


@vp_compile
class ChatMessage(VariablePayload):
    msg_id = 1
    names = ["message"]
    format_list = ["varlenH"]


@vp_compile
class FwdMessage(VariablePayload):
    msg_id = 2
    names = ["forwarded"]
    format_list = ["varlenH"]


class IPv8ChatCommunity(Community):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.message_callback = lambda public_key_bin, message: None
        self.fwd_map = defaultdict(set)

        self.add_message_handler(ChatMessage, self._on_message)
        self.add_message_handler(FwdMessage, self.on_fwd_message)

    async def unload(self):
        await super().unload()
        self.endpoint.close()

    def set_message_callback(self, callback):
        self.message_callback = callback

    def send_message(self, message: str):
        try:
            payload = ChatMessage(message[:250].encode())
            for peer in self.get_peers():
                self.ez_send(peer, payload)
        except:
            import traceback
            traceback.print_exc()
            self.logger.error("Failed to send message!")

    def fwd_message(self, data):
        msg_sig = data[-32:]
        fwd_group = set(self.get_peers()) - self.fwd_map[msg_sig]

        for peer in fwd_group:
            fwd = self.fwd_map[msg_sig]
            fwd.add(peer)
            self.fwd_map[msg_sig] = fwd

            self.ez_send(peer, FwdMessage(data))

    def on_message(self, peer_pk, payload, data):
        message = payload.message.decode()
        msg_sig = data[-32:]

        if msg_sig not in self.fwd_map:
            self.message_callback(peer_pk, message)

        self.fwd_message(data)

    @lazy_wrapper_wd(ChatMessage)
    def _on_message(self, peer, payload, data):
        self.on_message(peer.public_key.key_to_bin(), payload, data)

    @lazy_wrapper(FwdMessage)
    def on_fwd_message(self, peer, payload):
        auth, _ = self.serializer.unpack_serializable(BinMemberAuthenticationPayload, payload.forwarded, offset=23)
        signature_valid, remainder = self._verify_signature(auth, payload.forwarded)
        fwdpayload, = self.serializer.unpack_serializable_list([ChatMessage], remainder, offset=23)

        self.on_message(auth.public_key_bin, fwdpayload, payload.forwarded)

    def send_ping(self, peer):
        self.send_introduction_request(peer)


async def produce_community(ipv8, prefix):
    assert isinstance(prefix, str)
    assert len(prefix) == 40

    b_prefix = unhexlify(prefix)

    my_peer = Peer(default_eccrypto.generate_key("curve25519"))
    endpoint = await ipv8.produce_anonymized_endpoint()
    community_instance = type("IPv8ChatCommunity-%s" % prefix, (IPv8ChatCommunity, ), {"community_id": b_prefix})
    return community_instance(my_peer, endpoint, Network(), max_peers=200, anonymize=True)
