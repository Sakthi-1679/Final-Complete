import tempfile
import os

def save_input_files(video, audio):
    img_fd, img_path = tempfile.mkstemp(suffix=".jpg")
    aud_fd, audio_path = tempfile.mkstemp(suffix=".webm")

    video.save(img_path)
    audio.save(audio_path)

    return img_path, audio_path


def cleanup(paths):
    for p in paths:
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except Exception:
            pass
