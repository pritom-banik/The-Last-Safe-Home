# Methodology and demo limitations

The proposal describes a sequence of product-specific calibration, noise reduction, geometric correction, co-registration, AOI clipping, normalization, and change detection. Raw satellite values must not be subtracted blindly: processing depends on the sensor, product, and geophysical quantity.

This starter has no raster inputs, calibration, classifier, change mask, or ground-truth validation. Its polygon and dashboard metrics are illustrative interface fixtures. The displayed confidence and risk are not scientific estimates, official warnings, or actionable safety guidance.

Before implementing a real flood analysis, select a documented surface-water or SAR product and acquisition pair, define a validated detection method, account for clouds/quality masks and seasonal baselines where applicable, and test measured area against independent reference data.