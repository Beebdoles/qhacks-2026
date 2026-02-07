import os

import torchaudio


def preprocess(input_path: str) -> str:
    """Convert audio to mono 16kHz WAV."""
    waveform, sr = torchaudio.load(input_path)

    # Convert to mono
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)

    # Resample to 16kHz
    if sr != 16000:
        resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=16000)
        waveform = resampler(waveform)

    out_dir = os.path.dirname(input_path)
    out_path = os.path.join(out_dir, "audio_16k.wav")
    torchaudio.save(out_path, waveform, 16000)
    return out_path
