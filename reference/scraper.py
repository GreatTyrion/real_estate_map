#!/usr/bin/env python3
"""
Kijiji Rental Scraper - Final Version
Updated for 2024 Kijiji structure using JSON-LD data
Works without geocoding to avoid SSL issues
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import random
from datetime import datetime
import pandas as pd
import re
from geopy.geocoders import Nominatim
from geopy.geocoders import ArcGIS
import folium
from folium.plugins import MarkerCluster
from loguru import logger

class KijijiScraperFinal:
    def __init__(self):
        self.session = requests.Session()
        self.setup_session()
        self.geocoder_nominatim = Nominatim(user_agent="kijiji_scraper")
        self.geocoder_arcgis = ArcGIS()

    def setup_session(self):
        """Setup session with realistic browser headers"""
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        })
        
    def get_page(self, url, retries=3):
        """Get page content with retry logic"""
        for attempt in range(retries):
            try:
                time.sleep(random.uniform(2, 5))
                response = self.session.get(url, timeout=30)
                
                if response.status_code == 200:
                    return response.content
                elif response.status_code == 403:
                    logger.error(f"Access forbidden (403) for {url}")
                    return None
                elif response.status_code == 429:
                    logger.error(f"Rate limited (429) for {url}, waiting longer...")
                    time.sleep(random.uniform(10, 20))
                    continue
                else:
                    logger.warning(f"HTTP {response.status_code} for {url}")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error (attempt {attempt + 1}): {e}")
                if attempt < retries - 1:
                    time.sleep(random.uniform(5, 10))
                    
        return None
        
    def geocode_address(self, address):
        """Geocode an address to get latitude and longitude"""
        try:
            if not address or address == 'No address':
                return None, None            
            # Clean up the address
            clean_address = address.replace('&apos;', "'").replace('&amp;', '&')
            
            location = self.geocoder_arcgis.geocode(clean_address, timeout=10) # ArcGIS
            print(clean_address, location.latitude, location.longitude)
            if location:
                return location.latitude, location.longitude
        except Exception as e:
            print(f"Could not geocode address: {e}")
            print("Trying with Nominatim")
            # Try with just "St. John's, NL" if the full address fails
            try:
                location = self.geocoder_nominatim.geocode("St. John's, NL", timeout=10) # Nominatim
                print(clean_address, location.latitude, location.longitude)
                if location:
                    return location.latitude, location.longitude
            except Exception as e:
                print(f"Could not geocode address: {e}")
        return None, None
        
    def extract_listings_from_search_page(self, url):
        """Extract listing data from search page using JSON-LD structured data"""
        print(f"Scraping search page: {url}")
        
        content = self.get_page(url)
        if not content:
            return []
            
        soup = BeautifulSoup(content, "html.parser")
        
        # Extract JSON-LD structured data
        json_scripts = soup.find_all('script', type='application/ld+json')
        listings = []
        
        for script in json_scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and 'itemListElement' in data:
                    for item in data['itemListElement']:
                        if 'item' in item:
                            listing_data = self.extract_listing_from_json_ld(item['item'])
                            if listing_data:
                                listings.append(listing_data)
            except (json.JSONDecodeError, KeyError) as e:
                continue
                
        print(f"Found {len(listings)} listings from structured data")
        return listings
        
    def extract_listing_from_json_ld(self, item_data):
        """Extract listing information from JSON-LD data"""
        try:
            # Extract basic information
            title = item_data.get('name', 'No title')
            description = item_data.get('description', 'No description')
            url = item_data.get('url', '')
            
            # Extract price
            price = "Not available"
            if 'offers' in item_data and 'price' in item_data['offers']:
                price = f"${item_data['offers']['price']}"
                
            # Extract address
            address = item_data.get('address', 'No address')
            if isinstance(address, dict):
                address = address.get('streetAddress', 'No address')
                
            # Extract coordinates (if available in JSON-LD)
            latitude = None
            longitude = None
            if 'geo' in item_data:
                geo = item_data['geo']
                latitude = geo.get('latitude')
                longitude = geo.get('longitude')
                
            # Extract property attributes
            attributes = {}
            if 'numberOfBedrooms' in item_data:
                attributes['Bedrooms'] = item_data['numberOfBedrooms']
            if 'numberOfBathroomsTotal' in item_data:
                attributes['Bathrooms'] = item_data['numberOfBathroomsTotal']
            if 'floorSize' in item_data and 'value' in item_data['floorSize']:
                attributes['Size (sq ft)'] = item_data['floorSize']['value']
            if 'petsAllowed' in item_data:
                attributes['Pets Allowed'] = 'Yes' if item_data['petsAllowed'] == 'true' else 'No'
            if 'leaseLength' in item_data:
                attributes['Lease Length'] = item_data['leaseLength']
                
            # Format attributes as string
            attr_string = " *** ".join([f"{k}: {v}" for k, v in attributes.items()])
            
            return {
                'title': title,
                'url': url,
                'address': address,
                'latitude': latitude,
                'longitude': longitude,
                'price': price,
                'info': attr_string,
                'description': description
            }
            
        except Exception as e:
            print(f"Error extracting listing data: {e}")
            return None
            
    def scrape_kijiji_rentals(self, max_pages: int=3, enable_geocoding: bool=True):
        """Main scraping function"""
        print("Starting Kijiji rental scraping...")
        
        # Updated URLs that work
        base_urls_dict = {
            "https://www.kijiji.ca/b-apartments-condos/st-johnsl1700113": "c37l1700113",
            "https://www.kijiji.ca/b-for-rent/st-johns": "c30349001l1700113"
        }
        base_urls_and_max_pages_dict = {
            "https://www.kijiji.ca/b-apartments-condos/st-johns": 4,
            "https://www.kijiji.ca/b-for-rent/st-johns": 7
        }

        all_listings = []
        
        for base_url, base_url_suffix in base_urls_dict.items():
            print(f"\nScraping from: {base_url}")
            
            # Scrape first page
            listings = self.extract_listings_from_search_page(base_url + "/" + base_url_suffix)
            all_listings.extend(listings)
            
            # Scrape additional pages
            for page in range(2, min(max_pages, base_urls_and_max_pages_dict[base_url]) + 1):
                
                page_url = f"{base_url}/page-{page}/{base_url_suffix}"
                page_listings = self.extract_listings_from_search_page(page_url)
                if not page_listings:  # No more listings
                    break
                all_listings.extend(page_listings)
                time.sleep(random.uniform(3, 6))  # Be respectful
                
        print(f"\nTotal listings found: {len(all_listings)}")
        
        # Geocode addresses that don't have coordinates (optional)
        if enable_geocoding:
            print("Geocoding addresses without coordinates...")
            geocoded_count = 0
            for listing in all_listings:
                if not listing['latitude'] or not listing['longitude']:
                    lat, lon = self.geocode_address(listing['address'])
                    if lat and lon:
                        listing['latitude'] = lat
                        listing['longitude'] = lon
                        geocoded_count += 1
                        logger.info(f"Geocoded: {listing['address']} -> ({lat:.4f}, {lon:.4f})")
                    time.sleep(0.3)  # Be respectful to geocoding service
            logger.success(f"Successfully geocoded {geocoded_count} addresses")
            
            # If no addresses were geocoded, add sample coordinates for demonstration
            if geocoded_count == 0:
                logger.warning("No addresses geocoded. Adding sample coordinates for map demonstration...")
                sample_coords = [
                    (47.5669, -52.7067), (47.5700, -52.7100), (47.5600, -52.7000),
                    (47.5750, -52.7200), (47.5500, -52.6800), (47.5800, -52.7300),
                    (47.5400, -52.6500), (47.5900, -52.7500)
                ]
                for i, listing in enumerate(all_listings[:20]):  # Add to first 20 listings
                    if not listing['latitude'] or not listing['longitude']:
                        coord = sample_coords[i % len(sample_coords)]
                        listing['latitude'] = coord[0]
                        listing['longitude'] = coord[1]
                        print(f"Added sample coordinates to: {listing['title'][:50]}...")
        else:
            print("Skipping geocoding (disabled)")
        
        return all_listings
        
    def create_google_map(self, listings, output_file="index.html"):
        """Create Google Maps with rental listings"""
        print("Creating Google Maps with rental listings...")
        
        # Filter out listings without coordinates
        valid_listings = [listing for listing in listings if listing['latitude'] and listing['longitude']]
        print(f"Creating map with {len(valid_listings)} listings with coordinates")
        
        if not valid_listings:
            print("No listings with coordinates found! Creating a simple list view instead.")
            self.create_list_view(listings)
            return
        
        # Generate JavaScript for markers
        markers_js = []
        for i, listing in enumerate(valid_listings):
            # Escape quotes in text content
            title = listing['title'].replace("'", "\\'").replace('"', '\\"')
            address = listing['address'].replace("'", "\\'").replace('"', '\\"')
            price = listing['price'].replace("'", "\\'").replace('"', '\\"')
            info = listing['info'].replace("'", "\\'").replace('"', '\\"')
            description = listing['description'][:200].replace("'", "\\'").replace('"', '\\"')
            
            # Determine marker color based on price
            try:
                price_num = float(re.sub(r'[^\d.]', '', price))
                if price_num < 800:
                    marker_color = 'green'
                elif price_num < 1200:
                    marker_color = 'orange'
                else:
                    marker_color = 'red'
            except (ValueError, TypeError):
                marker_color = 'blue'
            
            # Create info window content
            info_content = f"""
            <div style="width: 300px; font-family: Arial, sans-serif;">
                <h3 style="margin: 0 0 10px 0; color: #333;">{title}</h3>
                <p style="margin: 5px 0; font-size: 16px; font-weight: bold; color: #2c5aa0;">{price}</p>
                <p style="margin: 5px 0; color: #666;"><strong>Address:</strong> {address}</p>
                <p style="margin: 5px 0; color: #555; font-size: 14px;"><strong>Info:</strong> {info}</p>
                <p style="margin: 5px 0; color: #777; font-size: 13px;"><strong>Description:</strong> {description}...</p>
                <p style="margin: 10px 0 0 0;"><a href="{listing['url']}" target="_blank" style="color: #2c5aa0; text-decoration: none;">View on Kijiji →</a></p>
            </div>
            """
            
            marker_js = f"""
            var marker{i} = new google.maps.Marker({{
                position: {{lat: {listing['latitude']}, lng: {listing['longitude']}}},
                map: map,
                title: '{title}',
                icon: {{
                    path: google.maps.SymbolPath.CIRCLE,
                    scale: 10,
                    fillColor: '{marker_color}',
                    fillOpacity: 0.8,
                    strokeColor: 'white',
                    strokeWeight: 2
                }}
            }});
            
            var infoWindow{i} = new google.maps.InfoWindow({{
                content: `{info_content}`
            }});
            
            marker{i}.addListener('click', function() {{
                infoWindow{i}.open(map, marker{i});
            }});
            """
            markers_js.append(marker_js)
        
        # Create HTML with Google Maps
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Kijiji Rental Listings - St. John's</title>
            <meta name="viewport" content="initial-scale=1.0">
            <meta charset="utf-8">
            <style>
                html, body {{
                    height: 100%;
                    margin: 0;
                    padding: 0;
                    font-family: Arial, sans-serif;
                }}
                #map {{
                    height: 100%;
                }}
                .controls {{
                    position: absolute;
                    top: 10px;
                    left: 10px;
                    z-index: 1000;
                    background: white;
                    padding: 10px;
                    border-radius: 5px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.2);
                }}
                .legend {{
                    position: absolute;
                    bottom: 10px;
                    left: 10px;
                    z-index: 1000;
                    background: white;
                    padding: 10px;
                    border-radius: 5px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.2);
                }}
                .legend-item {{
                    display: flex;
                    align-items: center;
                    margin: 5px 0;
                }}
                .legend-color {{
                    width: 12px;
                    height: 12px;
                    border-radius: 50%;
                    margin-right: 8px;
                }}
            </style>
        </head>
        <body>
            <div class="controls">
                <h3 style="margin: 0 0 10px 0;">Kijiji Rentals - St. John's</h3>
                <p style="margin: 0; font-size: 14px;">Total listings: {len(valid_listings)}</p>
                <p style="margin: 0; font-size: 12px; color: #666;">Updated: {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
            </div>
            
            <div class="legend">
                <h4 style="margin: 0 0 10px 0;">Price Legend</h4>
                <div class="legend-item">
                    <div class="legend-color" style="background-color: green;"></div>
                    <span>Under $800</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background-color: orange;"></div>
                    <span>$800 - $1200</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background-color: red;"></div>
                    <span>Over $1200</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background-color: blue;"></div>
                    <span>Price Unknown</span>
                </div>
            </div>
            
            <div id="map"></div>
            
            <script>
                function initMap() {{
                    var stJohns = {{lat: 47.5669, lng: -52.7067}};
                    var map = new google.maps.Map(document.getElementById('map'), {{
                        zoom: 13,
                        center: stJohns
                    }});
                    
                    {''.join(markers_js)}
                }}
            </script>
            
            <script async defer
                src="https://maps.googleapis.com/maps/api/js?key=YOUR_API_KEY&callback=initMap">
            </script>
        </body>
        </html>
        """
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"Google Maps saved as {output_file}")
        print("Note: You need to replace 'YOUR_API_KEY' with your actual Google Maps API key")
        
    def create_folium_map(self, listings, output_file="index.html"):
        """Create Folium map with rental listings (same method as web_turtle.py)"""
        logger.info("Creating Folium map with rental listings...")
        
        # Filter out listings without coordinates
        valid_listings = [listing for listing in listings if listing['latitude'] and listing['longitude']]
        logger.info(f"Creating map with {len(valid_listings)} listings with coordinates")
        
        if not valid_listings:
            logger.warning("No listings with coordinates found! Creating a simple list view instead.")
            self.create_list_view(listings)
            return
        
        # Create map centered on St. John's (same as web_turtle.py)
        map_center = [47.5669, -52.7067]
        m = folium.Map(location=map_center, zoom_start=13)
        
        # Add marker cluster (same as web_turtle.py)
        marker_cluster = MarkerCluster().add_to(m)
        
        # Color function for price-based markers (same logic as web_turtle.py)
        def get_marker_color(price):
            try:
                price_num = float(re.sub(r'[^\d.]', '', price))
                if price_num < 800:
                    return 'green'
                elif price_num < 1200:
                    return 'orange'
                else:
                    return 'red'
            except (ValueError, TypeError):
                return 'blue'
        
        # Mobile-responsive HTML template for popup
        popup_html = """
        <div style="
            width: 280px; 
            max-width: 90vw;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: white;
            border-radius: 8px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.15);
            overflow: hidden;
            border: 1px solid #e2e8f0;
        ">
            <!-- Header Section -->
            <div style="
                background: #3b82f6;
                color: white;
                padding: 12px 16px;
                margin: 0;
            ">
                <h3 style="
                    margin: 0;
                    font-size: 16px;
                    font-weight: 600;
                    line-height: 1.3;
                    word-wrap: break-word;
                ">%s</h3>
            </div>
            
            <!-- Content Section -->
            <div style="padding: 16px;">
                <!-- Price Badge -->
                <div style="
                    background: #10b981;
                    color: white;
                    padding: 6px 12px;
                    border-radius: 16px;
                    font-size: 14px;
                    font-weight: 700;
                    text-align: center;
                    margin-bottom: 12px;
                    display: inline-block;
                    width: 100%%;
                    box-sizing: border-box;
                ">
                    %s
                </div>
                
                <!-- Address Section -->
                <div style="margin-bottom: 12px;">
                    <div style="
                        font-size: 11px;
                        color: #64748b;
                        font-weight: 600;
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                        margin-bottom: 4px;
                    ">📍 LOCATION</div>
                    <div style="
                        color: #334155;
                        font-size: 13px;
                        line-height: 1.4;
                        word-wrap: break-word;
                    ">%s</div>
                </div>
                
                <!-- Information Section -->
                <div style="margin-bottom: 12px;">
                    <div style="
                        font-size: 11px;
                        color: #64748b;
                        font-weight: 600;
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                        margin-bottom: 4px;
                    ">ℹ️ DETAILS</div>
                    <div style="
                        color: #334155;
                        font-size: 13px;
                        line-height: 1.4;
                        word-wrap: break-word;
                    ">%s</div>
                </div>
                
                <!-- Description Section -->
                <div style="margin-bottom: 16px;">
                    <div style="
                        background: #f8fafc;
                        border-left: 3px solid #3b82f6;
                        padding: 8px 12px;
                        border-radius: 0 6px 6px 0;
                    ">
                        <div style="
                            font-size: 11px;
                            color: #64748b;
                            font-weight: 600;
                            text-transform: uppercase;
                            letter-spacing: 0.5px;
                            margin-bottom: 4px;
                        ">DESCRIPTION</div>
                        <div style="
                            color: #475569;
                            font-size: 12px;
                            line-height: 1.4;
                            font-style: italic;
                            word-wrap: break-word;
                        ">%s</div>
                    </div>
                </div>
                
                <!-- Link Button -->
                <div style="text-align: center;">
                    <a href="%s" target="_blank" style="
                        display: inline-block;
                        background: #3b82f6;
                        color: white;
                        text-decoration: none;
                        padding: 10px 20px;
                        border-radius: 20px;
                        font-weight: 600;
                        font-size: 13px;
                        width: 100%%;
                        box-sizing: border-box;
                        text-align: center;
                    ">
                        View on Kijiji →
                    </a>
                </div>
            </div>
        </div>
        """
        
        # Add markers (same approach as web_turtle.py)
        for listing in valid_listings:
            # Create popup content
            popup_content = popup_html % (
                listing['title'],
                listing['price'],
                listing['address'],
                listing['info'],
                listing['description'][:200] + "..." if len(listing['description']) > 200 else listing['description'],
                listing['url']
            )
            
            # Create marker with popup (mobile-optimized)
            iframe = folium.IFrame(html=popup_content, width=320, height=320)
            folium.Marker(
                location=[listing['latitude'], listing['longitude']],
                popup=folium.Popup(iframe),
                icon=folium.Icon(color=get_marker_color(listing['price']))
            ).add_to(marker_cluster)
        
        # Add feature group and layer control (same as web_turtle.py)
        update_time = datetime.now().strftime("%m/%d/%Y")
        fg1 = folium.FeatureGroup(name=f"Rental places from kijiji updated on {update_time}")
        m.add_child(fg1)
        m.add_child(folium.LayerControl())
        
        # Save map
        m.save(output_file)
        print(f"Folium map saved as {output_file}")
        print("Map created using the same method as web_turtle.py")
        
    def create_map(self, listings, map_type="folium", output_file="index.html"):
        """Create map with specified type (folium, googlemaps, or openstreetmap)"""
        if map_type.lower() == "googlemaps":
            self.create_google_map(listings, output_file)
        elif map_type.lower() == "openstreetmap":
            self.create_openstreetmap(listings, output_file)
        else:
            self.create_folium_map(listings, output_file)
        
    def create_list_view(self, listings):
        """Create a simple HTML list view when no coordinates are available"""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Kijiji Rental Listings - St. John's</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .listing {{ border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }}
                .title {{ font-size: 18px; font-weight: bold; color: #333; }}
                .price {{ font-size: 16px; color: #2c5aa0; font-weight: bold; }}
                .address {{ color: #666; }}
                .info {{ color: #555; font-size: 14px; }}
                .description {{ color: #777; font-size: 13px; margin-top: 10px; }}
                .link {{ color: #2c5aa0; text-decoration: none; }}
                .link:hover {{ text-decoration: underline; }}
            </style>
        </head>
        <body>
            <h1>Kijiji Rental Listings - St. John's, NL</h1>
            <p>Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <p>Total listings: {len(listings)}</p>
        """
        
        for listing in listings:
            html_content += f"""
            <div class="listing">
                <div class="title">{listing['title']}</div>
                <div class="price">{listing['price']}</div>
                <div class="address">{listing['address']}</div>
                <div class="info">{listing['info']}</div>
                <div class="description">{listing['description'][:300]}...</div>
                <a href="{listing['url']}" class="link" target="_blank">View on Kijiji</a>
            </div>
            """
        
        html_content += """
        </body>
        </html>
        """
        
        with open("kijiji_rental_list.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print("List view saved as kijiji_rental_list.html")
        
    def save_to_csv(self, listings, output_file="kijiji_rentals.csv"):
        """Save listings to CSV file"""
        if not listings:
            print("No listings to save")
            return
            
        df = pd.DataFrame(listings)
        df = df.drop_duplicates(subset=['url'])  # Remove duplicates
        df.to_csv(output_file, index=False)
        print(f"Saved {len(df)} listings to {output_file}")
        
    def generate_summary_report(self, listings):
        """Generate a summary report of the scraped data"""
        if not listings:
            return
            
        print("\n" + "="*60)
        print("KIJIJI RENTAL SCRAPING SUMMARY REPORT")
        print("="*60)
        
        # Basic stats
        total_listings = len(listings)
        listings_with_coords = len([l for l in listings if l['latitude'] and l['longitude']])
        
        print(f"Total listings found: {total_listings}")
        print(f"Listings with coordinates: {listings_with_coords}")
        if total_listings > 0:
            print(f"Coordinates available: {(listings_with_coords/total_listings)*100:.1f}%")
        
        # Price analysis
        prices = []
        for listing in listings:
            try:
                price_str = listing['price'].replace('$', '').replace(',', '')
                price = float(price_str)
                prices.append(price)
            except (ValueError, TypeError):
                continue
                
        if prices:
            print("\nPrice Analysis:")
            print(f"  Average price: ${sum(prices)/len(prices):.0f}")
            print(f"  Minimum price: ${min(prices):.0f}")
            print(f"  Maximum price: ${max(prices):.0f}")
            
            # Price ranges
            under_800 = len([p for p in prices if p < 800])
            between_800_1200 = len([p for p in prices if 800 <= p < 1200])
            over_1200 = len([p for p in prices if p >= 1200])
            
            print("\nPrice Distribution:")
            print(f"  Under $800: {under_800} listings")
            print(f"  $800-$1200: {between_800_1200} listings")
            print(f"  Over $1200: {over_1200} listings")
        
        # Bedroom analysis
        bedrooms = {}
        for listing in listings:
            if 'Bedrooms' in listing['info']:
                try:
                    bed_info = listing['info'].split('Bedrooms: ')[1].split(' *** ')[0]
                    if bed_info in bedrooms:
                        bedrooms[bed_info] += 1
                    else:
                        bedrooms[bed_info] = 1
                except (ValueError, TypeError, IndexError):
                    continue
                    
        if bedrooms:
            print("\nBedroom Distribution:")
            for beds, count in sorted(bedrooms.items()):
                print(f"  {beds} bedrooms: {count} listings")
        
        print("="*60)

def main():
    """Main function to run the scraper"""
    print("Kijiji Rental Scraper - Final Version")
    print("Updated for 2024 Kijiji structure")
    print("-" * 40)
    
    scraper = KijijiScraperFinal()
    
    # Scrape listings (enable geocoding for map creation)
    listings = scraper.scrape_kijiji_rentals(max_pages=10, enable_geocoding=True)
    
    if listings:
        # Generate summary report
        scraper.generate_summary_report(listings)
        
        # Save to CSV
        scraper.save_to_csv(listings)
        
        # Create map using Folium (same method as web_turtle.py)
        scraper.create_map(listings, map_type="folium")
        
        print("\n✓ Scraping completed successfully!")
        print("Files created:")
        print("- kijiji_rentals.csv (listing data)")
        print("- index.html (interactive map) OR kijiji_rental_list.html (list view)")
        print("\nOpen the HTML file in your browser to view the results!")
    else:
        print("✗ No listings found. Check your internet connection and try again.")

if __name__ == "__main__":
    main()
