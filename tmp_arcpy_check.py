import sys
try:
    import arcpy
    print('ARCPY_OK')
    print(sys.executable)
    print(hasattr(arcpy, 'conversion'))
    print(hasattr(arcpy, 'ListFeatureClasses'))
except Exception as e:
    print(type(e).__name__)
    print(e)
