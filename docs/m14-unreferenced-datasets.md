# m14: What is missing - widely used datasets with no byte-reference index

Status: musing, 2026-10-21. A research survey, not a plan. It lists
widely used environmental datasets (ocean, sea ice, polar, reanalysis,
remote sensing) that are public but have neither a cloud-optimised copy
nor a published byte-reference index (kerchunk, VirtualiZarr, Icechunk or
an mdim-refs table), and ranks them by value and by how hard a harvest
would be. Anything here becomes work by being picked up into a numbered
document or [commit-criteria.md](commit-criteria.md). It is written to be
compared against an independent list built from years of maintaining a
local mirror of these collections.

## Summary

- The obvious global datasets are mostly covered. ERA5 (ARCO-ERA5,
  Earthmover's Icechunk on AWS, NCAR GDEX kerchunk), JRA-3Q (GDEX
  kerchunk), every Copernicus Marine product (ARCO Zarr in two chunk
  orientations), GEBCO (several COG copies), REMA, Copernicus DEM,
  Landsat and Sentinel are all cloud-native already. Re-referencing them
  adds provenance, not access.
- The gap is the polar and Southern Ocean middle: products that a
  working group downloads every day, that sit on an agency HTTPS server or
  THREDDS as one netCDF or GeoTIFF per day, and that nobody has indexed.
  The top of the list is the NOAA/NSIDC sea ice concentration CDR, the
  Bremen AMSR2 ASI 3.125 km and 6.25 km sea ice concentration, the full
  NOAA OISST v2.1 record, CCMP v3.1 winds, BedMachine Antarctica, and the
  OSI SAF sea ice records.
- Seven of these collections are already mirrored into anonymous,
  range-capable object storage at Pawsey (the `idea-*` buckets that the
  sooty package catalogues, 232,798 objects). The object keys keep the
  publisher's host and path, so one harvest over the mirror gives a table
  with two remap targets: the mirror for speed and the publisher for
  provenance. This is the cheapest place to start.
- Almost every candidate is chunked netCDF4/HDF5 or GeoTIFF, so the
  existing harvest path (BRAN, GHRSST) applies unchanged. The hard cases
  are not hard because of size; they are hard because of form: gzip- or
  zip-wrapped files (CAFE productivity, GEBCO zips), HDF4 (MODIS
  heritage), GRIB (AMPS), binned ocean colour (not a grid), OPeNDAP-only
  hosts (HYCOM), and login-gated hosts (Earthdata, AVISO FTP).
- Two shapes recur in every long record: an era switch (a product
  version or a near-real-time tail with a different file name and
  sometimes a different chunk shape), and small daily files. Both are
  already in the commit criteria's reminders ("time-concat + eras
  first"); this survey adds evidence for how often they occur.

## 1. Method and sources

- Starting inventory: the source definitions of the bowerbird/blueant
  configuration (`sources_*.R`, about 120 named sources across
  altimetry, sea ice, SST, ocean colour, reanalysis, topography and
  oceanographic climatologies), the file-pattern functions of raadfiles
  (about 35 collections in daily use by raadtools), and the bundled
  catalogue of the sooty package (24 logical datasets mirrored to
  object storage).
- For each candidate, a web check for a cloud-optimised copy (Zarr, COG,
  Icechunk) and for a published reference index (kerchunk JSON/Parquet,
  VirtualiZarr, Icechunk virtual, DMR++). Sources checked: the AWS Open
  Data Registry (including the NOAA NODD kerchunk collection), Planetary
  Computer, source.coop, Earthmover and the Icechunk sample datasets,
  NCAR GDEX, CEDA/JASMIN, Copernicus Marine ARCO, Pangeo catalogues and
  NASA Earthdata/PO.DAAC material.
