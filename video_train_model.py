import os
import cv2
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv2D, MaxPooling2D, Flatten, Dense, Dropout
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.optimizers import Adam

# Define paths
video_paths = {
    "Defect": "Videos/Defect Cloth",
    "Non_Defect": "Videos/Non Defect Cloth"
}
output_dataset = "Dataset"

# Ensure directories exist
os.makedirs(output_dataset, exist_ok=True)
os.makedirs(f"{output_dataset}/Defect", exist_ok=True)
os.makedirs(f"{output_dataset}/Non_Defect", exist_ok=True)

def extract_frames(video_folder, output_folder, frame_interval=10):
    """ Extract frames from each video file in the given folder """
    for video_file in os.listdir(video_folder):
        video_path = os.path.join(video_folder, video_file)
        cap = cv2.VideoCapture(video_path)
        frame_count = 0
        success, frame = cap.read()

        while success:
            if frame_count % frame_interval == 0:
                frame_filename = os.path.join(output_folder, f"{video_file}_frame_{frame_count}.jpg")
                cv2.imwrite(frame_filename, frame)
            success, frame = cap.read()
            frame_count += 1

        cap.release()

# Extract frames from both video categories
extract_frames(video_paths["Defect"], f"{output_dataset}/Defect")
extract_frames(video_paths["Non_Defect"], f"{output_dataset}/Non_Defect")

# Define image size & batch size
IMG_SIZE = (128, 128)
BATCH_SIZE = 32

# Image Data Augmentation
train_datagen = ImageDataGenerator(
    rescale=1./255, 
    validation_split=0.2
)

train_generator = train_datagen.flow_from_directory(
    output_dataset,
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    class_mode="binary",
    subset="training"
)

val_generator = train_datagen.flow_from_directory(
    output_dataset,
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    class_mode="binary",
    subset="validation"
)

# Build CNN Model
model = Sequential([
    Conv2D(32, (3, 3), activation='relu', input_shape=(128, 128, 3)),
    MaxPooling2D(pool_size=(2, 2)),
    Conv2D(64, (3, 3), activation='relu'),
    MaxPooling2D(pool_size=(2, 2)),
    Flatten(),
    Dense(128, activation='relu'),
    Dropout(0.5),
    Dense(1, activation='sigmoid')  # Binary Classification (Defect / Non-Defect)
])

# Compile Model
model.compile(optimizer=Adam(learning_rate=0.0001), loss="binary_crossentropy", metrics=["accuracy"])

# Train Model
model.fit(train_generator, validation_data=val_generator, epochs=10)

# Save Model
model.save("video_fabric_defect_model.h5")

print("Model training completed and saved as video_fabric_defect_model.h5")
