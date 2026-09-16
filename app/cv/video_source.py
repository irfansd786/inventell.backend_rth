"""Video source abstraction.

Current:  UploadedVideoSource (testing video files).
Future:   LiveCameraSource (RTSP / USB / IP cameras) — same interface,
          so the frontend never needs to change when the source changes.
"""

import os

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None


class VideoSource:
    kind = 'unknown'

    def open(self):
        raise NotImplementedError

    def read(self):
        raise NotImplementedError

    def release(self):
        raise NotImplementedError

    def metadata(self) -> dict:
        return {'kind': self.kind}


class UploadedVideoSource(VideoSource):
    kind = 'uploaded'

    def __init__(self, path: str):
        if not os.path.isfile(path):
            raise FileNotFoundError(f'Video file not found: {path}')
        self.path = path
        self._cap = None
        self._meta = {}

    def open(self):
        if cv2 is None:
            raise RuntimeError('OpenCV (cv2) is not installed — detection engine unavailable')
        self._cap = cv2.VideoCapture(self.path)
        if not self._cap.isOpened():
            raise RuntimeError(f'Could not open video: {self.path}')
        fps = self._cap.get(cv2.CAP_PROP_FPS) or 25.0
        frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self._meta = {
            'kind': self.kind,
            'path': self.path,
            'fps': round(float(fps), 2),
            'frames': frames,
            'width': int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
            'height': int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0),
            'duration': round(frames / float(fps), 2) if fps else 0,
        }
        return self

    def read(self):
        if self._cap is None:
            raise RuntimeError('Source not opened')
        ok, frame = self._cap.read()
        if not ok:
            return None
        # Millisecond timestamp of the frame just read.
        t = self._cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        return frame, t

    def release(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def metadata(self) -> dict:
        return self._meta


class LiveCameraSource(VideoSource):
    """Future RTSP/USB/IP camera source. NOT implemented yet."""

    kind = 'live'

    def __init__(self, uri: str):
        self.uri = uri

    def open(self):
        raise NotImplementedError(
            'Live camera streaming (RTSP/USB/IP) is not implemented yet. Use UploadedVideoSource.'
        )
