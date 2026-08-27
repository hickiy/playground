import base64
import io
import os
import sys
import tempfile

import gradio as gr
import numpy as np
import torch
from PIL import Image, ImageDraw

CURRENT_DIR = os.path.dirname(__file__)
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

from models.mlp import MLP
from utils.checkpoint import load_checkpoint

DISPLAY_HIDDEN_NEURONS = 32


def _decode_base64_image(data: str) -> Image.Image:
    if "," in data:
        data = data.split(",", 1)[1]
    raw = base64.b64decode(data)
    return Image.open(io.BytesIO(raw))


def _coerce_image_payload(image: Image.Image | np.ndarray | dict) -> Image.Image | np.ndarray:
    if isinstance(image, dict):
        for key in ("image", "composite", "background", "mask"):
            if key in image and image[key] is not None:
                image = image[key]
                break

    if isinstance(image, dict):
        if "data" in image and isinstance(image["data"], str):
            return _decode_base64_image(image["data"])
        if "path" in image and isinstance(image["path"], str):
            return Image.open(image["path"])
        raise ValueError("Sketchpad did not return an image")

    if isinstance(image, str):
        return _decode_base64_image(image)

    return image


def preprocess_image(image: Image.Image | np.ndarray | dict) -> torch.Tensor:
    if image is None:
        raise ValueError("No image provided")

    image = _coerce_image_payload(image)

    if isinstance(image, np.ndarray):
        arr = image.astype(np.float32)
        if arr.ndim == 3:
            arr = arr[:, :, 0]
        arr = arr / 255.0
        img = Image.fromarray((arr * 255).astype(np.uint8), mode="L")
        img = img.resize((28, 28))
        arr = np.array(img, dtype=np.float32) / 255.0
    elif isinstance(image, Image.Image):
        img = image.convert("L").resize((28, 28))
        arr = np.array(img, dtype=np.float32) / 255.0
    else:
        raise ValueError("Unsupported image type from Sketchpad")

    # Heuristic: if background is bright, invert to match MNIST (white digit on black)
    if arr.mean() > 0.5:
        arr = 1.0 - arr

    tensor = torch.from_numpy(arr).unsqueeze(0).unsqueeze(0)
    return tensor


def _normalize_array(arr: np.ndarray) -> np.ndarray:
    arr = arr.astype(np.float32)
    min_val = float(arr.min())
    max_val = float(arr.max())
    if max_val - min_val < 1e-6:
        return np.zeros_like(arr, dtype=np.float32)
    return (arr - min_val) / (max_val - min_val)