- Not done: live HTTP range probes. The cloud environment this was
  written in refuses connections to nearly every publisher host
  (seaice.uni-bremen.de, data.remss.com, noaadata.apps.nsidc.org,
  downloads.psl.noaa.gov, thredds.met.no, ncei.noaa.gov, pangaea.de,
  projects.pawsey.org.au). Range support below is from known server
  behaviour and is marked "expected" until probed; a one-page probe
  script for an unrestricted machine is the obvious follow-up (sec 7).
- "Not found" means a search did not find one, not that none exists.
  Each "not found" is a claim to check against local knowledge.

## 2. What counts as missing

Three states, from least to most work:

| State | Meaning | Example |
|---|---|---|
| Covered | Cloud-native copy or published refs exist and are maintained | ERA5, CMEMS products, GEBCO COGs |
| Copy, no refs | Files sit in object storage (mirror or agency bucket) but nobody publishes an index over them | NOAA CDR sea ice on AWS NODD, the Pawsey mirror |
| Missing | Files only on a publisher server (HTTPS, THREDDS, FTP), no index | Bremen AMSR2 ASI, OSI SAF on thredds.met.no, CCMP on data.remss.com |

The second state is the most interesting for this project: no new
storage is needed, only a table.

## 3. Format classes and what each costs to harvest

| Class | Byte-referenceable as is? | Harvest path | Cost |
|---|---|---|---|
| netCDF4/HDF5, chunked + deflate | yes | HDF5 chunk index (VirtualiZarr HDF parser, kerchunk, GDAL raw block info) | low; proven on BRAN |
| netCDF4/HDF5, contiguous | yes, and the chunk grid can be chosen | split the one extent into virtual chunks | low; a nice property |
| netCDF classic (CDF-1/2/5) | yes, uncompressed; record variables interleave | offsets from the header; kerchunk netCDF3 | low |
| GeoTIFF, tiled or striped | yes | IFD tile/strip tables (async-tiff); predictor codecs exist | low; proven on GHRSST |
| raw binary grids (`.img`, `.bin`) | yes, uncompressed | arithmetic from a sidecar description | very low bytes, georef by hand |
| GRIB1/GRIB2 | per message | message scan (kerchunk grib2, cfgrib index) | medium; one message is one chunk |
| HDF4 / HDF-EOS2 | yes | HDF4 map files (h4mapwriter), VirtualiZarr HDF4 parser | medium; tooling is thin |
| gzip, bzip2 or zip-wrapped files | no (unless a zip member is stored) | transcode, or seekable-zstd re-wrap | high; it is a copy, not a ref |
| OPeNDAP / NCSS only | no bytes exposed | none; a copy is the only path | high |
| HDF5 compound or ragged (binned L3, Argo) | bytes yes, grid no | needs a non-grid reader | out of scope for the grid model |

## 4. Inventory

Columns: host and access; format and layout; size and cadence; what
exists already; harvest difficulty (L, M, H). "Mirror" means the Pawsey
`idea-*` copy catalogued by sooty.

### 4.1 Sea ice

