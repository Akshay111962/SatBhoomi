"""Offline fixture provider for zero-network testing and continuous integration."""

from datetime import timedelta

from satbhoomi.connectors.satellite.base import (
    NdviProvider,
    PlotLocation,
    RawObservation,
    SeasonWindow,
)


class FixtureNdviProvider(NdviProvider):
    """Deterministic offline fixture provider.

    Generates realistic Sentinel-2 5-day repeat cycle passes over the season window
    using an agricultural crop phenology curve (wheat sigmoid growth, peak, and senescence).
    """

    def __init__(
        self,
        force_cloudy: bool = False,
        inject_out_of_range: bool = False,
        fixed_observations: list[RawObservation] | None = None,
    ) -> None:
        """Initialize fixture provider with optional simulation overrides."""
        self.force_cloudy = force_cloudy
        self.inject_out_of_range = inject_out_of_range
        self.fixed_observations = fixed_observations

    @property
    def source_name(self) -> str:
        """Identifier for the fixture source."""
        return "fixture"

    def fetch_observations(
        self,
        plot: PlotLocation,
        window: SeasonWindow,
    ) -> list[RawObservation]:
        """Generate deterministic raw observations across the season window.

        Simulates Sentinel-2 5-day revisit cadence between window.start_date and window.end_date.
        """
        if self.fixed_observations is not None:
            return self.fixed_observations

        observations: list[RawObservation] = []
        current_date = window.start_date
        total_days = (window.end_date - window.start_date).days
        step_days = 5

        # Base potential peak NDVI depending on plot irrigation
        if plot.irrigation == "tube_well":
            max_ndvi = 0.76
        elif plot.irrigation == "canal":
            max_ndvi = 0.70
        else:
            max_ndvi = 0.52

        obs_index = 0
        while current_date <= window.end_date:
            progress = (current_date - window.start_date).days / max(1, total_days)

            # Wheat phenology: vegetative surge (0.15-0.45), peak heading (0.45-0.65),
            # and maturity/harvest (0.65-1.0)
            if progress < 0.20:
                # Early season (first ~30 days)
                ndvi = 0.18 + (progress / 0.20) * 0.15
            elif progress < 0.55:
                # Rapid vegetative growth toward heading
                frac = (progress - 0.20) / 0.35
                ndvi = 0.33 + frac * (max_ndvi - 0.33)
            elif progress < 0.75:
                # Peak heading & grain filling
                ndvi = max_ndvi - (progress - 0.55) * 0.10
            else:
                # Senescence & harvest
                frac = (progress - 0.75) / 0.25
                ndvi = (max_ndvi - 0.10) - frac * 0.35

            ndvi = round(max(0.10, min(0.95, ndvi)), 4)

            # Cloud simulation: every 6th observation is overcast/cloud-shadowed
            is_cloud = self.force_cloudy or (obs_index % 6 == 2)
            is_valid = not is_cloud
            scl_class = 8 if is_cloud else 4  # 8 = Cloud medium prob, 4 = Vegetation

            if self.inject_out_of_range and obs_index == 3:
                ndvi = 1.85  # Out-of-bounds trigger for validation tests

            observations.append(
                RawObservation(
                    date=current_date,
                    ndvi=ndvi,
                    is_valid=is_valid,
                    cloud_prob=85.0 if is_cloud else 5.0,
                    scl_class=scl_class,
                    scene_id=f"S2A_MSIL2A_{current_date.strftime('%Y%m%d')}_{plot.plot_code}",
                )
            )

            current_date += timedelta(days=step_days)
            obs_index += 1

        return observations
