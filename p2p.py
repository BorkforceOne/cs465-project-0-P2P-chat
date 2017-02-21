import socket
import struct
import uuid
import errno
import time
from threading import Thread, Lock, Event

MSGLEN = 1024

MSG_JOIN_NETWORK = 0X01
MSG_PEER = 0X02
MSG_LEAVE = 0X03
MSG_CHAT_MESSAGE = 0X04
MSG_PEER_REQUEST = 0X05
MSG_PEER_LIST = 0X06
MSG_ACKNOWLEDGE_JOIN = 0X07
MSG_JOIN_CHAT = 0X08
MSG_PEER_LIST_SYNC = 0X09

MSG_HEADER_LEN = 4
MSG_BUFFER_SIZE = 2048

peers = {}
peers_lock = Lock()


def add_peer(guid, hostname, port, name, instance=None, do_lock=True):
    peer = {
        'hostname': hostname,
        'port': port,
        'name': name,
        'instance': instance
    }

    if do_lock:
        peers_lock.acquire()

    try:
        peers[guid] = peer

    finally:
        if do_lock:
            peers_lock.release()


def safe_recv(sock, bytes_to_read):
    data = sock.recv(bytes_to_read)

    if data == b'':
        raise RuntimeError("socket connection broken")

    return data


def serialize_peers(do_lock=True):
    serialized_peers = ""

    if do_lock:
        peers_lock.acquire()

    try:
        for guid in peers:
            serialized_peers += serialize_peer(guid, False)

    finally:
        if do_lock:
            peers_lock.release()

    return serialized_peers


def serialize_peer(guid, do_lock=True):
    if do_lock:
        peers_lock.acquire()

    try:
        peer = peers[guid]
        serialized_peer = struct.pack("<I%dsI%dsI%dsh" % (len(guid), len(peer['hostname']), len(peer['name'])),
                                      len(guid), guid, len(peer['hostname']), peer['hostname'], len(peer['name']),
                                      peer['name'], peer['port'])

    finally:
        if do_lock:
            peers_lock.release()

    return serialized_peer


def unpack_helper(fmt, data):
    size = struct.calcsize(fmt)
    return struct.unpack(fmt, data[:size]), data[size:]


