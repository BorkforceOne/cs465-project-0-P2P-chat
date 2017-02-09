import socket # Import socket module
from threading import Thread

MSGLEN = 1024

class Peer(Thread):

    def __init__(self, socket=None):
        Thread.__init__(self)
        print("Client connected!")
        self.socket = socket

        self.recieve_messages()

    def recieve_messages(self):
        chunks = []
        bytes_recd = 0
        while bytes_recd < MSGLEN:
            chunk = self.sock.recv(min(MSGLEN - bytes_recd, 2048))
            if chunk == b'':
                raise RuntimeError("socket connection broken")
            chunks.append(chunk)
            bytes_recd = bytes_recd + len(chunk)
        return b''.join(chunks)

    def send_text(self, text):

        self.socket.send()


class Client:

    def __init__(self, port=8080):
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.port = int(port)
        self.peers = []
        self.guid = "asd"
        self.name = "Brandon"

        listen_thread = Thread(None, self.listen)
        interact_thread = Thread(None, self.interact)

        listen_thread.start()
        interact_thread.start()

    def interact(self):
        print("Interaction")

    def listen(self):
        print("[INFO] Listening for new peers on port " + str(self.port) + "...")

        self.listening_socket.bind((socket.gethostname(), self.port))
        self.listening_socket.listen(5)

        while True:
            # accept connections from outside
            (peer_socket, address) = self.listening_socket.accept()
            # now do something with the clientsocket
            # in this case, we'll pretend this is a threaded server

            peer = Peer(peer_socket)
            peer.start()
            self.peers.append(peer)

print("====Super Awesome P2P Chat For Super Awesome People (SAP2PCFSAP for short)====")

port = input("Listen port: ")

Client(port)