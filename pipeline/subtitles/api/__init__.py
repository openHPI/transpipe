import cv2


def get_runtime(video_path):
    video = cv2.VideoCapture(video_path)

    duration = video.get(cv2.CAP_PROP_POS_MSEC)
    frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)

    return duration, frame_count