| Dataset | Host and access | Format | Size, cadence | Exists | Diff |
|---|---|---|---|---|---|
| NOAA/NSIDC passive microwave SIC CDR (G02202 v5/v6) and NRT (G10016) | noaadata.apps.nsidc.org HTTPS anonymous; NSIDC Earthdata Cloud (login); AWS NODD `noaa-cdr-sea-ice-concentration-pds` | netCDF4, 25 km polar stereographic, one file per day per hemisphere | ~17,000 days per hemisphere since 1978; daily NRT | PolarWatch ERDDAP (a service, not bytes); NODD netCDF copy; no refs found | L |
| NSIDC-0051 / NSIDC-0081 NASA Team 25 km | NSIDC Earthdata (login); mirror | netCDF4 v2 | 15,448 days per hemisphere in the mirror; 0051 final then 0081 NRT tail | mirror only; no refs found | L |
| Bremen AMSR2 ASI 3.125 km and 6.25 km (and AMSR-E 2002-2011) | seaice.uni-bremen.de HTTPS anonymous | GeoTIFF, netCDF, HDF, per day per hemisphere | ~5,000 days; daily | mirror (Antarctic 3.125 km GeoTIFF, 4,791 days); no cloud copy or refs found | L |
| OSI SAF SIC CDR (OSI-450-a, OSI-430-a ICDR) | thredds.met.no (HTTPServer, OPeNDAP) | netCDF4, EASE2 25 km | 1978 onward, daily | a Copernicus Marine record exists; ARCO coverage to verify; no refs found | L |
| OSI SAF low-resolution ice drift; NSIDC-0116 Polar Pathfinder motion | thredds.met.no; NSIDC | netCDF4 | daily, decades | none found | L |
| Bremen SMOS thin ice | data.seaice.uni-bremen.de | GeoTIFF | 5,569 days north (mirror) | mirror only | L |
| ICESat-2 ATL20 gridded freeboard | NSIDC Earthdata Cloud (login) | HDF5 | monthly and daily grids | on-demand earthaccess virtualisation possible; nothing published found | M (auth) |
| Antarctic landfast ice (Fraser et al.) | AADC | netCDF | 2000-2018, 15-day | none found | L |

### 4.2 Sea surface temperature and winds

| Dataset | Host and access | Format | Size, cadence | Exists | Diff |
|---|---|---|---|---|---|
| NOAA OISST v2.1 daily | NCEI HTTPS; AWS NODD CDR bucket; mirror | netCDF4, one file per day, 0.25 deg | ~16,000 days since 1981; daily with a preliminary tail | 30-day pilot table in wxylib fixtures (m02); older Pangeo Forge Zarr (stale); no maintained full-record refs found | L |
| NOAA OISST v2 high-res yearly files (PSL) | downloads.psl.noaa.gov HTTPS, THREDDS | netCDF4, one file per year | 45 files | none found | L |
| GHRSST MUR v4.1 netCDF (PO.DAAC) | Earthdata Cloud (login) | netCDF4; chunk shape changes between eras | daily since 2002 | stale AWS Zarr; community kerchunk notebooks; this project's COG store covers the COG copy | M (eras) |
| CCMP v3.1 6-hourly 0.25 deg winds | data.remss.com HTTPS anonymous; PO.DAAC cloud (login); mirror | netCDF4, one file per day | 11,552 days in mirror (1993-2024) | none found | L |
| ERSST v5 | PSL HTTPS | netCDF, monthly | small | none; small enough not to need one | L, low value |

### 4.3 Reanalysis and weather

| Dataset | Host and access | Format | Size, cadence | Exists | Diff |
|---|---|---|---|---|---|
| NCEP/NCAR R1 and NCEP/DOE R2 | downloads.psl.noaa.gov HTTPS, THREDDS, FTP | netCDF4, one file per variable per year | decades, many variables | none found | L |
| AMPS (Antarctic Mesoscale Prediction System) | UCAR MMM HTTPS, rolling archive | GRIB2 | twice daily forecasts | none found | M (GRIB, rolling) |
| ERA5 | many | | | Covered (ARCO-ERA5, Earthmover Icechunk on AWS, GDEX kerchunk) | - |
| JRA-3Q | NCAR GDEX | GRIB | | Covered (GDEX kerchunk Parquet) | - |
| MERRA-2 | GES DISC Earthdata Cloud | netCDF4 | | community VirtualiZarr demos; nothing published found | M (auth) |

### 4.4 Ocean models, state estimates and climatologies

