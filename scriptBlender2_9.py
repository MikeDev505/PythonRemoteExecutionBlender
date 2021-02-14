import bpy
import json
import socket
import select


# RazerConnection is an operator that
class RemoteExecutionHubConnection(bpy.types.Operator):
    bl_idname = 'wm.remote_hub'
    bl_label = 'Remote Execution Hub'

    timer = None
    port = 56789
    serverSocket = None
    readReadySockets = None

    def modal(self, context, event):

        # Update the object with the received data.
        if event.type == 'TIMER':
            inputready, outputready, exceptready = select.select(self.readReadySockets, [], [], 0)
            for s in inputready:
                if s is self.serverSocket:
                    client_socket, address = self.serverSocket.accept()
                    self.readReadySockets.append(client_socket)
                    print(address)
                else:
                    try:
                        data = s.recv(1024)
                        commandString = data.decode('utf-8')
                        print("Commmand: ", commandString)
                        scriptResultString = self.executeScript(commandString)
                        print("scriptResultString: ", scriptResultString)
                        response = scriptResultString.encode('utf-8')
                        s.send(response)
                    finally:
                        s.close()
                        self.readReadySockets.remove(s)

            # bpy.data.objects['cube'].location = self.thread.data[:2]
            # bpy.data.objects['cube'].rotation_quaternion = self.thread.data[3:]

        return {'PASS_THROUGH'}

    def executeScript(self, commandString):
        loc = {}
        exec(commandString, globals(), loc)
        scriptResult = loc['scriptResult']
        return scriptResult


    def execute(self, context):
        print("test")
        # create udp socket
        self.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serverSocket.bind(('localhost', self.port))
        self.readReadySockets = [self.serverSocket]
        self.serverSocket.listen(1)
        self.timer = context.window_manager.event_timer_add(0.5, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


def register():
    print("register")
    bpy.utils.register_class(RemoteExecutionHubConnection)
    print("registered")

def unregister():
    bpy.utils.unregister_class(RemoteExecutionHubConnection)

if __name__ == "__main__":
    register()

print("Invoke")
bpy.ops.wm.remote_hub()
print("Invoked")