class StoppableThread(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.stop_event = Event()

    def stop(self):
        if self.isAlive():
            # set event to signal thread to terminate
            self.stop_event.set()
            # block calling thread until thread really has terminated
            self.join()


class Peer(StoppableThread):

    def __init__(self, sock, guid=None, name=None):
        StoppableThread.__init__(self)

        self.sock = sock
        self.guid = guid
        self.name = name

        self.sock.setblocking(False)

    def run(self):
        while self.stop_event.is_set() == False:
            data = ''
            msg_len = 0
            while self.stop_event.is_set() == False:
                try:
                    msg_len = safe_recv(self.sock, MSG_HEADER_LEN)
                    break
                except socket.error as (sock_errno, sock_errstr):
                    if sock_errno == errno.EWOULDBLOCK:
                        # socket would block - sleep sometime
                        time.sleep(0.1)
                    else:
                        self.stop_event.set()
                        break
                except:
                    self.stop_event.set()
                    break

            if self.stop_event.is_set():
                continue

            msg_len = struct.unpack('<I', msg_len)[0]

            read_len = 0
            while read_len < msg_len:
                chunk = None

                while self.stop_event.is_set() == False:
                    try:
                        chunk = safe_recv(self.sock, MSG_BUFFER_SIZE)
                        break
                    except socket.error as (sock_errno, sock_errstr):
                        if sock_errno == errno.EWOULDBLOCK:
                            # socket would block - sleep sometime
                            time.sleep(0.1)
                        else:
                            self.stop_event.set()
                            break
                    except:
                        self.stop_event.set()
                        break

                if self.stop_event.is_set():
                    break

                if not chunk:
                    break
                data += chunk
                read_len += len(chunk)

            if self.stop_event.is_set():
                continue

            while data != "":
                ((message_id,), data) = unpack_helper('<B', data)

                if message_id == MSG_LEAVE:
                    print("[CHAT] %s has left the chat" % self.name)
                    peers_lock.acquire()

                    try:
                        del peers[self.guid]

                    finally:
                        peers_lock.release()

                elif message_id == MSG_CHAT_MESSAGE:
                    # Read all data for this message
                    ((chat_len,), data) = unpack_helper('<I', data)
                    ((message,), data) = unpack_helper('<%ds' % chat_len, data)
                    print("[CHAT] %s says: %s" % (self.name, message))

                elif message_id == MSG_JOIN_NETWORK:
                    ((guid_len,), data) = unpack_helper('<I', data)
                    ((guid,), data) = unpack_helper('<%ds' % guid_len, data)
                    ((hostname_len,), data) = unpack_helper('<I', data)
                    ((hostname,), data) = unpack_helper('<%ds' % hostname_len, data)
                    ((name_len,), data) = unpack_helper('<I', data)
                    ((name,), data) = unpack_helper('<%ds' % name_len, data)
                    ((port,), data) = unpack_helper('<h', data)

                    self.guid = guid
                    self.name = name

                    add_peer(guid, hostname, port, name, self)

                    print("[INFO] %s has connected" % name)

                    packet = struct.pack("<BI%ds" % len(my_guid), MSG_ACKNOWLEDGE_JOIN, len(my_guid), my_guid)
                    self.send(packet)

                elif message_id == MSG_JOIN_CHAT:
                    ((guid_len,), data) = unpack_helper('<I', data)
                    ((guid,), data) = unpack_helper('<%ds' % guid_len, data)
                    ((hostname_len,), data) = unpack_helper('<I', data)
                    ((hostname,), data) = unpack_helper('<%ds' % hostname_len, data)
                    ((name_len,), data) = unpack_helper('<I', data)
                    ((name,), data) = unpack_helper('<%ds' % name_len, data)
                    ((port,), data) = unpack_helper('<h', data)

                    self.guid = guid
                    self.name = name

                    add_peer(guid, hostname, port, name, self)

                    print("[INFO] %s has connected" % name)

                elif message_id == MSG_PEER_REQUEST:
                    packet = struct.pack("<BI", MSG_PEER_LIST, len(peers))
                    packet += serialize_peers()
                    self.send(packet)

                elif message_id == MSG_ACKNOWLEDGE_JOIN:
                    ((guid_len,), data) = unpack_helper('<I', data)
                    ((self.guid,), data) = unpack_helper('<%ds' % guid_len, data)

                    # Request the peer list
                    packet = struct.pack("<B", MSG_PEER_REQUEST)
                    self.send(packet)

                elif message_id == MSG_PEER_LIST:

                    peers_lock.acquire()

                    try:
                        ((peers_len,), data) = unpack_helper('<I', data)
                        for i in range(peers_len):
                            # Connect to each peer identified
                            ((guid_len,), data) = unpack_helper('<I', data)
                            ((guid,), data) = unpack_helper('<%ds' % guid_len, data)
                            ((hostname_len,), data) = unpack_helper('<I', data)
                            ((hostname,), data) = unpack_helper('<%ds' % hostname_len, data)
                            ((name_len,), data) = unpack_helper('<I', data)
                            ((name,), data) = unpack_helper('<%ds' % name_len, data)
                            ((port,), data) = unpack_helper('<h', data)

                            peer_instance = None

                            if guid in peers:
                                continue
                            if guid == self.guid:
                                peer_instance = self
                                self.name = name
                            else:
                                peer_socket = socket.socket()
                                peer_socket.connect((hostname, port))

                                peer_instance = Peer(peer_socket, guid, name)
                                peer_instance.start()

                                packet = struct.pack("<B", MSG_JOIN_CHAT)
                                packet += serialize_peer(my_guid, False)
                                peer_instance.send(packet)

                            print("[INFO] Connected to %s at %s:%d" % (name, hostname, port))

                            add_peer(guid, hostname, port, name, peer_instance, False)

                    finally:
                        peers_lock.release()

                if data != "":
                    ((msg_len,), data) = unpack_helper('<I', data)

        self.sock.close()

    def send_leave(self):
        packet = struct.pack("<B", MSG_LEAVE)
        self.send(packet)
        self.stop_event.is_set()

    def send(self, packed):
        packed = struct.pack('<I', len(packed)) + packed
        totalsent = 0
        while totalsent < len(packed):
            sent = self.sock.send(packed[totalsent:])
            if sent == 0:
                raise RuntimeError("socket connection broken")
            totalsent += sent

class Listen(StoppableThread):
    def __init__(self, hostname, port):
        StoppableThread.__init__(self)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.hostname = hostname
        self.port = port

    def run(self):
        print("[INFO] Listening for new peers on port " + str(my_port) + "...")

        self.sock.bind(('', my_port))
        self.sock.listen(5)
        self.sock.settimeout(0.01)

        while self.stop_event.is_set() == False:
            try:
                (peer_socket, address) = self.sock.accept()
                peer = Peer(peer_socket)
                peer.start()
            except socket.timeout:
                if self.stop_event.isSet():
                    removed = []
                    peers_lock.acquire()

                    for guid, peer in peers.iteritems():
                        if peer['instance'] is not None:
                            peer['instance'].stop()
                            removed.append(guid)

                    for guid in removed:
                        del peers[guid]

                    peers_lock.release()


def interact():
    while True:
        command = raw_input("> ")
        if command == '':
            continue
        command = command.split(' ')

        if command[0] == 'connect':

            peers_lock.acquire()

            # Do connection here
            details = command[1].split(':')
            host = details[0]
            port = int(details[1])

            peer_socket = socket.socket()
            peer_socket.connect((host, port))

            peer_instance = Peer(peer_socket)

            peer_instance.start()

            # Tell them about ourselves
            packet = struct.pack("<B", MSG_JOIN_NETWORK)
            packet += serialize_peer(my_guid, False)
            peer_instance.send(packet)

            packet = struct.pack("<BI", MSG_PEER_LIST, len(peers))
            packet += serialize_peers(False)
            peer_instance.send(packet)

            peers_lock.release()

        elif command[0] == 'say':
            chat_message = ' '.join(command[1:])
            packet = struct.pack("<BI%ds" % len(chat_message), MSG_CHAT_MESSAGE, len(chat_message), chat_message)

            peers_lock.acquire()

            try:
                for guid in peers:
                    peer = peers[guid]
                    if peer['instance'] is not None:
                        peer['instance'].send(packet)

            finally:
                peers_lock.release()

            # Do chat message
            print("[CHAT] %s says: %s" % (my_name, chat_message))

        elif command[0] == 'peers':
            for peer_instance in peers:
                print(peer_instance)

        elif command[0] == 'exit':
            peers_lock.acquire()

            try:
                for guid in peers:
                    peer = peers[guid]
                    if peer['instance'] is None:
                        continue

                    peer['instance'].send_leave()
                    peer['instance'].stop()

            finally:
                peers_lock.release()

            listen_thread.stop()

            break

print("====Super Awesome P2P Chat For Super Awesome People (SAP2PCFSAP for short)====")

my_guid = str(uuid.uuid1())
my_hostname = '127.0.0.1'
my_port = raw_input("Listen port: ")

if my_port == "":
    my_port = 8080
else:
    my_port = int(my_port)

my_name = raw_input("Enter your name: ")

add_peer(my_guid, my_hostname, my_port, my_name)

listen_thread = Listen(my_hostname, my_port)
listen_thread.start()

interact()

print("Exiting...")