def _layer_positions(count: int, x: int, y_top: int, y_bottom: int) -> list[tuple[int, int]]:
    if count == 1:
        return [(x, (y_top + y_bottom) // 2)]
    gap = (y_bottom - y_top) / (count - 1)
    return [(x, int(y_top + i * gap)) for i in range(count)]


def _sample_indices(total: int, display: int) -> np.ndarray:
    if total <= display:
        return np.arange(total, dtype=np.int64)
    return np.linspace(0, total - 1, num=display, dtype=np.int64)


def _describe_layers(model: MLP) -> str:
    parts = []
    for layer in model.net:
        if isinstance(layer, torch.nn.Linear):
            parts.append(f"Linear({layer.in_features}->{layer.out_features})")
        else:
            parts.append(layer.__class__.__name__)
    return " -> ".join(parts)


def _draw_network_frame(
    input_grid: np.ndarray,
    hidden_vec: np.ndarray,
    output_vec: np.ndarray,
    layer_info: str,
    display_hidden: int,
    hidden_total: int,
    highlight: str,
) -> Image.Image:
    width, height = 980, 540
    margin_top = 60
    margin_bottom = 40
    y_top = margin_top
    y_bottom = height - margin_bottom

    img = Image.new("RGB", (width, height), color=(18, 20, 24))
    draw = ImageDraw.Draw(img)

    x_input = 140
    x_hidden = 490
    x_output = 840

    input_rows, input_cols = input_grid.shape
    input_box_h = y_bottom - y_top
    input_cell = min(6, max(2, input_box_h // max(input_rows, 1)))
    input_width = input_cols * input_cell
    input_height = input_rows * input_cell
    input_x0 = x_input - input_width // 2
    input_y0 = (y_top + y_bottom - input_height) // 2

    hidden_positions = _layer_positions(display_hidden, x_hidden, y_top, y_bottom)
    output_positions = _layer_positions(len(output_vec), x_output, y_top, y_bottom)

    title = "Fully Connected Activation"
    draw.text((30, 20), title, fill=(235, 235, 235))
    draw.text((30, 42), layer_info, fill=(170, 170, 170))
    draw.text(
        (30, 64),
        f"Hidden shown: {display_hidden}/{hidden_total}",
        fill=(150, 150, 150),
    )

    # Draw sampled connections for legibility.
    conn_color = (70, 72, 78)
    input_sample_rows = range(0, input_rows, max(1, input_rows // 12))
    input_sample_cols = range(0, input_cols, max(1, input_cols // 12))
    hidden_sample_idx = range(0, display_hidden, max(1, display_hidden // 16))

    for r in input_sample_rows:
        for c in input_sample_cols:
            x0 = input_x0 + c * input_cell + input_cell // 2
            y0 = input_y0 + r * input_cell + input_cell // 2
            for idx in hidden_sample_idx:
                x1, y1 = hidden_positions[idx]
                draw.line((x0, y0, x1, y1), fill=conn_color, width=1)

    for idx in hidden_sample_idx:
        x0, y0 = hidden_positions[idx]
        for x1, y1 in output_positions:
            draw.line((x0, y0, x1, y1), fill=conn_color, width=1)

    # Input nodes
    input_norm = _normalize_array(input_grid)
    for r in range(input_rows):
        for c in range(input_cols):
            val = float(input_norm[r, c]) if highlight == "input" else 0.15
            brightness = int(40 + 200 * val)
            color = (brightness, brightness, brightness)
            x0 = input_x0 + c * input_cell
            y0 = input_y0 + r * input_cell
            draw.rectangle((x0, y0, x0 + input_cell - 1, y0 + input_cell - 1), fill=color)

    # Hidden nodes
    hidden_norm = _normalize_array(hidden_vec)
    for idx, (x, y) in enumerate(hidden_positions):
        val = float(hidden_norm[idx]) if highlight == "hidden" else 0.1
        brightness = int(50 + 180 * val)
        fill = (60, 140, brightness) if highlight == "hidden" else (80, 90, 100)
        draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=fill, outline=(40, 40, 40))

    # Output nodes
    output_norm = _normalize_array(output_vec)
    for idx, (x, y) in enumerate(output_positions):
        val = float(output_norm[idx]) if highlight == "output" else 0.1
        brightness = int(60 + 180 * val)
        fill = (brightness, 120, 60) if highlight == "output" else (100, 90, 80)
        draw.ellipse((x - 10, y - 10, x + 10, y + 10), fill=fill, outline=(40, 40, 40))
        draw.text((x + 14, y - 6), str(idx), fill=(210, 210, 210))

    return img


def _activation_gif(
    input_tensor: torch.Tensor,
    hidden: torch.Tensor,
    probs: np.ndarray,
    layer_info: str,
) -> str:
    input_arr = input_tensor.squeeze().cpu().numpy()
    hidden_arr = hidden.squeeze().cpu().numpy()
    probs_arr = probs.astype(np.float32)

    display_hidden = min(DISPLAY_HIDDEN_NEURONS, hidden_arr.shape[0])
    sampled_idx = _sample_indices(hidden_arr.shape[0], display_hidden)
    hidden_display = hidden_arr[sampled_idx]

    frames = [
        _draw_network_frame(
            input_arr,
            hidden_display,
            probs_arr,
            layer_info,
            display_hidden,
            hidden_arr.shape[0],
            "input",
        ),
        _draw_network_frame(
            input_arr,
            hidden_display,
            probs_arr,
            layer_info,
            display_hidden,
            hidden_arr.shape[0],
            "hidden",
        ),
        _draw_network_frame(
            input_arr,
            hidden_display,
            probs_arr,
            layer_info,
            display_hidden,
            hidden_arr.shape[0],
            "output",
        ),
    ]

    fd, path = tempfile.mkstemp(prefix="mnist_activation_", suffix=".gif")
    os.close(fd)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=500, loop=0)
    return path


def load_model(checkpoint_path: str, device: str) -> MLP:
    model = MLP().to(device)
    if checkpoint_path and os.path.isfile(checkpoint_path):
        load_checkpoint(model, checkpoint_path, device)
    else:
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
    model.eval()
    return model


def predict(image: Image.Image | np.ndarray | dict, checkpoint_path: str) -> tuple[dict, str]:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    try:
        model = load_model(checkpoint_path, device)
    except FileNotFoundError as exc:
        raise gr.Error(str(exc))
    x = preprocess_image(image).to(device)

    with torch.no_grad():
        flat = model.net[0](x)
        hidden = model.net[2](model.net[1](flat))
        logits = model.net[3](hidden)
        probs = torch.softmax(logits, dim=1).cpu().numpy()[0]

    layer_info = _describe_layers(model)
    gif_path = _activation_gif(x, hidden, probs, layer_info)
    return {str(i): float(probs[i]) for i in range(10)}, gif_path


def main() -> None:
    default_ckpt = os.path.expanduser(
        "~/.recognition_handwritten_digital/checkpoints/mlp.pt"
    )

    with gr.Blocks() as demo:
        gr.Markdown("# MNIST 手写数字识别\n画一个数字，模型会给出 0-9 的概率。")
        ckpt_state = gr.State(default_ckpt)
        with gr.Row():
            image_input = gr.Sketchpad(
                label="画板",
                height=280,
                width=280,
            )
            pred_output = gr.Label(num_top_classes=3, label="预测结果")
        predict_btn = gr.Button("预测")
        activation_output = gr.Image(label="神经元激活过程", type="filepath")

        predict_btn.click(
            fn=predict,
            inputs=[image_input, ckpt_state],
            outputs=[pred_output, activation_output],
        )

    demo.launch()


if __name__ == "__main__":
    main()
