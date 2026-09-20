"""Optional local MP3 analysis (requires miniaudio and numpy, not game dependencies)."""
import json
import sys
import miniaudio
import numpy as np

decoded = miniaudio.decode_file(sys.argv[1], output_format=miniaudio.SampleFormat.FLOAT32,
                               nchannels=1, sample_rate=22050)
samples = np.asarray(decoded.samples)
hop, size = 220, 2048
frames = np.lib.stride_tricks.sliding_window_view(samples, size)[::hop]
spectrum = abs(np.fft.rfft(frames * np.hanning(size)))
flux = np.maximum(np.diff(np.log1p(spectrum), axis=0), 0).sum(axis=1)
flux -= flux.mean()
lags = range(30, 100)
ranked = sorted(((float(np.dot(flux[:-lag], flux[lag:]) / len(flux[lag:])), lag)
                 for lag in lags), reverse=True)
print(json.dumps({"duration_seconds": round(len(samples) / 22050, 2),
                  "tempo_candidates_bpm": [round(60 * 22050 / hop / lag, 1) for _, lag in ranked[:6]],
                  "note": "Autocorrelation estimates, not an exact transcription."}, indent=2))
