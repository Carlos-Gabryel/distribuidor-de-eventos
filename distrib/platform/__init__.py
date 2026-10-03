"""Detecção de plataforma e adaptadores específicos (Android)."""
from __future__ import annotations

import os
import sys

IS_ANDROID = sys.platform == "android" or "ANDROID_DATA" in os.environ
