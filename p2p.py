import socket
import uuid
import struct
from threading import Thread

MSGLEN = 1024

MSG_JOIN_NETWORK = 0X01
MSG_ACKNOWLEDGE_JOIN = 0X01
MSG_PEER = 0X02
MSG_LEAVE = 0X03
MSG_CHAT_MESSAGE = 0X04
MSG_PEER_REQUEST = 0X05
MSG_PEER_LIST = 0X06

MSG_HEADER_LEN = 4
MSG_BUFFER_SIZE = 2048

peers = []
client = None

def safe_recv(socket, bytes_to_read):
    data = socket.recv(bytes_to_read)

    if data == b'':
        raise RuntimeError("socket connection broken")

    return data

def unpack_helper(fmt, data):
    size = struct.calcsize(fmt)
    return struct.unpack(fmt, data[:size]), data[size:]

class Peer(Thread):

    def __init__(self, socket, name=None):
        Thread.__init__(self)
        print("[INFO] Peer created")

        self.name = name
        self.socket = socket

    def run(self):
        self.receive()

    def receive(self):
        while True:
            data = ''
            msg_len = safe_recv(self.socket, MSG_HEADER_LEN)
            msg_len = struct.unpack('<I', msg_len)[0]

            read_len = 0
            while read_len < msg_len:
                chunk = safe_recv(self.socket, MSG_BUFFER_SIZE)
                if not chunk:
                    break
                data += chunk
                read_len += len(chunk)

            while data != "":
                ((message_id), data) = unpack_helper('<B', data)
                message_id = message_id[0]

                if message_id == MSG_CHAT_MESSAGE:
                    # Read all data for this message
                    ((chat_len), data) = unpack_helper('<I', data)
                    chat_len = chat_len[0]
                    ((message), data) = unpack_helper('<%ds' % chat_len, data)
                    message = message[0]
                    print("[CHAT] %s says: %s" % (self.name, message))

                elif message_id == MSG_JOIN_NETWORK:
                    ((host_len), data) = unpack_helper('<I', data)
                    host_len = host_len[0]
                    ((host), data) = unpack_helper('<%ds' % host_len, data)
                    self.host = host[0]

                    ((port), data) = unpack_helper('<h', data)
                    self.port = port[0]

                    ((name_len), data) = unpack_helper('<I', data)
                    name_len = name_len[0]
                    ((name), data) = unpack_helper('<%ds' % name_len, data)
                    self.name = name[0]

                    #((guid), data) = unpack_helper('q', data)
                    #guid = guid[0]

                elif message_id == MSG_PEER_REQUEST:
                    packet = struct.pack("<BI", MSG_PEER_LIST, len(peers) - 1)
                    for peer in peers:
                        if peer == self:
                            continue
                        packet += peer.serialize()
                    self.send(packet)

                elif message_id == MSG_PEER_LIST:
                    ((peers_len), data) = unpack_helper('<I', data)
                    peers_len = peers_len[0]
                    for i in range(peers_len):
                        # Connect to each peer identified

                        ((host_len), data) = unpack_helper('<I', data)
                        host_len = host_len[0]
                        ((host), data) = unpack_helper('<%ds' % host_len, data)
                        host = host[0]

                        ((port), data) = unpack_helper('<h', data)
                        port = port[0]

                        ((name_len), data) = unpack_helper('<I', data)
                        name_len = name_len[0]
                        ((name), data) = unpack_helper('<%ds' % name_len, data)
                        name = name[0]

                        peer_socket = socket.socket()
                        peer_socket.connect((host, port))

                        peer = Peer(peer_socket, name)

                        packet = struct.pack("<BI%dshI%ds" % (len(client.host), len(client.name)), MSG_JOIN_NETWORK,
                                             len(client.host), client.host, client.port, len(client.name), client.name)
                        peer.send(packet)

                        peers.append(peer)
                        peer.start()

                if data != "":
                    (nothing, data) = unpack_helper('<I', data)

    def send(self, packed):
        packed = struct.pack('<I', len(packed)) + packed
        totalsent = 0
        while totalsent < len(packed):
            sent = self.socket.send(packed[totalsent:])
            if sent == 0:
                raise RuntimeError("socket connection broken")
            totalsent += sent

    def serialize(self):
        return struct.pack("<I%dshI%ds" % (len(self.host), len(self.name)), len(self.host), self.host, self.port, len(self.name), self.name)


class Client:

    def __init__(self):
        port = raw_input("Listen port: ")
        if (port == ""):
            port = 8080
        else:
            port = int(port)

        name = raw_input("Enter your name: ")

        self.uuid = uuid.uuid1()
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.port = port
        self.host = '127.0.0.1'
        self.guid = self.uuid.int
        self.name = name

        listen_thread = Thread(None, self.listen)
        interact_thread = Thread(None, self.interact)

        interact_thread.start()
        listen_thread.start()

    def interact(self):
        while True:
            command = raw_input("> ")
            if command == '':
                continue
            command = command.split(' ')

            if command[0] == 'connect':
                # Do connection here
                details = command[1].split(':')
                host = details[0]
                port = int(details[1])

                peer_socket = socket.socket()
                peer_socket.connect((host, port))

                peer = Peer(peer_socket)

                peers.append(peer)
                peer.start()

                packet = struct.pack("<BI%dshI%ds" % (len(self.host), len(self.name)), MSG_JOIN_NETWORK, len(self.host), self.host, self.port, len(self.name), self.name)
                peer.send(packet)

                packet = struct.pack("<B", MSG_PEER_REQUEST)
                peer.send(packet)
                continue

            elif command[0] == 'say':
                str = ' '.join(command[1:])
                packed = struct.pack("<BI%ds" % len(str), MSG_CHAT_MESSAGE, len(str), str)
                for peer in peers:
                    peer.send(packed)
                # Do chat message
                continue

            elif command[0] == 'exit':
                exit()
                continue

    def listen(self):
        print("[INFO] Listening for new peers on port " + str(self.port) + "...")

        self.listening_socket.bind((self.host, self.port))
        self.listening_socket.listen(5)

        while True:
            # accept connections from outside
            (peer_socket, address) = self.listening_socket.accept()
            # now do something with the clientsocket
            # in this case, we'll pretend this is a threaded server

            peer = Peer(peer_socket)
            peers.append(peer)
            peer.start()

print("====Super Awesome P2P Chat For Super Awesome People (SAP2PCFSAP for short)====")

client = Client()