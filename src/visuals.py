"""Shared colour palette and plotting theme for the Sonic Signature notebooks."""

import matplotlib as mpl
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap

PALETTE = {
    "spotify_green": "#1DB954",
    "forest": "#1A7F45",
    "sage": "#9BBF5A",
    "deep_forest": "#0F3D23",
    "mint": "#D8F3E3",
    "charcoal": "#2B2D2F",
    "muted_text": "#5F6B63",
    "grid": "#E3E8E4",
    "background": "#FBFCFA",
}

# Categorical series colours, used in this fixed order (never cycled past three).
SERIES_COLORS = [PALETTE["spotify_green"], PALETTE["forest"], PALETTE["sage"]]

# Correlations: charcoal (-1) -> light neutral (0) -> forest green (+1)
GREEN_DIVERGING = LinearSegmentedColormap.from_list(
    "green_diverging", ["#2B2D2F", "#7C8580", "#F2F3F1", "#6FCB8E", "#0F5C33"]
)
# Density: mint (few tracks) -> deep forest (many tracks)
GREEN_SEQUENTIAL = LinearSegmentedColormap.from_list(
    "green_sequential", ["#EEF8F1", "#A8DDB9", "#1DB954", "#1A7F45", "#0F3D23"]
)


def set_theme():
    """Apply the project's matplotlib/seaborn theme globally."""
    sns.set_style("ticks")
    mpl.rcParams.update({
        "figure.facecolor": PALETTE["background"],
        "axes.facecolor": PALETTE["background"],
        "savefig.facecolor": PALETTE["background"],
        "figure.dpi": 110,
        "axes.edgecolor": PALETTE["muted_text"],
        "axes.labelcolor": PALETTE["charcoal"],
        "axes.titlecolor": PALETTE["charcoal"],
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.labelsize": 10.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.prop_cycle": mpl.cycler(color=SERIES_COLORS),
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": PALETTE["grid"],
        "grid.linewidth": 0.8,
        "xtick.color": PALETTE["muted_text"],
        "ytick.color": PALETTE["muted_text"],
        "text.color": PALETTE["charcoal"],
        "lines.linewidth": 2,
        "legend.frameon": False,
        "font.size": 10.5,
    })
