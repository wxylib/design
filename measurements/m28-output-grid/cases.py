"""Source grids and target CRSs shared by the m28 scripts."""

SOURCES = {
    "world-0.5": ("EPSG:4326", [-180, 180, -90, 90], [720, 360]),
    "world-0.25-0to360": ("+proj=longlat +datum=WGS84 +lon_wrap=180", [0, 360, -90, 90], [1440, 720]),
    "antarctic-25km": ("EPSG:3031", [-6e6, 6e6, -6e6, 6e6], [480, 480]),
    "utm55s-10m": ("EPSG:32755", [499980, 609780, 5190220, 5300020], [10980, 10980]),
    "pacific-150to210": ("EPSG:4326", [150, 210, -60, -30], [240, 120]),
}

TARGETS = {
    "4326": "EPSG:4326",
    "3857": "EPSG:3857",
    "3031": "EPSG:3031",
    "laea-hobart": "+proj=laea +lat_0=-42.9 +lon_0=147.3 +datum=WGS84",
    "moll": "+proj=moll +datum=WGS84",
    "32755": "EPSG:32755",
}
