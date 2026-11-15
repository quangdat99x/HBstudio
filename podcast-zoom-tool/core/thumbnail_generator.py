"""
Thumbnail Generator — Creates podcast-style split-screen thumbnail images.

After processing a video, generates a thumbnail where the frame is split
into N equal panels (one per detected podcaster), with each face centered
and properly aligned — similar to the classic podcast layout.
"""

import cv2
import numpy as np
from typing import List, Tuple


def generate_split_thumbnail(
    frame: np.ndarray,
    face_centers: List[Tuple[float, float]],
    face_bboxes: List[Tuple[int, int, int, int]],
    output_path: str,
    output_width: int = 1920,
    output_height: int = 1080,
    border_width: int = 2,
    border_color: Tuple[int, int, int] = (20, 20, 20),
    face_vertical_bias: float = 0.38,
) -> str:
    """
    Generate a split-screen thumbnail from a single frame.

    Args:
        frame: BGR video frame
        face_centers: List of (x, y) face center points
        face_bboxes: List of (x, y, w, h) face bounding boxes
        output_path: Where to save the thumbnail image
        output_width: Output thumbnail width
        output_height: Output thumbnail height
        border_width: Width of the dividing border between panels
        border_color: BGR color of dividing border
        face_vertical_bias: How high to place the face (0.0=top, 0.5=center, 1.0=bottom)
                           0.38 places face roughly at upper-third for natural look

    Returns:
        Path to the saved thumbnail image
    """
    h, w = frame.shape[:2]
    n_faces = len(face_centers)

    if n_faces == 0:
        # No faces: just resize the whole frame
        thumbnail = cv2.resize(frame, (output_width, output_height),
                               interpolation=cv2.INTER_LANCZOS4)
        cv2.imwrite(output_path, thumbnail, [cv2.IMWRITE_JPEG_QUALITY, 95])
        return output_path

    # Sort faces left-to-right by their x position
    sorted_indices = sorted(range(n_faces), key=lambda i: face_centers[i][0])
    sorted_centers = [face_centers[i] for i in sorted_indices]
    sorted_bboxes = [face_bboxes[i] for i in sorted_indices]

    # Calculate panel dimensions
    panel_width = output_width // n_faces
    panel_height = output_height

    # Create output thumbnail
    thumbnail = np.zeros((output_height, output_width, 3), dtype=np.uint8)

    for idx in range(n_faces):
        cx, cy = sorted_centers[idx]
        bx, by, bw, bh = sorted_bboxes[idx]

        # Desired crop aspect ratio (panel_width / panel_height)
        crop_aspect = panel_width / panel_height

        # Use 2.8x the face height for good framing (head + shoulders)
        face_frame_h = max(bh * 2.8, h * 0.6)
        face_frame_w = face_frame_h * crop_aspect

        # Ensure crop doesn't exceed frame dimensions
        if face_frame_w > w:
            face_frame_w = w
            face_frame_h = face_frame_w / crop_aspect
        if face_frame_h > h:
            face_frame_h = h
            face_frame_w = face_frame_h * crop_aspect

        # Center the crop on the face, with vertical bias
        crop_cx = cx
        crop_cy = cy + (face_frame_h * (0.5 - face_vertical_bias))

        # Clamp crop to frame bounds
        half_w = face_frame_w / 2
        half_h = face_frame_h / 2

        crop_x1 = max(0, int(crop_cx - half_w))
        crop_y1 = max(0, int(crop_cy - half_h))
        crop_x2 = min(w, int(crop_cx + half_w))
        crop_y2 = min(h, int(crop_cy + half_h))

        # Re-adjust if we hit bounds
        if crop_x2 - crop_x1 < face_frame_w:
            if crop_x1 == 0:
                crop_x2 = min(w, int(face_frame_w))
            else:
                crop_x1 = max(0, int(w - face_frame_w))
        if crop_y2 - crop_y1 < face_frame_h:
            if crop_y1 == 0:
                crop_y2 = min(h, int(face_frame_h))
            else:
                crop_y1 = max(0, int(h - face_frame_h))

        # Extract and resize to panel
        cropped = frame[crop_y1:crop_y2, crop_x1:crop_x2]
        if cropped.size == 0:
            cropped = frame

        panel = cv2.resize(cropped, (panel_width, panel_height),
                           interpolation=cv2.INTER_LANCZOS4)

        # Place panel in thumbnail
        x_offset = idx * panel_width
        thumbnail[:, x_offset:x_offset + panel_width] = panel

    # Draw dividing borders between panels
    if border_width > 0 and n_faces > 1:
        for i in range(1, n_faces):
            x = i * panel_width
            x1 = max(0, x - border_width // 2)
            x2 = min(output_width, x + border_width // 2 + border_width % 2)
            thumbnail[:, x1:x2] = border_color

    # Save thumbnail
    cv2.imwrite(output_path, thumbnail, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return output_path
