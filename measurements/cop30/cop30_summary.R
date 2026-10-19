# cop30_summary.R
# Summarize the COP30 sources from the OpenTopography VRT's own source
# table - one XML download, no COG requests. The VRT already records every
# child's dimensions (SrcRect), placement (DstRect), and name (lat/lon),
# which is the shareable table of the COGs. A small optional sample at the
# end touches ~a dozen COG headers for the codec/registration questions the
# VRT cannot answer.

vrt_url  <- "https://opentopography.s3.sdsc.edu/raster/COP30/COP30_hh.vrt"
vrt_file <- "COP30_hh.vrt"
if (!file.exists(vrt_file)) curl::curl_download(vrt_url, vrt_file)

x  <- xml2::read_xml(vrt_file)
gt <- as.numeric(strsplit(xml2::xml_text(
        xml2::xml_find_first(x, ".//GeoTransform")), ",")[[1]])

src <- xml2::xml_find_all(x, ".//SimpleSource|.//ComplexSource")
ga  <- function(rect, at) as.numeric(xml2::xml_attr(
         xml2::xml_find_first(src, paste0(".//", rect)), at))

cogs <- data.frame(
  filename  = xml2::xml_text(xml2::xml_find_first(src, ".//SourceFilename")),
  src_w = ga("SrcRect", "xSize"), src_h = ga("SrcRect", "ySize"),
  dst_xoff = ga("DstRect", "xOff"), dst_yoff = ga("DstRect", "yOff"),
  dst_w = ga("DstRect", "xSize"), dst_h = ga("DstRect", "ySize")
)
cogs$ratio_x <- cogs$dst_w / cogs$src_w
## placement in degrees from DstRect against the VRT geotransform
cogs$lon <- gt[1] + cogs$dst_xoff * gt[2]
cogs$lat <- gt[4] + cogs$dst_yoff * gt[6]

arrow::write_parquet(cogs, "cop30_sources.parquet")   # the shareable table
str(cogs); nrow(cogs)

## ---- 1. the N+1 census (SRTM-convention check) ----------------------------
## Expect src_h 3601 everywhere, src_w in {3601, 2401, 1801, 1201, 721, 361}.

print(table(cogs$src_w, cogs$src_h))

## ---- 2. band census by latitude -------------------------------------------

band <- cut(cogs$lat, c(-90, -85, -80, -70, -60, -50, 50, 60, 70, 80, 85))
print(table(cogs$src_w, band))

## ---- 3. what the VRT bakes in ---------------------------------------------
## DstRect/SrcRect = the resampling ratio materialized in the index.
## Expect ~ {1, 1.5, 2, 3, 5, 10}, matching the bands.

print(table(round(cogs$ratio_x, 3), band))

## ---- 4. sparsity, extent, antimeridian ------------------------------------

nrow(cogs); 360 * 174; nrow(cogs) / (360 * 174)
print(range(cogs$lon)); print(range(cogs$lat))
print(table(floor(cogs$lon) %in% c(-180, 179)))        # seam columns present?

## ---- 5. optional sample: codec + registration (about a dozen requests) ----
## The two things the VRT cannot say: how tiles decode, and where the raw
## tiepoints sit. One or two files per distinct width covers it.

if (FALSE) {
  base <- dirname(vrt_url)
  pick <- do.call(rbind, lapply(split(cogs, cogs$src_w), head, 2))
  urls <- file.path(base, pick$filename)
  s <- rustycogs::tiff_ifd_info(dsn::unvsicurl(urls))
  print(unique(s[c("is_tiled", "tile_w", "tile_h", "dtype", "compression",
                   "predictor", "bits_per_sample", "photometric",
                   "planar_configuration", "gdal_nodata")]))
  s0 <- subset(s, ifd == 0)
  print(s0[c("image_w", "origin_x", "origin_y", "scale_x")])
  print(table(round((s0$origin_x %% 1) * 7200)))  # 0 = point tiepoint on the degree

  ## the two-distribution check: same logical tile, AWS vs OpenTopography
  aws <- paste0("https://copernicus-dem-30m.s3.amazonaws.com/",
                "Copernicus_DSM_COG_10_N73_00_W030_00_DEM/",
                "Copernicus_DSM_COG_10_N73_00_W030_00_DEM.tif")
  ot  <- file.path(base, grep("N73_00_W030", cogs$filename, value = TRUE))
  print(rustycogs::tiff_ifd_info(dsn::unvsicurl(c(ot, aws)))[
    , c("path", "ifd", "image_w", "image_h", "compression", "predictor",
        "origin_x", "origin_y")])
}
