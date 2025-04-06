from google import genai
from google.genai import types
import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from selenium.webdriver.chrome.options import Options
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
import time
import bs4
import requests
import json
from google.oauth2 import service_account

load_dotenv()
service_account_info = json.loads(os.environ['GOOGLE_APPLICATION_CREDENTIALS_JSON'])
credentials = service_account.Credentials.from_service_account_info(service_account_info)
PROJECT_ID = os.getenv("PROJECT_ID")
REGION = os.getenv("REGION")
ENDPOINT_ID = os.getenv("ENDPOINT_ID")

def query_pill_features(image_bytes):
    client = genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location=REGION,
        credentials=credentials
    )

    msg1_image1 = types.Part.from_bytes(
        data=image_bytes,
        mime_type="image/png",
    )

    model = f"projects/{PROJECT_ID}/locations/{REGION}/endpoints/{ENDPOINT_ID}"
    contents = [
        types.Content(
            role="user",
            parts=[
                msg1_image1,
                types.Part.from_text(text="""Get the color, shape, and imprint of this pill.""")
            ]
        ),
    ]
    generate_content_config = types.GenerateContentConfig(
        temperature=0.2,
        top_p=0.8,
        max_output_tokens=1024,
        response_modalities=["TEXT"],
        safety_settings=[
            types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH",
                threshold="OFF"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="OFF"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                threshold="OFF"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT",
                threshold="OFF"
            )
        ],
    )

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=generate_content_config,
    )

    features = response.text.split(",")
    imprint = features[0]
    color = features[1]
    shape = features[2]

    return imprint, color, shape

def query_drugs(imprint: str, color: str, shape: str):
    url = f"https://www.drugs.com/imprints.php?imprint={imprint}&color={color}&shape={shape}"

    response = requests.get(url)
    if response.status_code == 200:
        if response:
            html_content = response.text
            soup = BeautifulSoup(html_content, "html.parser")
            
            pills = soup.find_all("a", string="View details")
            
            results = []
            for pill_link in pills:
                container = pill_link.find_parent("div")
                if container:
                    text = container.get_text(" ", strip=True)
                    results.append(text)
            
            i = 0
            output = []
            if results:
                print("Found pill information!")
                for r in results:
                    if i < 3:
                        if r is None:
                            print("Bad pill data")
                        else:
                            output.append(r)
                        i += 1
            else:
                print("No pill details found using the current parsing strategy.")
    else:
        print(f"Error fetching page: Status code {response.status_code}")
        
    return {
        "imprint": imprint,
        "color": color,
        "shape": shape,
        "1st choice": output[0] if len(output) > 0 else "N/A",
        "2nd choice": output[1] if len(output) > 1 else "N/A",
        "3rd choice": output[2] if len(output) > 2 else "N/A",
    }

def query_side_effects(drug_name: str):
    url = f"https://api.fda.gov/drug/event.json?search=patient.drug.medicinalproduct:\"{drug_name}\"&limit=10"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        side_effects = []
        
        for event in data.get("results", []):
            reactions = event.get("patient", {}).get("reaction", [])
            for reaction in reactions:
                if "reactionmeddrapt" in reaction:
                    side_effects.append(reaction["reactionmeddrapt"])
        
        return list(set(side_effects))
    else:
        print(f"Error fetching side effects: Status code {response.status_code}")
        return []

chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")

def get_id(drug_name, sleep_time=1):
    driver = webdriver.Chrome(options=chrome_options)

    driver.get(f"https://www.drugs.com/interaction/list/?searchterm={drug_name}")
    previous_url = driver.current_url

    time.sleep(sleep_time)
    current_url = driver.current_url
    drug_id = None
    if current_url != previous_url:
        print(f'URL changed to: {current_url}')
        drug_id = current_url.split('?drug_list=')[1]
        print(f'Drug ID: {drug_id}')
    else:
        print("URL did not change. Retrying...")
        get_id(drug_name, sleep_time + 1)
        
    driver.quit()

    return drug_id

def query_ddi(drug_name1, drug_name2):
    url = f'https://www.drugs.com/interactions-check.php?drug_list={get_id(drug_name1)},{get_id(drug_name2)}'
    response = requests.get(url)
    response.raise_for_status()

    soup = bs4.BeautifulSoup(response.text, 'html.parser')

    results = {}

    header = soup.find('h2', string=lambda s: s and 'drug and food interactions' in s.lower())
    if not header:
        results["message"] = "No 'Drug and food interactions' section found on the page."
        return results

    wrapper = header.find_next_sibling("div", class_="interactions-reference-wrapper")
    if not wrapper:
        results["message"] = "No interactions wrapper found."
        return results

    instances = wrapper.find_all("div", class_="interactions-reference")
    if not instances:
        results["message"] = "No drug-food interaction instances found."
        return results

    def ordinal(n):
        if 10 <= n % 100 <= 20:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
        return str(n) + suffix

    for i, instance in enumerate(instances, start=1):
        item = {}
        header_div = instance.find("div", class_="interactions-reference-header")
        if header_div:
            h3_tag = header_div.find("h3")
            if h3_tag:
                item["title"] = h3_tag.get_text(" ", strip=True)
            applies_to_tag = header_div.find("p")
            if applies_to_tag:
                item["applies_to"] = applies_to_tag.get_text(strip=True)
        description_paragraphs = []
        for p in instance.find_all("p", recursive=False):
            if "Switch to professional" in p.get_text():
                continue
            if header_div and p in header_div.find_all("p"):
                continue
            description_paragraphs.append(p.get_text(strip=True))
        if description_paragraphs:
            item["description"] = " ".join(description_paragraphs)
        results[f"{ordinal(i)} interaction"] = item

    return results