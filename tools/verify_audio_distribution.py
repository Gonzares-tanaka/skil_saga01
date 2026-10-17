"""Reuse source/asset/SAVE/launcher audits and keep AUDIO PASS's own record."""
from pathlib import Path
from verify_legend_distribution import main

if __name__ == '__main__':
    main(Path(__file__).resolve().parents[1] / 'verification/audio_pass_packages.json')
