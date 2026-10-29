# src/etl/load/plot_ch_runoff_curve.py
import os
import sys
from typing import Any, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.config.settings import load_config
from src.etl.transform.runoff_markov import scs_lumped, runoff_matrix


def plot_ch_runoff_curve(config: Optional[Any], out_path: str) -> str:
    """Generate the 'Kurva CH-Run off' plot comparing lumped monthly SCS-CN vs Event-Based SCS-CN."""
    if config is None:
        config = load_config()

    cn = config.runoff.curve_number

    pp = np.linspace(0, 450, 226)
    fig, a = plt.subplots(figsize=(7, 5))
    a.plot(pp, scs_lumped(pp, cn=cn), color="gray", ls=":", label="SCS-CN langsung bulanan (lama)")
    a.plot(pp, runoff_matrix(pp, cn=cn), color="#9467bd", lw=2, label="SCS-CN berbasis kejadian (baru)")
    a.set_xlabel("Curah hujan bulanan (mm)")
    a.set_ylabel("Run off bulanan (mm)")
    a.set_title(f"Kurva CH-Run off (CN={cn:g})")
    a.grid(alpha=0.3)
    a.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path
