"""
KrishiSathi Leaf Disease Model Training Script.
Uses Transfer Learning with MobileNetV2 on the PlantVillage crop leaf disease dataset.
Exports a quantized .tflite model for edge deployment on mobile and Raspberry Pi devices.

Prerequisites:
  pip install tensorflow pillow matplotlib

Dataset:
  Download PlantVillage dataset from Kaggle or GitHub:
  https://github.com/spMohanty/PlantVillage-Dataset
  Arrange dataset into folders:
    dataset/
      Tomato___Early_blight/
      Tomato___Late_blight/
      Wheat___Brown_rust/
      Maize___Northern_Leaf_Blight/
      Cotton___Bacterial_blight/
      Healthy/
"""

import os
import sys

def main():
    print("=" * 70)
    print("KrishiSathi MobileNetV2 Leaf Disease Model Trainer")
    print("=" * 70)

    try:
        import tensorflow as tf
        from tensorflow.keras import layers, models
        from tensorflow.keras.applications import MobileNetV2
        from tensorflow.keras.preprocessing.image import ImageDataGenerator
    except ImportError:
        print("[!] TensorFlow not installed in this environment.")
        print("    To run training, execute: pip install tensorflow pillow")
        print("    KrishiSathi will continue using the high-accuracy built-in heuristic classifier.")
        return

    # Hyperparameters
    IMG_SIZE = (224, 224)
    BATCH_SIZE = 32
    EPOCHS = 10
    DATASET_DIR = "dataset"
    OUTPUT_TFLITE = "leaf_disease_model.tflite"

    if not os.path.exists(DATASET_DIR):
        print(f"[!] Dataset directory '{DATASET_DIR}' not found.")
        print("    Please follow instructions in ml/README.md to download PlantVillage.")
        return

    print(f"[*] Loading dataset from '{DATASET_DIR}'...")
    datagen = ImageDataGenerator(
        rescale=1.0 / 255.0,
        validation_split=0.2,
        rotation_range=20,
        zoom_range=0.15,
        horizontal_flip=True
    )

    train_gen = datagen.flow_from_directory(
        DATASET_DIR,
        target_size=IMG_SIZE,
        batch_size=BATCH_SIZE,
        subset="training",
        class_mode="categorical"
    )

    val_gen = datagen.flow_from_directory(
        DATASET_DIR,
        target_size=IMG_SIZE,
        batch_size=BATCH_SIZE,
        subset="validation",
        class_mode="categorical"
    )

    num_classes = train_gen.num_classes
    print(f"[*] Detected {num_classes} classes: {list(train_gen.class_indices.keys())}")

    # Build Transfer Learning Architecture using MobileNetV2 (fast & lightweight)
    print("[*] Instantiating MobileNetV2 base (ImageNet weights)...")
    base_model = MobileNetV2(
        weights="imagenet",
        include_top=False,
        input_shape=(224, 224, 3)
    )
    base_model.trainable = False  # Freeze pre-trained convolutional feature extractor

    model = models.Sequential([
        base_model,
        layers.GlobalAveragePooling2D(),
        layers.Dropout(0.2),
        layers.Dense(128, activation="relu"),
        layers.Dense(num_classes, activation="softmax")
    ])

    model.compile(
        optimizer="adam",
        loss="categorical_crossentropy",
        metrics=["accuracy"]
    )
    model.summary()

    # Train model
    print(f"[*] Training for {EPOCHS} epochs...")
    history = model.fit(
        train_gen,
        validation_data=val_gen,
        epochs=EPOCHS
    )

    # Export to TensorFlow Lite with float16 quantization for edge speed
    print(f"[*] Converting model to TensorFlow Lite ({OUTPUT_TFLITE})...")
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_types = [tf.float16]
    tflite_model = converter.convert()

    with open(OUTPUT_TFLITE, "wb") as f:
        f.write(tflite_model)

    print(f"[✓] Successfully exported {OUTPUT_TFLITE} ({len(tflite_model) / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
