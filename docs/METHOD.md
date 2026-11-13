# How The Last Safe Home works

This page explains, in plain words, how the map turns satellite images into a **Home Risk Score** and an
estimated number of **years until the river arrives**. Every number on the map is an estimate from satellite
data, not an engineering survey.

## 1. Where is the water?

**NISAR radar (2026).** NISAR is a radar satellite built by NASA and ISRO. Radar sends its own microwaves
and measures the echo, so it sees through clouds and monsoon rain. Calm water reflects the signal away from
the satellite and looks dark; land, crops and houses send more of it back and look brighter. For each NISAR
pass over the site (every 12 days since June 2026) we:

1. smooth out radar speckle with a 5 × 5 pixel median filter,
2. find the brightness that best separates dark and bright pixels (Otsu's method),
3. call everything darker than that *water*, and drop specks smaller than 10 pixels.

Fields of rice standing in water can look *brighter* than usual (the radar bounces off the water and then the
plant stems). We flag those pixels as **possible flooded vegetation**.

**Landsat (1988–2026).** For the long history we use Landsat images from the dry season (January–March) every
five years, starting in 1988. Clouds are removed, the remaining images are combined, and water is found with
the *MNDWI* index (water reflects green light but almost no short-wave infrared).

## 2. Where is the river bank?

From each water map we keep only the river (water that touches the edge of the study area or is larger than
1 km²; small ponds are ignored). The edge of the remaining land is the **bank line**. During the monsoon,
NISAR also maps flooded fields as water, so for bank lines NISAR water only counts as river within 300 m of
the dry-season river. Radar water maps change a little from pass to pass (tide, wind), so today's bank is the
**median of the last three NISAR passes**.

## 3. How fast is the bank moving?

We draw a baseline inside the land of 1988 and, every **100 m** along it, a line straight out towards the
river (a *transect*). On each transect we measure the distance from the baseline to the bank in every
Landsat year and to today's NISAR bank, and fit a straight line through those distances over time
(least squares). Its slope is the **retreat rate** in metres per year: positive means the river is eating
into the land, negative means the land is growing. The ± value is the statistical uncertainty of the slope.
A transect needs at least four dates to get a rate.

## 4. How often does it flood?

For every place that is not permanent river, **flood frequency** is the share of the 2026 NISAR passes in
which it was water. 0.5 means it was under water on half of the passes.

## 5. Is the ground moving?

NISAR can also measure tiny ground movements by comparing the radar *phase* of two passes 12 days apart
(interferometry). This only works where the ground looks the same in both images ("coherent"). Over wet
fields, mud and water it does not, so the result is shown as **low confidence**, and if less than 30 % of the
land is coherent over the season the layer is hidden and not used in the score.

## 6. The Home Risk Score

For any place on land we know: **D**, the distance to today's bank; **R ± σ**, the retreat rate of the nearest
transect; **F**, the flood frequency; and **M**, the ground movement.

- **Years until the river arrives**: T = D ÷ R (only if the bank is retreating). The range uses R + σ and R − σ.
  More than 50 years is shown as "over 50 years".
- **Erosion hazard** H_E is 1 if the river may arrive within 5 years, 0 if it needs 50 years or more, and in
  between on a logarithmic scale (about 0.5 at 16 years).
- **Flood hazard** H_F = F.
- **Movement hazard** H_G = |M| ÷ 30 mm, capped at 1.

Score = 100 × (0.6 · H_E + 0.3 · H_F + 0.1 · H_G). If ground movement cannot be used at a site, its weight
goes to the other two (0.667 and 0.333).

| Score | Class | What it means |
|---|---|---|
| 0–24 | Low | No sign of fast change here |
| 25–49 | Moderate | Watch this area each monsoon |
| 50–74 | High | Talk to your union parishad about plans |
| 75–100 | Severe | The river may reach here within a few years |

The same code computes the map colours and the numbers in the click card, so they always agree.

## 7. Buildings and people

Buildings, schools, hospitals and places of worship come from OpenStreetMap; people per 30 m pixel from
WorldPop's population estimates. The panels count them by risk class. Both sources miss some homes.

## 8. Data and references

- **NISAR** L2 GCOV (geocoded backscatter, HH and HV, 10 m) and GUNW (interferograms, 80 m), provisional
  products from 17 June 2026, from the Alaska Satellite Facility (ASF DAAC). One orbit track per site, so all
  dates look at the ground from the same angle.
- **Landsat 5, 7, 8 and 9** Collection 2 Level 2 surface reflectance (USGS), January–March of 1988, 1993, …,
  2023 and 2026, via Microsoft Planetary Computer.
- **Sentinel-2** L2A (ESA Copernicus), only to check the water maps.
- **OpenStreetMap** buildings and facilities, **WorldPop** 2025 population, **geoBoundaries** union boundaries.
- Methods: Otsu (1979) thresholding; MNDWI (Xu 2006); transect rates like the "linear regression rate" of the
  USGS Digital Shoreline Analysis System (Himmelstoss et al. 2021); the NISAR L2 GCOV and GUNW product
  specifications (NASA JPL).

## 9. How we check the maps

- **Land area against published studies**: the island's land area from our Landsat maps is compared with
  published values.
- **Against an optical image**: the river outline of a late NISAR pass is compared with a cloud-free
  Sentinel-2 image taken within a few days.
- **Hand-labelled points**: 200 random points (100 water, 100 land) are labelled by hand from Sentinel-2 and
  compared with the NISAR water map. Until that is done, the site is marked "not validated".

The live results for the selected site are below.