| Dataset | Host and access | Format | Size, cadence | Exists | Diff |
|---|---|---|---|---|---|
| B-SOSE / SOSE | sose.ucsd.edu HTTPS | netCDF, large per-variable files | multi-TB, fixed iterations | old Pangeo Zarr of SOSE on GCS (status unknown); no refs found | M (size, layout unknown) |
| ACCESS-OM2-01 and other COSIMA runs | NCI THREDDS | netCDF4 | very large | intake catalogues on NCI; no public refs found | L (same host as BRAN) |
| World Ocean Atlas 2018 / 2023 | NCEI HTTPS, THREDDS | netCDF | a few GB, static | none found | L, low value (small) |
| CARS2009 | CSIRO | netCDF | small, static | none found | L, low value |
| HYCOM GOFS 3.1 reanalysis | HYCOM THREDDS, mostly OPeNDAP/NCSS | netCDF via services | large | none found | H (no bytes) |
| Copernicus Marine (GLORYS, OSTIA, SLA, WAVERYS, BGC) | Copernicus Marine S3 | ARCO Zarr plus original files | | Covered (ARCO Zarr, time- and geo-chunked) | - |

### 4.5 Ocean colour and productivity

| Dataset | Host and access | Format | Size, cadence | Exists | Diff |
|---|---|---|---|---|---|
| NASA OB.DAAC L3 mapped (SeaWiFS, MODIS, VIIRS) | Earthdata Cloud (login) | netCDF4 | daily, 8-day, monthly since 1997 | PACE OCI L3 has a community Icechunk store on source.coop; heritage sensors none found | L (auth) |
| NASA L3 binned (ISIN bins) | Earthdata Cloud (login) | HDF5 compound, ragged rows | daily | none; not a grid | H (non-grid reader) |
| ESA OC-CCI v6 chlorophyll | oceancolour.org THREDDS; mirror (GeoTIFF) | netCDF4; GeoTIFF | daily since 1997 | CEDA hosts kerchunk for some CCI products; OC-CCI coverage to verify | L |
| Oregon State VGPM / CAFE productivity | HTTPS | gzip-wrapped HDF4 | monthly, 8-day | none | H (transcode) |

### 4.6 Topography and ice sheet geometry

| Dataset | Host and access | Format | Size, cadence | Exists | Diff |
|---|---|---|---|---|---|
| BedMachine Antarctica v3+ (NSIDC-0756) | NSIDC HTTPS and Earthdata Cloud (login) | one netCDF, 500 m | ~ a few GB, static | v1 community Zarr on GCS (Pangeo); current versions none found | L |
| IBCSO v2 | PANGAEA HTTPS | GeoTIFF per layer | static | none found | L |
| RTopo-2 | PANGAEA HTTPS | netCDF | static | none found | L |
| Smith and Sandwell global topography | topex.ucsd.edu HTTPS, FTP | raw big-endian int16, Mercator | one file per version | none | L bytes, M georef |
| GEBCO | BODC zip | netCDF/GeoTIFF in zip | yearly | Covered (several COG copies, incl. source.coop) | - |
| REMA, Copernicus DEM, SRTM | AWS | COG | | Covered (m10 measured two) | - |

### 4.7 Point and profile collections (outside the grid model)

Argo profiles (GDAC on HTTPS and an AWS bucket), the World Ocean
Database and animal tracking archives are widely used and mostly not
cloud-indexed, but they are ragged collections, not grids. They belong
with the point cloud work (m08), not here.

## 5. Ranking

Value is weighted toward how often the dataset is read by polar and
Southern Ocean work, how long the record is, and whether a table would
change how people read it (sections, time series at a point, match-ups).
Feasibility counts format class, host behaviour, auth and era switches.

