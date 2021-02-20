# RemoteExecutionHubClient ver 2.0.0
import bpy
import struct
import threading
import time
import json
import socket
import sys
import select
import mathutils
import math


#Stuktura opisująca konfig
class RemoteExecutionConfig:
    def __init__(self):
        self.clientName = "blender"
        self.clientId = "wersdf234"

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__,
                          sort_keys=True, indent=4)


class RemoteExecutionHubClientThread(threading.Thread):
    data = None
    running = False

    def __init__(self):
        threading.Thread.__init__(self)
        self.server_address = ('localhost', 56788)
        self.config = RemoteExecutionConfig()
        self.clientSocket = self.create_socket()
        self.script_request = ''
        self.script_response = None

    @staticmethod
    def create_socket():
        return socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def start(self):

        # Start the thread.
        print('Starting RemoteExecutionHubClient thread')
        self.running = True
        threading.Thread.start(self)

    def stop(self):

        # Stop the thread.
        print('Stopping RemoteExecutionHubClient thread')
        self.running = False

    @staticmethod
    def log(messsage):
        print(messsage)

    def run(self):

        while self.running:
            try:
                # Setup the network socket.
                self.log('lacze sie z hubem/serwerem')
                self.connect()
                self.log('polaczylem sie')
                # Receive new data from the client.
                while self.running:
                    self.log('czekam na requesta')
                    self.script_response = None
                    self.script_request = self.recv_string()
                    self.log('czekam na responsa')
                    while self.script_response is None:
                        time.sleep(0.05)
                    self.log('wysylam responsa')
                    self.send_string(self.script_response)
                    self.log('wyslalem responsa')
            except:
                print("Unexpected error:", sys.exc_info()[0])
                self.log('blad - czekam chwile i ponownie lacze')
                time.sleep(10)
                self.clientSocket = self.create_socket()

    def connect(self):
        self.clientSocket.connect(self.server_address)  # łączę się z serwerem
        self.send_string(self.config.toJSON())  # wysyłam przywitanie

    def send_string(self, message):
        buf = bytes(message, "utf-8")
        print("send_string: " + message)
        self.send_bytes(buf)

    def send_bytes(self, msg):
        # Prefix each message with a 4-byte length (network byte order)
        new_message = struct.pack('<I', len(msg)) + msg
        #print("send_bytes: " + new_message)
        self.clientSocket.sendall(new_message)

    def recv_string(self):
        bytesBuffor = self.recv_bytes()
        return bytesBuffor.decode('utf-8')

    def recv_bytes(self):
        # Read message length and unpack it into an integer
        raw_msglen = self.recv_all_bytes(4)
        if not raw_msglen:
            return None
        msglen = struct.unpack('<I', raw_msglen)[0]
        # Read the message data
        return self.recv_all_bytes(msglen)

    def recv_all_bytes(self, n):
        # Helper function to recv n bytes or return None if EOF is hit
        data = bytearray()
        while len(data) < n:
            packet = self.clientSocket.recv(n - len(data))
            if not packet:
                return None
            data.extend(packet)
        return data


# RemoteExecutionHubConnection is an operator that
class RemoteExecutionHubConnection(bpy.types.Operator):

    def __init__(self):
        self.remoteExecutionHubClientThread = RemoteExecutionHubClientThread()

    bl_idname = 'wm.remote_hub'
    bl_label = 'Remote Execution Hub'
    timer = None

    def modal(self, context, event):

        # Stop the thread when ESCAPE is pressed.
        if event.type == 'ESC':
            self.remoteExecutionHubClientThread.stop()
            self.remoteExecutionHubClientThread.running = False
            context.window_manager.event_timer_remove(self.timer)
            return {'CANCELLED'}

        # Update the object with the received data.
        if event.type == 'TIMER':
            if self.remoteExecutionHubClientThread.script_request is not None:
                script_request = self.remoteExecutionHubClientThread.script_request
                self.remoteExecutionHubClientThread.script_request = None
                print("Recived script")
                self.remoteExecutionHubClientThread.script_response = self.execute_script(script_request)
                print("executed script: " + self.remoteExecutionHubClientThread.script_response)
        return {'PASS_THROUGH'}

    def execute(self, context):
        print("start clienta")
        self.remoteExecutionHubClientThread.start()

        self.timer = context.window_manager.event_timer_add(0.02,  window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def execute_script(self, command_string):
        try:
            loc = {}
            exec(command_string, globals(), loc)
            script_result = loc['scriptResult']
            return script_result
        except:
            return ""
            pass

def register():
    print("register")
    bpy.utils.register_class(RemoteExecutionHubConnection)
    print("registered")

def unregister():
    bpy.utils.unregister_class(RemoteExecutionHubConnection)

register()

print("Invoke")
bpy.ops.wm.remote_hub()
print("Invoked")
