import asyncio
import threading
import time
import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst

Gst.init(None)

latest_frame = None
lock = threading.Lock()
capture_failed = threading.Event()


def capture():
    global latest_frame

    pipeline = Gst.parse_launch(
        "v4l2src device=/dev/video0  ! "
        "image/jpeg,width=1920,height=1080,framerate=10/1 ! "
        "appsink name=sink "
        "emit-signals=false "
        "sync=false "
        "max-buffers=1 "
        "drop=true"
    )

    sink = pipeline.get_by_name("sink")

    pipeline.set_state(Gst.State.PLAYING)

    bus = pipeline.get_bus()

    try:
        while True:
            # Handle pipeline errors/messages
            msg = bus.timed_pop_filtered(
                1000000,
                Gst.MessageType.ERROR
                | Gst.MessageType.EOS
                | Gst.MessageType.STATE_CHANGED,
            )

            if msg:
                t = msg.type

                if t == Gst.MessageType.ERROR:
                    err, debug = msg.parse_error()
                    print("GStreamer ERROR:", err, debug)
                    capture_failed.set()
                    return

                elif t == Gst.MessageType.EOS:
                    print("GStreamer EOS")
                    capture_failed.set()
                    return

            # Pull latest frame
            sample = sink.emit("try-pull-sample", 100000000)

            if not sample:
                continue

            buf = sample.get_buffer()
            success, mapinfo = buf.map(Gst.MapFlags.READ)

            if success:
                frame = bytes(mapinfo.data)
                buf.unmap(mapinfo)

                with lock:
                    latest_frame = frame

    finally:
        pipeline.set_state(Gst.State.NULL)


def capture_guarded():
    try:
        capture()
    except Exception as exc:
        print("GStreamer capture failed:", exc)
        capture_failed.set()


async def handler(reader, writer):
    writer.write(
        b"HTTP/1.1 200 OK\r\n"
        b"Connection: close\r\n"
        b"Cache-Control: no-cache\r\n"
        b"Pragma: no-cache\r\n"
        b"Content-Type: multipart/x-mixed-replace; boundary=frame\r\n\r\n"
    )

    await writer.drain()

    try:
        while True:
            await asyncio.sleep(0.1)

            with lock:
                frame = latest_frame

            if frame is None:
                continue

            writer.write(
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                + f"Content-Length: {len(frame)}\r\n\r\n".encode()
                + frame
                + b"\r\n"
            )

            await writer.drain()

    except (
        ConnectionResetError,
        BrokenPipeError,
        asyncio.CancelledError,
    ):
        pass

    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except (ConnectionResetError, BrokenPipeError):
            pass


async def main():
    server = await asyncio.start_server(
        handler,
        "0.0.0.0",
        8090,
    )

    async with server:
        while not capture_failed.is_set():
            await asyncio.sleep(1)

    raise RuntimeError("GStreamer capture stopped")


if __name__ == "__main__":
    threading.Thread(target=capture_guarded, daemon=True).start()
    asyncio.run(main())
