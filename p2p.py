import socket
import uuid
import struct
from threading import Thread

MSGLEN = 1024

MSG_JOIN_NETWORK = 0X01
MSG_PEER = 0X02
MSG_LEAVE = 0X03
MSG_CHAT_MESSAGE = 0X04
MSG_PEER_REQUEST = 0X05
MSG_PEER_LIST = 0X06
MSG_ACKNOWLEDGE_JOIN = 0X07

MSG_HEADER_LEN = 4
MSG_BUFFER_SIZE = 2048

peers = []

def safe_recv(socket, bytes_to_read):
    data = socket.recv(bytes_to_read)

    if data == b'':
        raise RuntimeError("socket connection broken")

    return data

def unpack_helper(fmt, data):
    size = struct.calcsize(fmt)
    return struct.unpack(fmt, data[:size]), data[size:]

class Peer(Thread):

    def __init__(self, socket, name="", host="", port=-1):
        Thread.__init__(self)
        print("[INFO] Peer connecting...")

        self.name = name
        self.sock = socket
        self.host = host
        self.port = port

    def run(self):
        self.receive()

    def receive(self):
        is_running = True
        while is_running:
            data = ''
            try:
                msg_len = safe_recv(self.sock, MSG_HEADER_LEN)
            except socket.error:
                is_running = False
                break

            msg_len = struct.unpack('<I', msg_len)[0]

            read_len = 0
            while read_len < msg_len:
                try:
                    chunk = safe_recv(self.sock, MSG_BUFFER_SIZE)
                except socket.error:
                    is_running = False
                    break

                if not chunk:
                    break
                data += chunk
                read_len += len(chunk)

            while data != "":
                ((message_id,), data) = unpack_helper('<B', data)

                if message_id == MSG_LEAVE:
                    print("[CHAT] %s has left the chat", self.name)
                    peers.remove(self)
                    is_running = False

                if message_id == MSG_CHAT_MESSAGE:
                    # Read all data for this message
                    ((chat_len,), data) = unpack_helper('<I', data)
                    ((message,), data) = unpack_helper('<%ds' % chat_len, data)
                    print("[CHAT] %s says: %s" % (self.name, message))

                elif message_id == MSG_JOIN_NETWORK:
                    ((host_len,), data) = unpack_helper('<I', data)
                    ((self.host,), data) = unpack_helper('<%ds' % host_len, data)
                    ((self.port,), data) = unpack_helper('<h', data)
                    ((name_len,), data) = unpack_helper('<I', data)
                    ((self.name,), data) = unpack_helper('<%ds' % name_len, data)

                    print("[INFO] %s has connected" % self.name)

                    packet = struct.pack("<B", MSG_ACKNOWLEDGE_JOIN)
                    packet += serialize()
                    self.send(packet)

                elif message_id == MSG_PEER_REQUEST:
                    packet = struct.pack("<BI", MSG_PEER_LIST, len(peers) - 1)
                    for peer in peers:
                        if peer == self:
                            continue
                        packet += peer.serialize()
                    self.send(packet)

                elif message_id == MSG_ACKNOWLEDGE_JOIN:
                    ((host_len,), data) = unpack_helper('<I', data)
                    ((self.host,), data) = unpack_helper('<%ds' % host_len, data)
                    ((self.port,), data) = unpack_helper('<h', data)
                    ((name_len,), data) = unpack_helper('<I', data)
                    ((self.name,), data) = unpack_helper('<%ds' % name_len, data)

                    print("[INFO] Connected to %s at %s:%d" % (self.name, self.host, self.port))

                elif message_id == MSG_PEER_LIST:
                    ((peers_len,), data) = unpack_helper('<I', data)
                    for i in range(peers_len):
                        # Connect to each peer identified

                        ((host_len,), data) = unpack_helper('<I', data)
                        ((host,), data) = unpack_helper('<%ds' % host_len, data)
                        ((port,), data) = unpack_helper('<h', data)
                        ((name_len,), data) = unpack_helper('<I', data)
                        ((name,), data) = unpack_helper('<%ds' % name_len, data)

                        peer_socket = socket.socket()
                        peer_socket.connect((host, port))

                        peer = Peer(peer_socket, name, host, port)

                        packet = struct.pack("<BI%dshI%ds" % (len(my_hostname), len(my_name)), MSG_JOIN_NETWORK, len(my_hostname), my_hostname, my_port, len(my_name), my_name)
                        peer.send(packet)

                        print("[INFO] Connected to %s at %s:%d" % (name, host, port))

                        peers.append(peer)
                        peer.start()

                if data != "":
                    ((msg_len,), data) = unpack_helper('<I', data)

        self.sock.close()

    def send_leave(self):
        packet = struct.pack("<B", MSG_LEAVE)
        self.send(packet)
        self.sock.close()

    def send(self, packed):
        packed = struct.pack('<I', len(packed)) + packed
        totalsent = 0
        while totalsent < len(packed):
            sent = self.sock.send(packed[totalsent:])
            if sent == 0:
                raise RuntimeError("socket connection broken")
            totalsent += sent

    def serialize(self):
        return struct.pack("<I%dshI%ds" % (len(self.host), len(self.name)), len(self.host), self.host, self.port, len(self.name), self.name)

    def __str__(self):
        return "(%s:%d, %s)" % (self.host, self.port, self.name)


def interact():
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

            packet = struct.pack("<BI%dshI%ds" % (len(host), len(my_name)), MSG_JOIN_NETWORK, len(host), host, port, len(my_name), my_name)
            peer.send(packet)

            packet = struct.pack("<B", MSG_PEER_REQUEST)
            peer.send(packet)

        elif command[0] == 'say':
            str = ' '.join(command[1:])
            packet = struct.pack("<BI%ds" % len(str), MSG_CHAT_MESSAGE, len(str), str)
            for peer in peers:
                peer.send(packet)
            # Do chat message
            print("[CHAT] %s says: %s" % (my_name, str))

        elif command[0] == 'peers':
            for peer in peers:
                print(peer)

        elif command[0] == 'exit':
            for peer in peers:
                peer.send_leave()
            exit()


def listen():
    print("[INFO] Listening for new peers on port " + str(my_port) + "...")

    my_listening_socket.bind((my_hostname, my_port))
    my_listening_socket.listen(5)

    while True:
        # accept connections from outside
        (peer_socket, address) = my_listening_socket.accept()

        peer = Peer(peer_socket)
        peers.append(peer)
        peer.start()


def serialize():
    return struct.pack("<I%dshI%ds" % (len(my_hostname), len(my_name)), len(my_hostname), my_hostname, my_port, len(my_name), my_name)

print("====Super Awesome P2P Chat For Super Awesome People (SAP2PCFSAP for short)====")

my_hostname = '127.0.0.1'
my_port = raw_input("Listen port: ")

if my_port == "":
    my_port = 8080
else:
    my_port = int(my_port)

my_name = raw_input("Enter your name: ")

my_listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

listen_thread = Thread(None, listen)
interact_thread = Thread(None, interact)

interact_thread.start()
listen_thread.start()
