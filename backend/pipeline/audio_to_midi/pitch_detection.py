import numpy as np
import torch
import torchcrepe

from .config import CREPE_MODEL, FMIN, FMAX, HOP, SAMPLE_RATE
from .utils import get_device


def detect_pitch(
    harmonic: np.ndarray, original: np.ndarray, sr: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Run CREPE pitch detection on harmonic audio.

    Returns (times, frequencies, confidences).
    """
    device = get_device()
    audio_tensor = torch.tensor(harmonic, dtype=torch.float32).unsqueeze(0)

    # Try preferred device; fall back to CPU if it fails (e.g. MPS Viterbi bug)
    try:
        frequency, periodicity = torchcrepe.predict(
            audio_tensor,
            sr,
            hop_length=HOP,
            fmin=FMIN,
            fmax=FMAX,
            model=CREPE_MODEL,
            decoder=torchcrepe.decode.viterbi,
            return_periodicity=True,
            device=device,
            batch_size=1024,
        )
    except RuntimeError:
        if device != "cpu":
            print(f"[pitch_detection] {device} failed, falling back to CPU")
            frequency, periodicity = torchcrepe.predict(
                audio_tensor,
                sr,
                hop_length=HOP,
                fmin=FMIN,
                fmax=FMAX,
                model=CREPE_MODEL,
                decoder=torchcrepe.decode.viterbi,
                return_periodicity=True,
                device="cpu",
                batch_size=1024,
            )
        else:
            raise

    # Apply silence mask using original audio
    periodicity = torchcrepe.threshold.Silence(-60.0)(
        periodicity, audio_tensor, sr, HOP
    )

    frequency = frequency.squeeze(0).cpu().numpy()
    periodicity = periodicity.squeeze(0).cpu().numpy()

    times = np.arange(len(frequency)) * HOP / sr

    return times, frequency, periodicity
