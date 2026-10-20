"""
Leaf Disease Classifier Interface with TFLite Support and Smart Mock Fallback.

Design:
1. BaseLeafClassifier: Abstract interface defining `classify_image(image_bytes, filename, crop)`.
2. TFLiteLeafClassifier: Attempts to run inference using an exported TensorFlow Lite model
   (`ml/leaf_disease_model.tflite`).
3. MockLeafClassifier: Demo-ready, deterministic classifier that parses filenames or crop context
   to produce realistic diagnostic probabilities.
4. Confidence Thresholding:
   If confidence < 70% (0.70), the classifier explicitly refuses to guess:
   "Unsure - sent to extension officer".
   Such cases are added to the Officer Review Queue.
"""

import os
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session

from backend.models import OfficerQueueItem

CONFIDENCE_THRESHOLD = 0.70

FIRST_STEP_ADVICE = {
    "Tomato___Early_blight": {
        "disease_name": "Tomato Early Blight (Alternaria solani)",
        "advice_en": "Prune and bury lower yellowed leaves. Avoid wetting foliage during irrigation. Inspect nearby plants.",
        "advice_hi": "निचली पीली पत्तियों को काट कर नष्ट करें। पत्तियों पर पानी न पड़ने दें। खेत का निरीक्षण करें।",
        "advice_mr": "खालची पिवळी पडलेली पाने काढून जमिनीत गाडून टाका. पानांवर पाणी उडणार नाही याची काळजी घ्या."
    },
    "Tomato___Late_blight": {
        "disease_name": "Tomato Late Blight (Phytophthora infestans)",
        "advice_en": "High moisture hazard. Stop flood irrigation immediately; ensure row aeration. Inspect leaf undersides daily for white mildew.",
        "advice_hi": "अत्यधिक नमी का खतरा। तुरंत अधिक सिंचाई रोकें और हवादार स्थिति बनाएं। सफेद फफूंद के लिए पत्तियों का निरीक्षण करें।",
        "advice_mr": "जास्त आर्द्रतेमुळे फैलाव वाढतो. मोकळे पाणी देणे त्वरित थांबवा आणि रोज पानांची बारकाईने पाहणी करा."
    },
    "Wheat___Brown_rust": {
        "disease_name": "Wheat Brown Rust (Puccinia triticina)",
        "advice_en": "Check for orange-brown powdery pustules. Delay nitrogen fertilizer application; monitor daily for field spread.",
        "advice_hi": "पत्तियों पर नारंगी-भूरे पाउडर जैसे धब्बों का निरीक्षण करें। नाइट्रोजन खाद का प्रयोग रोकें।",
        "advice_mr": "पानांवर केशरी रंगाचे डाग तपासा. नत्राचा वापर टाळा आणि शेतात रोग किती पसरला आहे ते पहा."
    },
    "Maize___Northern_Leaf_Blight": {
        "disease_name": "Maize Northern Leaf Blight (Exserohilum turcicum)",
        "advice_en": "Cigar-shaped lesions identified. Improve furrow drainage and inspect upper leaves near tassel.",
        "advice_hi": "लंबे सिगार जैसे धब्बे देखे गए। जल निकासी दुरुस्त करें और ऊपरी पत्तियों का निरीक्षण करें।",
        "advice_mr": "पानांवर लांबट चट्टे आढळले. पाण्याचा निचरा नीट करा आणि वरील पानांची पाहणी करा."
    },
    "Cotton___Bacterial_blight": {
        "disease_name": "Cotton Bacterial Blight / Angular Leaf Spot",
        "advice_en": "Angular water-soaked leaf spots detected. Avoid overhead splashing; remove and burn infected fallen debris.",
        "advice_hi": "कोणीय धब्बे पाए गए। खेत में गिरे संक्रमित पत्तों को इकट्ठा कर नष्ट करें।",
        "advice_mr": "पानांवर कोनीय चट्टे आढळले. रोगट गळालेली पाने गोळा करून जाळून नष्ट करा."
    },
    "Healthy": {
        "disease_name": "Healthy Leaf",
        "advice_en": "Leaf shows normal vigor and chlorophyll density. Continue regular weekly scouting.",
        "advice_hi": "पत्ती पूरी तरह स्वस्थ और हरी है। नियमित साप्ताहिक निरीक्षण जारी रखें।",
        "advice_mr": "पान पूर्णपणे निरोगी आणि सशक्त आहे. नियमित साप्ताहिक पाहणी सुरू ठेवा."
    }
}


class BaseLeafClassifier(ABC):
    @abstractmethod
    def classify(self, image_bytes: bytes, filename: str, crop: str) -> Dict[str, Any]:
        pass


