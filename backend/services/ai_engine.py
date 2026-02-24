import numpy as np
import os
import json
from pathlib import Path
from typing import Dict, Optional
import traceback

# TensorFlow / Keras for face_model.h5
try:
    import tensorflow as tf
    from tensorflow.keras.models import load_model as keras_load_model
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    print("[WARN] TensorFlow not installed. Face model (face_model.h5) will be unavailable.")

# OpenCV for face detection and image pre-processing
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("[WARN] OpenCV (cv2) not installed. Face detection will be unavailable.")


class MultimodalEngine:
    """AI Engine for face emotion detection using face_model.h5 (Keras/TF)."""

    # Standard FER-style emotion labels -> mapped to app mood labels
    # Adjust this list if your face_model.h5 was trained with different class ordering.
    FER_LABELS = ["angry", "disgust", "fear", "happy", "neutral", "sad", "surprise"]

    # Only 4 supported moods: happy, calm, sad, angry
    FER_TO_MOOD = {
        "angry":    "angry",
        "disgust":  "angry",
        "fear":     "sad",
        "happy":    "happy",
        "neutral":  "calm",
        "sad":      "sad",
        "surprise": "happy",
    }

    # Expected input size for the face model (height, width)
    FACE_INPUT_SIZE = (48, 48)

    def __init__(self, model_path: str = None):
        models_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models"
        )

        # face_model.h5 path
        if model_path is None:
            model_path = os.path.join(models_dir, "face_model.h5")

        self.model_path = model_path
        self.model = None        # Keras model
        self.model_version = "face_model_h5"

        # Haar cascade for frontal face detection
        self.face_cascade = None

        self._load_model()
        self._load_face_cascade()

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _load_model(self):
        """Load face_model.h5 with Keras."""
        if not TF_AVAILABLE:
            print("[WARN] TensorFlow unavailable - skipping face model load.")
            return False

        if not os.path.exists(self.model_path):
            print(f"[WARN] face_model.h5 not found at: {self.model_path}")
            print("[INFO] Falling back to heuristic mood prediction.")
            return False

        try:
            print(f"[LOAD] Loading face emotion model from: {self.model_path}")
            self.model = keras_load_model(self.model_path, compile=False)

            # Infer expected number of output classes and build label mapping
            output_classes = self.model.output_shape[-1]

            # --- Always try face_labels.json first ---
            labels_json = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "models", "face_labels.json"
            )
            if os.path.exists(labels_json):
                with open(labels_json, "r") as f:
                    raw = json.load(f)   # e.g. {"0":"angry","1":"happy","2":"sad"}
                self.FER_LABELS = [raw[str(i)] for i in range(output_classes)]
                print(f"[LOAD] Face labels from face_labels.json: {self.FER_LABELS}")
            elif output_classes != len(self.FER_LABELS):
                print(
                    f"[INFO] Model has {output_classes} output classes; "
                    f"expected {len(self.FER_LABELS)}. "
                    "Using generic label indices."
                )
                self.FER_LABELS = [f"emotion_{i}" for i in range(output_classes)]

            # Rebuild FER_TO_MOOD from the resolved label list
            # Supported moods: happy, calm, sad, angry
            LABEL_MAP = {
                "angry":    "angry",
                "disgust":  "angry",
                "fear":     "sad",
                "happy":    "happy",
                "neutral":  "calm",
                "sad":      "sad",
                "surprise": "happy",
            }
            self.FER_TO_MOOD = {
                label: LABEL_MAP.get(label, "calm")
                for label in self.FER_LABELS
            }
            print(f"[LOAD] FER->Mood map: {self.FER_TO_MOOD}")

            # Try to infer input image size from model
            input_shape = self.model.input_shape  # e.g. (None, 48, 48, 1)
            if len(input_shape) == 4:
                self.FACE_INPUT_SIZE = (input_shape[1], input_shape[2])

            print(f"[SUCCESS] face_model.h5 loaded. Input: {self.model.input_shape}, "
                  f"Output classes: {output_classes}, "
                  f"Labels: {self.FER_LABELS}")
            return True

        except Exception as e:
            print(f"[ERROR] Failed to load face_model.h5: {e}")
            traceback.print_exc()
            self.model = None
            return False

    def _load_face_cascade(self):
        """Load OpenCV Haar cascade for frontal face detection."""
        if not CV2_AVAILABLE:
            return
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        if os.path.exists(cascade_path):
            self.face_cascade = cv2.CascadeClassifier(cascade_path)
            print("[LOAD] OpenCV Haar cascade loaded for face detection.")
        else:
            print("[WARN] Haar cascade file not found; face detection may be limited.")

    # ------------------------------------------------------------------
    # Image preprocessing
    # ------------------------------------------------------------------

    def _preprocess_face(self, face_bgr: np.ndarray) -> np.ndarray:
        """
        Resize and normalise a detected face crop for model input.
        Returns array of shape (1, H, W, C) ready for model.predict().
        """
        h, w = self.FACE_INPUT_SIZE
        face_resized = cv2.resize(face_bgr, (w, h))

        # Determine channel requirement from model input shape
        input_channels = self.model.input_shape[-1] if self.model else 1

        if input_channels == 1:
            face_gray = cv2.cvtColor(face_resized, cv2.COLOR_BGR2GRAY)
            face_norm = face_gray.astype("float32") / 255.0
            face_input = np.expand_dims(face_norm, axis=-1)  # (H, W, 1)
        else:
            face_rgb = cv2.cvtColor(face_resized, cv2.COLOR_BGR2RGB)
            face_input = face_rgb.astype("float32") / 255.0   # (H, W, 3)

        return np.expand_dims(face_input, axis=0)  # (1, H, W, C)

    def _detect_and_crop_face(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        Run Haar cascade face detection and return the largest face crop.
        Falls back to the full image if no face is detected.
        """
        if self.face_cascade is None:
            return image  # no detector available

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )

        if len(faces) == 0:
            print("[INFO] No face detected - using full image for emotion analysis.")
            return image

        # Pick the largest face
        faces = sorted(faces, key=lambda r: r[2] * r[3], reverse=True)
        x, y, fw, fh = faces[0]
        return image[y : y + fh, x : x + fw]

    # ------------------------------------------------------------------
    # Inference - Keras model (TF available)
    # ------------------------------------------------------------------

    def _predict_from_image(self, img_path: str) -> Optional[Dict]:
        """
        Run face emotion detection on *img_path* using the Keras model.
        Returns a result dict, or None if the model is unavailable.
        """
        if not CV2_AVAILABLE or self.model is None:
            return None

        image = cv2.imread(img_path)
        if image is None:
            print(f"[WARN] Could not read image: {img_path}")
            return None

        face_crop = self._detect_and_crop_face(image)
        face_input = self._preprocess_face(face_crop)

        probs = self.model.predict(face_input, verbose=0)[0]  # shape: (num_classes,)
        emotion_idx = int(np.argmax(probs))
        confidence = float(probs[emotion_idx])
        fer_label = self.FER_LABELS[emotion_idx]

        # Always trust the model's top prediction.
        # "calm" is reserved for the OpenCV fallback (no Keras model available).
        # Only fall back to calm if every class is virtually identical (pure noise).
        if confidence < (1.0 / len(self.FER_LABELS)) + 0.02:
            # Probabilities are almost uniform - true neutral/calm expression
            mood = "calm"
        else:
            mood = self.FER_TO_MOOD.get(fer_label, "calm")

        print(f"[Predict] probs={[round(float(p),2) for p in probs]} top={fer_label}({confidence:.0%}) -> {mood}")

        return {
            "mood": mood,
            "confidence": round(min(confidence, 0.99), 4),
            "fer_label": fer_label,
            "all_probs": {self.FER_LABELS[i]: round(float(p), 4) for i, p in enumerate(probs)},
        }

    # ------------------------------------------------------------------
    # Inference - OpenCV pixel analysis (TF NOT available)
    # ------------------------------------------------------------------

    def _predict_opencv_fallback(self, img_path: str) -> Optional[Dict]:
        """
        Estimate mood from raw pixel features when face_model.h5 cannot be
        loaded (e.g. TensorFlow not installed).  Uses OpenCV only.

        Logic:
          - Detect & crop the face with the Haar cascade.
          - Split the face into three horizontal thirds:
              top  = forehead / brow region
              mid  = eye / nose region
              bot  = mouth / chin region
          - Features:
              * bottom_brightness  - bright mouth area -> teeth showing -> happy
              * top_gradient       - strong edge in brow area -> angry/stressed
              * overall_brightness - very dark -> sad tendency
              * contrast (std dev) - very low variance -> calm / neutral
        """
        if not CV2_AVAILABLE:
            return None

        image = cv2.imread(img_path)
        if image is None:
            return None

        face_crop = self._detect_and_crop_face(image)

        # Resize to a fixed size for consistent feature extraction
        face_small = cv2.resize(face_crop, (64, 64))
        gray = cv2.cvtColor(face_small, cv2.COLOR_BGR2GRAY).astype("float32")

        h = gray.shape[0]
        top_band = gray[: h // 3, :]          # brow / forehead
        bot_band = gray[2 * h // 3 :, :]      # mouth / chin

        overall_brightness = float(np.mean(gray))          # 0-255
        contrast           = float(np.std(gray))           # 0-128 approx
        bottom_brightness  = float(np.mean(bot_band))
        # Sobel gradient magnitude in the brow region
        sobel_x = cv2.Sobel(top_band, cv2.CV_32F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(top_band, cv2.CV_32F, 0, 1, ksize=3)
        top_gradient = float(np.mean(np.sqrt(sobel_x**2 + sobel_y**2)))

        # ---- Decision rules ----------------------------------------
        # happy : bright mouth area (> 140) AND decent overall brightness
        # angry : strong brow gradient (> 25) AND contrast (> 40)
        # sad   : dark overall face (< 90) OR very low contrast (< 18)
        # calm  : everything in mid range - default

        if bottom_brightness > 140 and overall_brightness > 100:
            mood       = "happy"
            confidence = round(min(0.55 + (bottom_brightness - 140) / 300, 0.90), 2)
            reason     = (
                f"Bright mouth region ({bottom_brightness:.0f}) indicates happy expression"
            )
        elif top_gradient > 25 and contrast > 40:
            mood       = "angry"
            confidence = round(min(0.50 + top_gradient / 200, 0.88), 2)
            reason     = (
                f"Strong brow gradient ({top_gradient:.1f}) indicates tense/angry expression"
            )
        elif overall_brightness < 90 or contrast < 18:
            mood       = "sad"
            confidence = round(min(0.50 + (90 - overall_brightness) / 200, 0.85), 2)
            reason     = (
                f"Low face brightness ({overall_brightness:.0f}) / contrast ({contrast:.0f}) "
                "indicates subdued/sad expression"
            )
        else:
            mood       = "calm"
            confidence = round(0.55 + contrast / 400, 2)
            reason     = (
                f"Balanced face features (brightness={overall_brightness:.0f}, "
                f"contrast={contrast:.0f}) indicate calm expression"
            )

        print(
            f"[OpenCV] brightness={overall_brightness:.1f} contrast={contrast:.1f} "
            f"bot_bright={bottom_brightness:.1f} top_grad={top_gradient:.1f} "
            f"-> {mood} ({confidence:.0%})"
        )

        return {
            "mood": mood,
            "confidence": confidence,
            "fer_label": mood,
            "method": "opencv_pixel_analysis",
            "reasoning": reason,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, img_path: str = None, audio_path: str = None) -> Dict:
        """
        Analyse mood from a face image (and optionally audio).

        Priority:
          1. Keras face_model.h5  (when TensorFlow is installed)
          2. OpenCV pixel-analysis fallback (always available if cv2 installed)
          3. Hard default "calm"

        Returns:
            Dict with keys: mood, confidence, reasoning
        """
        try:
            if img_path and os.path.exists(img_path):
                # --- Try Keras model first ---
                keras_result = self._predict_from_image(img_path)
                if keras_result is not None:
                    return {
                        "mood": keras_result["mood"],
                        "confidence": keras_result["confidence"],
                        "reasoning": (
                            f"face_model.h5 detected '{keras_result['fer_label']}' "
                            f"-> mood '{keras_result['mood']}' "
                            f"(confidence {keras_result['confidence']:.2%})"
                        ),
                    }

                # --- OpenCV pixel-analysis fallback ---
                cv_result = self._predict_opencv_fallback(img_path)
                if cv_result is not None:
                    return {
                        "mood": cv_result["mood"],
                        "confidence": cv_result["confidence"],
                        "reasoning": cv_result["reasoning"],
                    }

            # Last resort default
            return self._default_mood()

        except Exception as e:
            print(f"[ERROR] Error in mood analysis: {e}")
            traceback.print_exc()
            return self._default_mood()

    def _default_mood(self) -> Dict:
        """Absolute last-resort default (no image available at all)."""
        return {
            "mood": "calm",
            "confidence": 0.5,
            "reasoning": "No image available for analysis - defaulting to calm",
        }

    def batch_analyze(self, samples: list) -> list:
        """Analyse multiple (img_path, audio_path) pairs."""
        return [self.analyze(img, audio) for img, audio in samples]

    def get_model_info(self) -> Dict:
        """Return metadata about the loaded model."""
        return {
            "version": self.model_version,
            "model_path": self.model_path,
            "model_loaded": self.model is not None,
            "fer_labels": self.FER_LABELS,
            "fer_to_mood_map": self.FER_TO_MOOD,
            "face_input_size": self.FACE_INPUT_SIZE,
            "tensorflow_available": TF_AVAILABLE,
            "opencv_available": CV2_AVAILABLE,
        }
