import folium
import pandas as pd

real_estate_data = pd.read_csv("data1.csv")
houseLocation = [(latitude, longitude) for latitude, longitude in zip(
    list(real_estate_data.latitude), list(real_estate_data.longitude)
)]
real_estate_data['location'] = houseLocation
df = real_estate_data.drop_duplicates("href")

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

def change_to_number(string):
    try:
        price = float(string.replace("$", "").replace(",", ""))
    except:
        price = None
    return price
money = lambda x: change_to_number(x)
df["money"] = pd.DataFrame(df.price.apply(money))

price_level_list = []
price_level1 = df[df["money"] < 100000]  #green
price_level_list.append(price_level1)
price_level2 = df[(df.money>=100000) & (df.money<200000)]  #blue
price_level_list.append(price_level2)
price_level3 = df[(df.money>=200000) & (df.money<300000)]  #purple
price_level_list.append(price_level3)
price_level4 = df[(df.money>=300000) & (df.money<400000)]  #orange
price_level_list.append(price_level4)
price_level5 = df[(df.money>=400000)]  #red
price_level_list.append(price_level5)
price_unknown = df[(df.money.isnull())]  #white
price_level_list.append(price_unknown)

color_list = ["green", "blue", "purple", "orange", "red", "white"]
tag_list = ["< $100,000",
            "$100,000 - $200,000",
            "$200,000 - $300,000",
            "$300,000 - $400,000",
            "> $400,000",
            "Please contact"]

map = folium.Map(location=[47.5669, -52.7067], zoom_start=13)

for item in range(6):
    data = price_level_list[item]
    houseLocation = list(data.location)
    priceList = list(data.price)
    hrefList = list(data.href)
    roomNumber = list(data['info'])
    titleList = list(data.title)
    address = list(data.address)

    fg = folium.FeatureGroup(name=tag_list[item])
    for i in range(len(houseLocation)):
        iframe = folium.IFrame(html=html % (titleList[i], address[i], priceList[i], roomNumber[i], hrefList[i]), width=300, height=350)
        fg.add_child(folium.Marker(location=houseLocation[i], popup=folium.Popup(iframe),
                                   icon=folium.Icon(color=color_list[item])))
    map.add_child(fg)

map.add_child(folium.LayerControl())
# Real estates in St.John's with layers
map.save("index.html")