| Rank | Dataset | Value | Feasibility | Why now |
|---|---|---|---|---|
| 1 | NOAA/NSIDC SIC CDR + NRT | very high | high | anonymous HTTPS and an AWS copy; tiny daily files are exactly where a table beats a file list |
| 2 | NOAA OISST v2.1 full record | very high | very high | the m02 pilot already scanned 30 days with the same code; extend to the record and keep the preliminary tail as an era |
| 3 | Bremen AMSR2 ASI 3.125 km (Antarctic) | high | high | GeoTIFF path proven on GHRSST; mirror exists; no other copy anywhere |
| 4 | CCMP v3.1 | high | high | anonymous HTTPS and mirror; netCDF4 daily |
| 5 | BedMachine Antarctica | high | high | one static file; a single table row set with a long life |
| 6 | OSI SAF SIC CDR and ice drift | high | medium-high | THREDDS HTTPServer like BRAN; check Copernicus Marine first |
| 7 | NASA Team 25 km (0051 then 0081) | medium-high | high | mirror exists; its 0051 to 0081 switch is a real era test |
| 8 | ESA OC-CCI chlorophyll | medium-high | medium | verify CEDA kerchunk coverage before building |
| 9 | NCEP R1/R2 | medium | high | yearly files, easy; value is legacy continuity |
| 10 | ACCESS-OM2-01 (COSIMA) | high | medium | same THREDDS host as BRAN; size and variable count are the cost |
| 11 | B-SOSE | high | medium-low | file layout unknown; large |
| 12 | AMPS | high (polar weather) | low-medium | GRIB, rolling archive |
| - | binned ocean colour, CAFE, HYCOM | high | low | form, not size, is the blocker (sec 3) |

## 6. Findings along the way

- **The mirror is a ready-made harvest target.** The sooty catalogue
  lists 232,798 objects in 24 logical datasets, all addressable as
  `https://projects.pawsey.org.au/<bucket>/<publisher host>/<publisher
  path>`. A table built over it can be remapped to the publisher URL with
  a prefix rewrite (the remap-at-publish rule already in use for BRAN and
  GHRSST).
- **Era switches are everywhere.** In the bundled catalogue, the
  25 km sea ice series is NSIDC-0051 for 15,033 days and NSIDC-0081 for
  the last 415; the sea level series is the multi-year product for
  11,208 days and the near-real-time product for the last 603. GHRSST
  MUR's PO.DAAC netCDF changes chunk shape between date ranges, which
  defeats a single kerchunk store. Era-aware concatenation is the common
  case, not an edge case.
- **Catalogue check.** In the sooty package's bundled (stale) catalogue,
  the `sealevel-sla-tif`, `sealevel-ugos-tif`, `sealevel-ugosa-tif`,
  `sealevel-vgos-tif` and `sealevel-vgosa-tif` datasets all resolve to the
  `err_*` files (11,717 rows each), which looks like a substring match on
  the variable name. Worth a check in the live catalogue.
- **Contiguous and raw arrays are a gift.** Uncompressed arrays (netCDF
  contiguous storage, raw `.img` grids) let a table choose its own chunk
  grid. A static grid like Smith and Sandwell or a contiguous BedMachine
  variable can be cut into whatever chunks the reader wants, with no
  copy.
- **Small daily files favour a table over a file list.** A 25 km sea ice
  day is well under a megabyte; one table row per chunk with a time
  column makes a 47-year point time series a single sorted scan of the
  table followed by one small range read per day.

## 7. Next steps, if picked up

1. Probe range support and CORS on the hosts in sec 4 from an
   unrestricted machine (HEAD, `Range: bytes=0-99`, `Accept-Ranges`,
   ACAO), and record the results in this document.
2. Harvest the NOAA/NSIDC CDR over the AWS NODD bucket and over the
   Pawsey mirror into one mdim-refs table with two remap targets; the
   same four views as m13. This would also be a first data point for
   commit criterion 2 from a third producer shape.
3. Extend the OISST pilot to the full record with the preliminary tail
   as a second era.
4. Bremen AMSR2 ASI 3.125 km GeoTIFF through the GHRSST harvest code.
5. Compare this list with the independent list from raadtools
   experience; record what each missed.

## 8. Open questions

- Should a table over a third-party mirror (Pawsey) be published, or
  only the publisher-remapped table? The mirror is faster and
  range-capable; the publisher is the citation.
- Login-gated hosts (Earthdata, AVISO): a table can be public while its
  bytes need credentials. Is that useful enough to publish, or does it
  only belong in-region?
- Where should a growing set of public tables live: source.coop under
  one organisation, alongside each mirror, or in a catalogue that points
  at many homes?
