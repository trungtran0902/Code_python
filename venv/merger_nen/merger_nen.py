import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, MultiPolygon
from shapely.validation import make_valid

# Load shapefile
shapefile_path = r'C:\Users\Admin Data\PycharmProjects\pythonProject1\venv\merger_nen\export_1.shp'
gdf = gpd.read_file(shapefile_path)

# Check and print invalid geometries before fixing
invalid_geometries = gdf[~gdf.is_valid]  # Filter invalid geometries
if not invalid_geometries.empty:
    print("Invalid geometries detected before fixing:")
    print(invalid_geometries)

# Attempt to fix invalid geometries using make_valid() and buffer(0)
gdf['geometry'] = gdf['geometry'].apply(lambda x: make_valid(x) if not x.is_valid else x)
gdf['geometry'] = gdf['geometry'].apply(lambda x: x.buffer(0) if not x.is_valid else x)

# Simplify geometry (if needed) by removing invalid or tiny polygons (optional)
gdf['geometry'] = gdf['geometry'].apply(lambda x: x.simplify(0.0001) if isinstance(x, Polygon) or isinstance(x, MultiPolygon) else x)

# Re-check invalid geometries after fixing
invalid_geometries = gdf[~gdf.is_valid]  # Re-check invalid geometries
if not invalid_geometries.empty:
    print("Still invalid geometries detected after fixing:")
    print(invalid_geometries)

# Keep only valid geometries
gdf = gdf[gdf.is_valid]  # Keep only valid geometries

# Apply additional checks to ensure polygons are well-formed (e.g., no polygons with fewer than 4 points)
gdf['geometry'] = gdf['geometry'].apply(lambda x: x if isinstance(x, Polygon) and len(x.exterior.coords) >= 4 else None)
gdf = gdf.dropna(subset=['geometry'])  # Drop invalid geometries (None)

# Check if any valid geometries remain
if gdf.empty:
    print("No valid geometries found after filtering.")
    exit()

# Extract the geometry (polygon)
boundary = gdf.geometry.union_all()

# Check if the boundary is a Polygon or MultiPolygon
if boundary.geom_type == 'GeometryCollection':
    # If the result is a GeometryCollection, we merge it into a MultiPolygon
    boundary = boundary.buffer(0)  # This helps resolve any issues and ensures it's a valid geometry

# Check if the boundary is a MultiPolygon and take the outermost boundary if it is
if boundary.geom_type == 'MultiPolygon':
    boundary = boundary.convex_hull

# Wrap the boundary in a GeoDataFrame to enable plotting
boundary_gdf = gpd.GeoDataFrame(geometry=[boundary], crs=gdf.crs)

# Plot the boundary using GeoDataFrame's plot() method
fig, ax = plt.subplots()
boundary_gdf.plot(ax=ax)

# Manually adjust the aspect ratio
ax.set_aspect('equal', adjustable='box')  # This ensures the aspect ratio is maintained correctly

# Show the plot
plt.show()

# Optionally, export the boundary to a new shapefile
boundary_gdf.to_file(r'C:\Users\Admin Data\PycharmProjects\pythonProject1\venv\merger_nen\outer_boundary.shp')

print("Boundary extraction complete. The boundary shapefile has been saved.")
