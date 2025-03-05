from django.shortcuts import render,redirect
from django.views import View

from imutils.video import VideoStream
from django.http import StreamingHttpResponse

import imutils
import os 
import cv2
import time
import threading

# ウェブカメラの動作を管理するクラス。
class CameraManager:
    def __init__(self):
        self.vs             = None
        self.thread         = None

        # TIPS: threading.Event() は他のスレッドに何かしらの合図を送りたいときに使う。フラグ変数のようなもの。
        #       .set()    : フラグを立てる(Trueにする)
        #       .clear()  : フラグを下ろす(Falseにする)
        #       .is_set() : フラグをチェックする(TrueかFalseか)
        self.stop_event     = threading.Event()

        # TIPS: threading.Lock() は 複数のスレッドで同一のデータにアクセスしないようにするための仕組み
        #       with self.lock: を使えば排他制御できる。
        self.lock           = threading.Lock()
        self.output_frame   = None

    def start(self):
        with self.lock:
            if self.vs is not None:
                return

            # ここのUSBカメラ番号指定はコンストラクタで引数を受け取るように
            self.vs = VideoStream(src=0).start()
            #time.sleep(1)

            self.stop_event.clear()
            self.thread = threading.Thread(target=self._capture_loop)
            self.thread.daemon = True
            self.thread.start()

    def stop(self):
        with self.lock:
            if self.vs is None:
                return

            # ここで停止指示を出しても停止しないので、タイムアウトを用意して停止している。
            self.stop_event.set()
            self.thread.join(timeout=0.1)
            print("終了")

            self.vs.stop()
            self.vs = None
            self.output_frame = None


    def _capture_loop(self):

        # ここで停止指示を受けてもループを続けてしまう？
        while not self.stop_event.is_set():
            frame = self.vs.read()

            # カメラのフレームが取得できない場合は停止
            if frame is None:
                break

            # リサイズ
            frame = imutils.resize(frame, width=400)
            with self.lock:
                self.output_frame = frame.copy()

            print("キャプチャーしています。")


# ウェブカメラの管理をグローバル化して、すべてのビューでウェブカメラの起動と停止ができるようにしている。
camera_manager = CameraManager()


# トップページ
class IndexView(View):
    def get(self, request, *args, **kwargs):
        global camera_manager

        context = {}

        if camera_manager.vs is None:
            context["is_active"] = False
        else:
            context["is_active"] = True

        return render(request,"bbs/index.html", context)

index   = IndexView.as_view()


# ウェブカメラの起動と停止をするビュー
class VideoControlView(View):
    def post(self, request, *args, **kwargs):

        if camera_manager.vs is None:
            camera_manager.start()
        else:
            camera_manager.stop()

        return redirect("bbs:index")

video_control = VideoControlView.as_view()




# 最新のフレームをjpgに変換して返却している
def generate():

    global camera_manager

    while True:
        with camera_manager.lock:
            if camera_manager.output_frame is None:
                continue
            (flag, encodedImage) = cv2.imencode(".jpg", camera_manager.output_frame)
            if not flag:
                continue

        # バイナリでyieldを返す。
        yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(encodedImage) + b'\r\n')


# jpgデータを配信している
class StreamView(View):
    def get(self, request, *args, **kwargs):
        return StreamingHttpResponse(generate(), content_type="multipart/x-mixed-replace; boundary=frame")

stream   = StreamView.as_view()

