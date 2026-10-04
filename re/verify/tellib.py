r"""tellib.py - in-process telemetry recorder for verify/run_scenario.py.

Wraps tools/telemetry/i76tel.py (imported, not copied: Header, decode_frame, decode_events, Csv, source_udp) in a
thread so the runner can stop it and have the CSV flushed and closed (a terminated listener process loses its
buffered tail). Output: <path> (one row per rendered frame, every i76tel_frame_t field) and <path minus .csv>.events.csv.
"""
import os
import socket
import threading
import time

from common import tools_path

tools_path()
import i76tel  # noqa: E402


def port_free(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


class TelemetryRecorder(threading.Thread):
    def __init__(self, csv_path, port=None, keep=False):
        """keep=True also retains every decoded frame in memory (`kept`: list of frame dicts with a `t_wall` key added,
        and `kept_events`: the events with `t_wall`) so a live driver (verify/poke.py) can window its observations
        without re-reading the CSV."""
        super().__init__(daemon=True)
        self.h = i76tel.Header()
        self.port = port or self.h.consts["I76TEL_PORT"]
        self.csv_path = csv_path
        self.csv = None
        self.frames = 0
        self.events = 0
        self.first = None
        self.last = None
        self.stop_flag = threading.Event()
        self.error = None
        self.keep = keep
        self.kept = []
        self.kept_events = []

    def run(self):
        try:
            self.csv = i76tel.Csv(self.h, self.csv_path)
            for data in i76tel.source_udp(self.port):
                if self.stop_flag.is_set():
                    break
                if data is None or len(data) < self.h.frame_size:
                    continue
                fr = i76tel.decode_frame(self.h, data)
                evs = i76tel.decode_events(self.h, data, self.h.frame_size, fr["event_count"])
                self.csv.frame(fr)
                for ev in evs:
                    self.csv.event(ev)
                if self.keep:
                    now = time.time()
                    fr["t_wall"] = now
                    self.kept.append(fr)
                    for ev in evs:
                        ev["t_wall"] = now
                        self.kept_events.append(ev)
                self.frames += 1
                self.events += len(evs)
                if self.first is None:
                    self.first = fr
                self.last = fr
        except Exception as e:  # noqa: BLE001
            self.error = repr(e)
        finally:
            if self.csv:
                self.csv.close()

    def stop(self, timeout=5.0):
        self.stop_flag.set()
        self.join(timeout)          # source_udp yields None every 2 s on timeout
        root, ext = os.path.splitext(self.csv_path)
        return {"frames": self.frames, "events": self.events, "error": self.error,
                "first_frame": self.first["frame"] if self.first else None, "last_frame": self.last["frame"] if self.last else None,
                "events_csv": root + ".events" + (ext or ".csv")}