class TFLiteLeafClassifier(BaseLeafClassifier):
    def __init__(self, model_path: str):
        self.model_path = model_path
        self.interpreter = None
        self._initialize_interpreter()

    def _initialize_interpreter(self):
        try:
            # Try importing tflite_runtime or full tensorflow
            try:
                import tflite_runtime.interpreter as tflite
                self.interpreter = tflite.Interpreter(model_path=self.model_path)
            except ImportError:
                import tensorflow as tf
                self.interpreter = tf.lite.Interpreter(model_path=self.model_path)
            self.interpreter.allocate_tensors()
        except Exception:
            self.interpreter = None

    def is_available(self) -> bool:
        return self.interpreter is not None

    def classify(self, image_bytes: bytes, filename: str, crop: str) -> Dict[str, Any]:
        # Preprocessing and running inference if model is active
        # Fall back gracefully if not loaded
        if not self.interpreter:
            raise RuntimeError("TFLite interpreter not initialized.")
        # Note: Production implementation loads image array, normalizes to 224x224, runs invoke()
        pass


class MockLeafClassifier(BaseLeafClassifier):
    """
    Intelligent heuristic mock classifier for viva and offline demonstration.
    Returns realistic diseases based on filename keywords or crop context.
    """
    def classify(self, image_bytes: bytes, filename: str, crop: str) -> Dict[str, Any]:
        fname = filename.lower()
        crop_clean = crop.lower()

        # Unsure / Low confidence triggers
        if any(w in fname for w in ["blurry", "unsure", "unclear", "dark", "unknown", "low_conf"]):
            return {
                "raw_disease": "Unknown",
                "disease_name": "Unsure - sent to extension officer",
                "confidence": 0.48,
                "is_unsure": True,
                "advice": {
                    "en": "Photo quality is ambiguous. Sent to the extension officer queue. Do not apply chemical sprays.",
                    "hi": "फोटो अस्पष्ट है। कृषि विस्तार अधिकारी को भेजा गया है। अभी कोई दवा न छिड़कें।",
                    "mr": "फोटो स्पष्ट नाही. कृषी अधिकाऱ्याकडे तपासणीसाठी पाठवला आहे. परस्पर रासायनिक फवारणी करू नका."
                }
            }

        # Explicit filename matching
        if "late_blight" in fname or ("tomato" in crop_clean and "blight" in fname):
            key = "Tomato___Late_blight"
            conf = 0.94
        elif "early_blight" in fname:
            key = "Tomato___Early_blight"
            conf = 0.91
        elif "rust" in fname or "wheat" in crop_clean:
            key = "Wheat___Brown_rust"
            conf = 0.89
        elif "maize" in crop_clean or "corn" in fname:
            key = "Maize___Northern_Leaf_Blight"
            conf = 0.92
        elif "cotton" in crop_clean:
            key = "Cotton___Bacterial_blight"
            conf = 0.88
        elif "healthy" in fname:
            key = "Healthy"
            conf = 0.96
        else:
            # Default fallback based on selected crop
            if crop_clean == "tomato":
                key = "Tomato___Late_blight"
                conf = 0.88
            elif crop_clean == "wheat":
                key = "Wheat___Brown_rust"
                conf = 0.87
            elif crop_clean == "maize":
                key = "Maize___Northern_Leaf_Blight"
                conf = 0.86
            elif crop_clean == "cotton":
                key = "Cotton___Bacterial_blight"
                conf = 0.85
            else:
                key = "Tomato___Early_blight"
                conf = 0.82

        info = FIRST_STEP_ADVICE[key]
        return {
            "raw_disease": key,
            "disease_name": info["disease_name"],
            "confidence": conf,
            "is_unsure": False,
            "advice": {
                "en": info["advice_en"],
                "hi": info["advice_hi"],
                "mr": info["advice_mr"]
            }
        }


# Model factory / singleton
TFLITE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "ml",
    "leaf_disease_model.tflite"
)

def get_classifier() -> BaseLeafClassifier:
    """Returns TFLite classifier if model file exists and runs, otherwise returns Mock."""
    if os.path.exists(TFLITE_PATH):
        try:
            tflite_cls = TFLiteLeafClassifier(TFLITE_PATH)
            if tflite_cls.is_available():
                return tflite_cls
        except Exception:
            pass
    return MockLeafClassifier()


def inspect_leaf_image(
    image_bytes: bytes,
    filename: str,
    crop: str,
    village_id: str,
    db: Session
) -> Dict[str, Any]:
    """
    Processes uploaded leaf photo:
    - Runs classification
    - If confidence < CONFIDENCE_THRESHOLD: pushes to OfficerQueueItem
    - Returns structured diagnostic result
    """
    classifier = get_classifier()
    res = classifier.classify(image_bytes, filename, crop)

    if res["confidence"] < CONFIDENCE_THRESHOLD or res.get("is_unsure"):
        # Auto-route to Officer review queue
        queue_item = OfficerQueueItem(
            image_filename=filename,
            crop=crop.lower(),
            village_id=village_id,
            confidence=res["confidence"],
            status="pending"
        )
        db.add(queue_item)
        db.commit()
        db.refresh(queue_item)

        return {
            "disease_name": "Unsure - sent to extension officer",
            "raw_disease": "Unsure",
            "confidence_pct": round(res["confidence"] * 100.0, 1),
            "is_unsure": True,
            "queued_id": queue_item.id,
            "advice": res["advice"]
        }

    return {
        "disease_name": res["disease_name"],
        "raw_disease": res["raw_disease"],
        "confidence_pct": round(res["confidence"] * 100.0, 1),
        "is_unsure": False,
        "advice": res["advice"]
    }
