import folium
from folium.plugins import MarkerCluster
import pandas as pd

houseLocation = []
with open("Rental place coordinates.txt", "r") as file:
    for line in file:
        string = line.replace("\n", "")
        houseLocation.append([float(string.split(",")[0]), float(string.split(",")[1])])

real_estate_data = pd.read_csv("data1.csv")
real_estate_data['location'] = houseLocation

df = real_estate_data.drop_duplicates("href")

houseLocation = list(df.location)
priceList = list(df.price)
hrefList = list(df.href)
roomNumber = list(df['info'])
titleList = list(df.title)
address = list(df.address)

html = """
%s<br>
######################<br>
Address: %s<br>
######################<br>
Price: %s<br>
######################<br>
%s<br>
######################<br>
<a href="%s" target="_blank">Link to Kijiji</a>
"""

def color_selector(price):
    try:
        price = float(price.replace("$", "").replace(",", ""))
        if price < 100000.0:
            return "green"
        if price >= 100000.0 and price < 200000.0:
            return "blue"
        if price >= 200000.0 and price < 300000.0:
            return "purple"
        if price >= 300000.0 and price < 400000.0:
            return "orange"
        if price >= 400000.0:
            return "red"
    except:
        return "white"

map = folium.Map(location=[47.5669, -52.7067], zoom_start=13)

marker_cluster = MarkerCluster().add_to(map)

fg1 = folium.FeatureGroup(name="Real estate updated on 07/15/2019")
for i in range(len(houseLocation)):
    iframe = folium.IFrame(html=html % (titleList[i], address[i], priceList[i], roomNumber[i], hrefList[i]), width=300, height=350)
    folium.Marker(location=houseLocation[i], popup=folium.Popup(iframe),
                               icon=folium.Icon(color_selector(priceList[i]))).add_to(marker_cluster)

map.add_child(fg1)
map.add_child(folium.LayerControl())
map.save("index.html")
