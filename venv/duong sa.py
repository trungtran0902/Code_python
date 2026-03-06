import osmium

class MyHandler(osmium.SimpleHandler):
    def node(self, n):
        print("Node:", n)

    def way(self, w):
        print("Way:", w)

    def relation(self, r):
        print("Relation:", r)

handler = MyHandler()
reader = osmium.io.Reader("202401111158.pbf")
osmium.apply(reader, handler)
reader.close()