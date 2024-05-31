from django.shortcuts import render,redirect

from django.views import View
#from .models import Topic

class IndexView(View):

    def get(self, request, *args, **kwargs):

        #topics  = Topic.objects.all()
        #context = { "topics":topics }

        return render(request,"bbs/index.html")

    def post(self, request, *args, **kwargs):

        """
        posted  = Topic( comment = request.POST["comment"] )
        posted.save()
        """

        return redirect("bbs:index")

index   = IndexView.as_view()



from .detector import SingleMotionDetector
from imutils.video import VideoStream
from django.http import StreamingHttpResponse

import threading
import time
import datetime
import imutils
import cv2
import os 

# 最新のフレームが入る変数
outputFrame     = None

# スレッド間でのフレームの読み書きを制御するためのロック
lock            = threading.Lock()

# カメラを起動させる(このカメラの起動を任意のタイミングにすることで、使っていないときはOFFにできるのでは？)
vs              = VideoStream(src=0).start()
time.sleep(2.0)

# カメラからフレームを読み取り、動体検知処理をする
def detect_motion(frameCount):
    global vs, outputFrame, lock

    # 動体検知処理を動かす
    md      = SingleMotionDetector(accumWeight=0.1)
    total   = 0

    while True:

        # カメラを読み込みして、リサイズする。
        frame       = vs.read()
        frame       = imutils.resize(frame, width=400)

        # グレースケールとぼかしを掛ける(動体検知の高速化)
        gray        = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray        = cv2.GaussianBlur(gray, (7, 7), 0)

        # 現在の時刻を表示している
        timestamp   = datetime.datetime.now()
        cv2.putText(frame, timestamp.strftime("%A %d %B %Y %I:%M:%S%p"), (10, frame.shape[0] - 10),cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)

        # ここで囲みをつけている
        if total > frameCount:
            motion = md.detect(gray)
            if motion is not None:
                (thresh, (minX, minY, maxX, maxY)) = motion
                cv2.rectangle(frame, (minX, minY), (maxX, maxY),(0, 0, 255), 2)

        # 動体検知機にフレームを更新する
        md.update(gray)

        total += 1
        with lock:
            # 最新のフレームをコピーする
            outputFrame = frame.copy()


# 最新のフレームをjpgに変換して返却している
def generate():
    global outputFrame, lock

    total = 0

    while True:

        start   = time.time()

        with lock:
            if outputFrame is None:
                continue
            (flag, encodedImage) = cv2.imencode(".jpg", outputFrame)
            if not flag:
                continue

        total += 1

        if total < 30:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S%f")
            filename = os.path.join(f"frame_{timestamp}.jpg")
            with open(filename, "wb") as f:
                f.write(encodedImage)

            diff    = time.time() - start
            print(f"{diff * 1000}ミリ秒")

        # yield the output frame in the byte format
        yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(encodedImage) + b'\r\n')



# jpgデータを配信している
class StreamView(View):
    def get(self, request, *args, **kwargs):
        return StreamingHttpResponse(generate(), content_type="multipart/x-mixed-replace; boundary=frame")

# サーバー稼働とストリーミング配信処理を並列に実行する
t           = threading.Thread(target=detect_motion, args=(32,))
t.daemon    = True
t.start()

stream   = StreamView.as_view()


