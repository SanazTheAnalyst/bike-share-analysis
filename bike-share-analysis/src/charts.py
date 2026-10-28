"""Charts comparing members and casual riders. Each function saves a PNG to images/."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.bikeshare import DAY_ORDER

COLORS = {"member": "#2a78d6", "casual": "#eb6834"}
LABELS = {"member": "Members", "casual": "Casual riders"}
INK, MUTED, GRID, AXIS = "#1f1f1e", "#6b6a63", "#e1e0d9", "#c3c2b7"

plt.rcParams.update({
    "font.size": 11, "axes.edgecolor": AXIS, "axes.labelcolor": MUTED, "axes.titlecolor": INK,
    "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.8, "axes.axisbelow": True, "axes.spines.top": False,
    "axes.spines.right": False, "legend.frameon": False, "figure.dpi": 110,
})


def _save(fig, out_dir: Path, name: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.png"
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    return path


def _grouped_bars(ax, table: pd.DataFrame, width=0.38):
    """table: index = categories, columns = member/casual."""
    x = range(len(table))
    for i, rider in enumerate(["member", "casual"]):
        offset = (i - 0.5) * (width + 0.02)
        ax.bar([p + offset for p in x], table[rider], width=width, color=COLORS[rider],
               label=LABELS[rider])
    ax.set_xticks(list(x), table.index)
    ax.grid(axis="x", visible=False)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2)


def rides_by_day(df: pd.DataFrame, out_dir: Path) -> Path:
    table = (df.groupby(["day_of_week", "member_casual"], observed=False).size()
             .unstack().reindex(DAY_ORDER))
    table.index = [d[:3] for d in table.index]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    _grouped_bars(ax, table / 1000)
    ax.set_title("Members ride on weekdays, casual riders peak at the weekend", pad=28)
    ax.set_ylabel("Rides (thousands)")
    return _save(fig, out_dir, "rides_by_day")


def rides_by_hour(df: pd.DataFrame, out_dir: Path) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    for ax, weekend, title in zip(axes, [False, True], ["Weekdays", "Weekends"]):
        part = df[df["is_weekend"] == weekend]
        days = part["started_at"].dt.date.nunique()
        table = part.groupby(["hour", "member_casual"]).size().unstack().reindex(range(24), fill_value=0) / days
        for rider in ["member", "casual"]:
            ax.plot(table.index, table[rider], color=COLORS[rider], linewidth=2, label=LABELS[rider])
        ax.set_title(title)
        ax.set_xticks([0, 6, 12, 18, 23], ["0:00", "6:00", "12:00", "18:00", "23:00"])
        ax.set_xlabel("Hour of day")
    axes[0].set_ylabel("Average rides per day")
    axes[0].set_ylim(bottom=0)
    axes[0].legend(loc="upper left")
    fig.suptitle("Weekdays: members ride at commute times (8:00 and 17:00). Weekends: both groups ride late morning to evening",
                 x=0.06, ha="left", fontsize=12, color=INK)
    fig.tight_layout()
    return _save(fig, out_dir, "rides_by_hour")


def ride_duration(df: pd.DataFrame, out_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4.2))
    bins = range(0, 61, 2)
    for rider in ["member", "casual"]:
        s = df.loc[df["member_casual"] == rider, "ride_minutes"]
        ax.hist(s[s <= 60], bins=bins, weights=[1 / len(s)] * int((s <= 60).sum()), histtype="step", linewidth=2, color=COLORS[rider],
                label=f"{LABELS[rider]} (median {s.median():.0f} min)")
    ax.set_title("Casual riders take longer rides")
    ax.set_xlabel("Ride length in minutes (rides up to 60 min)")
    ax.set_ylabel("Share of all rides (2-minute bins)")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.legend(loc="upper right")
    return _save(fig, out_dir, "ride_duration")


def rides_by_month(df: pd.DataFrame, out_dir: Path) -> Path:
    table = df.groupby(["month", "member_casual"]).size().unstack().sort_index()
    growth = table.max() / table.min()
    table.index = pd.to_datetime(table.index).strftime("%b\n%Y")
    fig, ax = plt.subplots(figsize=(9, 4.4))
    _grouped_bars(ax, table / 1000)
    ax.set_title(f"From the quietest to the busiest month, casual rides grow {growth['casual']:.0f}x, "
                 f"member rides {growth['member']:.0f}x", pad=28)
    ax.set_ylabel("Rides (thousands)")
    return _save(fig, out_dir, "rides_by_month")


def top_stations(stations: pd.DataFrame, out_dir: Path) -> Path:
    s = stations.iloc[::-1]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.barh(s["start_station"], s["casual_rides"], color=COLORS["casual"], height=0.6)
    for y, v in enumerate(s["casual_rides"]):
        ax.annotate(f"{v:,}", (v, y), xytext=(4, 0), textcoords="offset points",
                    va="center", fontsize=9, color=INK)
    ax.grid(axis="y", visible=False)
    ax.set_title("Top 10 start stations for casual riders")
    ax.set_xlabel("Rides started by casual riders")
    return _save(fig, out_dir, "top_casual_stations")
