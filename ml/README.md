# KrishiSathi MobileNetV2 Leaf Disease Model

This directory contains the machine learning pipeline for Tier 2 Leaf-Photo Disease Identification.

## Overview
- **Architecture**: MobileNetV2 with ImageNet transfer learning + GlobalAveragePooling + Dense Classification head.
- **Quantization**: Float16 post-training quantization to reduce model footprint to ~8 MB for offline Raspberry Pi and mobile deployment.
- **Dataset**: PlantVillage (Open-access crop disease dataset with >54,000 images).

## How to Train and Export
1. Install ML dependencies:
   ```bash
   pip install tensorflow pillow matplotlib
   ```
2. Download the PlantVillage dataset:
   ```bash
   # From GitHub or Kaggle
   git clone https://github.com/spMohanty/PlantVillage-Dataset.git
   ```
3. Organize target classes under `ml/dataset/`:
   - `Tomato___Early_blight/`
   - `Tomato___Late_blight/`
   - `Wheat___Brown_rust/`
   - `Maize___Northern_Leaf_Blight/`
   - `Cotton___Bacterial_blight/`
   - `Healthy/`
4. Run training:
   ```bash
   python train_leaf_model.py
   ```
5. The script automatically exports `leaf_disease_model.tflite` to `ml/`. Once present, KrishiSathi's backend detects it and uses it in place of the built-in mock classifier.
