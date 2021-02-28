# RemoteExecutionHubClient ver 2.1.1
import bpy
import struct
import threading
import time
import json
import socket
import sys
import array
import numpy as np
import select
import mathutils
import math


# Stuktura opisująca konfig
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
        self.log('Starting RemoteExecutionHubClient thread')
        self.running = True
        threading.Thread.start(self)

    def stop(self):

        # Stop the thread.
        self.log('Stopping RemoteExecutionHubClient thread')
        self.running = False

    @staticmethod
    def log(messsage):
        # print(messsage)
        return

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
        self.send_bytes(buf)

    def send_bytes(self, msg):
        # Prefix each message with a 4-byte length (network byte order)
        new_message = struct.pack('<I', len(msg)) + msg
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

    @staticmethod
    def log(messsage):
        # print(messsage)
        return

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
                self.log("Recived script")
                self.remoteExecutionHubClientThread.script_response = self.execute_script(script_request)
                self.log("executed script: " + self.remoteExecutionHubClientThread.script_response)
        return {'PASS_THROUGH'}

    def execute(self, context):
        print("start clienta")
        self.remoteExecutionHubClientThread.start()

        self.timer = context.window_manager.event_timer_add(0.02, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def execute_script(self, command_string):
        try:
            loc = {}
            print('cmd: ' + command_string)
            exec(command_string, globals(), loc)
            script_result = loc['scriptResult']
            return script_result
        except:
            print(sys.exc_info()[0])
            return repr(sys.exc_info()[0])
            pass


def register():
    print("register")
    bpy.utils.register_class(RemoteExecutionHubConnection)
    print("registered")


def unregister():
    bpy.utils.unregister_class(RemoteExecutionHubConnection)


########################################################


# plugin Rigify
class RigifyController:
    def __init__(self, armatureName):
        self.armature = bpy.data.objects[armatureName]

        bone_names_hand_l = ['hand_ik.L', 'thumb.01_master.L', 'f_index.01_master.L', 'f_middle.01_master.L',
                             'f_ring.01_master.L', 'f_pinky.01_master.L']
        bone_names_hand_r = ['hand_ik.R', 'thumb.01_master.R', 'f_index.01_master.R', 'f_middle.01_master.R',
                             'f_ring.01_master.R', 'f_pinky.01_master.R']
        self.handBones_l = self.get_hand_bones(self.armature, bone_names_hand_l)
        self.handBones_r = self.get_hand_bones(self.armature, bone_names_hand_r)
        self.bone_position = {}
        self.bone_rotation = {}
        self.is_recording = False
        self.set_bone_rotation_mode(['head', 'chest', 'foot_ik.R', 'foot_ik.L'] + bone_names_hand_l + bone_names_hand_r)

    # kontroler do poruszania palcem - zamykanie i na boki
    def finger_control(self, finger_close, finger_rot, poseBone):
        poseBone.scale.y = np.interp(finger_close, [-1, 0, 1], [0.5, 0.9, 1.05])  # zamykanie palca
        poseBone.rotation_euler.x = np.interp(finger_close, [-1, 0, 1], [.9, 0, -.1])  # zamykanie palca
        poseBone.rotation_euler.z = np.interp(finger_rot, [-1, 1], [.3, -.3])  # poruszanie na boki
        self.insert_keyframe_rotation_if_recording(poseBone)
        self.insert_keyframe_scale_if_recording(poseBone)
        return

    # kontroler do ustawiania pozycji 2D ręki (otwarta/zamknięta, zciśnięta/rozwarta)
    def hand_control(self, finger_close, finger_rot, fingersPostBone):
        self.finger_control(np.interp(finger_close, [-1, 1], [-.4, .5]), np.interp(finger_rot, [-1, 1], [-1, 1]),
                            fingersPostBone[0])
        self.finger_control(finger_close, np.interp(finger_rot, [-1, 1], [-1, 1]), fingersPostBone[1])
        self.finger_control(finger_close, np.interp(finger_rot, [-1, 1], [-.5, .5]), fingersPostBone[2])
        self.finger_control(finger_close, np.interp(finger_rot, [-1, 1], [.5, -.5]), fingersPostBone[3])
        self.finger_control(finger_close, np.interp(finger_rot, [-1, 1], [1, -1]), fingersPostBone[4])

    @staticmethod
    def get_hand_bones(armature, bonesNames):
        bones = []
        for boneName in bonesNames:
            bones.append(armature.pose.bones.get(boneName))
        return bones

    def set_bone_rotation_mode(self, boneNames):
        for boneName in boneNames:
            bp = self.armature.pose.bones.get(boneName)
            bp.rotation_mode = 'XYZ'

    # kontrola 2d gestu ręki(otwarta/zamknięta, zciśnięta/rozwarta)
    def hand_l(self, finger_close, finger_rot):
        self.hand_control(finger_close, finger_rot, self.handBones_l[1:])

    # kontrola 2d gestu ręki(otwarta/zamknięta, zciśnięta/rozwarta)
    def hand_r(self, finger_close, finger_rot):
        self.hand_control(finger_close, finger_rot, self.handBones_r[1:])

    # zapisuje pozycję kości
    def save_bone_position(self, bone_name):
        pb = self.armature.pose.bones.get(bone_name)
        mw = self.armature.convert_space(pose_bone=pb,
                                         matrix=pb.matrix,
                                         from_space='POSE',
                                         to_space='WORLD')

        self.bone_position[bone_name] = mw.translation

    # przywracam zapisaną pozycję kości
    def restore_bone_position(self, bone_name):
        self.set_bone_position(bone_name, self.bone_position[bone_name])

    # ustawiam pozycję kości
    def set_bone_position(self, bone_name, position):
        pb = self.armature.pose.bones.get(bone_name)
        mw = self.armature.convert_space(pose_bone=pb,
                                         matrix=pb.matrix,
                                         from_space='POSE',
                                         to_space='WORLD')
        mw.translation = position

        pb.matrix = self.armature.convert_space(pose_bone=pb,
                                                matrix=mw,
                                                from_space='WORLD',
                                                to_space='POSE')
        self.insert_keyframe_location_rotation_if_recording(pb)

    # przesówam kość o 'd_position' względem zapisanej pozycji
    def add_bone_position(self, bone_name, d_position):
        pb = self.armature.pose.bones.get(bone_name)
        old_position = self.bone_position[bone_name]
        new_position = (
            old_position[0] + d_position[0], old_position[1] + d_position[1], old_position[2] + d_position[2])
        self.set_bone_position(bone_name, new_position)

    # zapisuje rotacje kości
    def save_bone_rotation(self, bone_name):
        pb = self.armature.pose.bones.get(bone_name)
        self.bone_rotation[bone_name] = pb.rotation_euler.copy()

    def restore_bone_rotation(self, bone_name):
        pb = self.armature.pose.bones.get(bone_name)
        pb.rotation_euler = self.bone_rotation[bone_name]

    def set_bone_rotation(self, bone_name, rotation):
        pb = self.armature.pose.bones.get(bone_name)
        pb.rotation_euler = rotation
        self.insert_keyframe_rotation_if_recording(pb)

    def add_bone_rotation(self, bone_name, d_rotation):
        pb = self.armature.pose.bones.get(bone_name)
        old_rotation = self.bone_rotation[bone_name]
        new_rotation = (
            old_rotation[0] + d_rotation[0], old_rotation[1] + d_rotation[1], old_rotation[2] + d_rotation[2])
        self.set_bone_rotation(bone_name, new_rotation)

    def reset_bone_rotation(self, bone_name, x, y, z):
        pb = self.armature.pose.bones.get(bone_name)
        rotation = pb.rotation_euler.copy()
        if x:
            self.set_bone_rotation(bone_name, (0, rotation[1], rotation[2]))
        if y:
            self.set_bone_rotation(bone_name, (rotation[0], 0, rotation[2]))
        if z:
            self.set_bone_rotation(bone_name, (rotation[0], rotation[1], 0))

    def start_record(self):
        self.is_recording = True

    def stop_record(self):
        self.is_recording = False

    def toggle_record(self):
        self.is_recording = not self.is_recording
        return self.is_recording

    def insert_keyframe_location_rotation_if_recording(self, pose_bone):
        if self.is_recording:
            pose_bone.keyframe_insert(data_path='location')

    def insert_keyframe_rotation_if_recording(self, pose_bone):
        if self.is_recording:
            pose_bone.keyframe_insert(data_path='rotation_euler')

    def insert_keyframe_scale_if_recording(self, pose_bone):
        if self.is_recording:
            pose_bone.keyframe_insert(data_path='scale')

    def inc_frame(self):
        bpy.context.scene.frame_current += 30

    def dec_frame(self):
        bpy.context.scene.frame_current -= 30
        if bpy.context.scene.frame_current < 1:
            bpy.context.scene.frame_current = 1


rigifyControler = RigifyController('rig')

register()

print("Invoke")
bpy.ops.wm.remote_hub()
print("Invoked")
