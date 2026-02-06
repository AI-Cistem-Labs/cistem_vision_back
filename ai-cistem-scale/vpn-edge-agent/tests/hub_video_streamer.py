import gi
gi.require_version("Gst", "1.0")
gi.require_version("GstRtspServer", "1.0")
from gi.repository import Gst, GstRtspServer, GLib

Gst.init(None)

server = GstRtspServer.RTSPServer()
server.set_address("0.0.0.0")
server.set_service("8554")

mounts = server.get_mount_points()

factory = GstRtspServer.RTSPMediaFactory()
factory.set_launch(
    "( v4l2src device=/dev/video0 ! "
    "videoconvert ! video/x-raw,width=640,height=480,framerate=30/1 ! "
    "x264enc tune=zerolatency speed-preset=ultrafast bitrate=800 key-int-max=30 ! "
    "rtph264pay name=pay0 pt=96 )"
)

factory.set_shared(True)

mounts.add_factory("/stream", factory)
server.attach(None)

print("RTSP activo en rtsp://<IP>:8554/stream")
GLib.MainLoop().run()