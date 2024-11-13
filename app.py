from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time

def open_url_in_chrome(url, mode='headless'):
    # Set Chrome options
    options = Options()
    if mode == 'headless':
        options.add_argument('--headless')  # Run in headless mode (no UI)
    
    # Specify the path to the chromedriver
    service = Service('./chromedriver.exe')  # Update this path if needed
    
    # Initialize the driver with the Service object and options
    driver = webdriver.Chrome(service=service, options=options)
    
    # Open the URL
    driver.get(url)
    
    # Let the page load (you can adjust the sleep time as necessary)
    time.sleep(5)  # Adjust sleep time as needed
    
    return driver

def get_transcript(video_url):
    # Open the URL in Chrome with headless mode
    driver = open_url_in_chrome(video_url, mode='headless')
    
    # Add your logic here to extract the transcript or interact with the page
    # Example: Find the transcript text if it's available on the page
    try:
        # Adjust this selector based on how the transcript is presented
        transcript_element = driver.find_element(By.CSS_SELECTOR, 'div.transcript')  # Adjust selector
        transcript = transcript_element.text
        return transcript
    except Exception as e:
        print(f"Error extracting transcript: {e}")
        return None
    finally:
        driver.quit()

# Example usage:
video_url = 'https://www.youtube.com/watch?v=example_video_id'  # Replace with actual video URL
transcript = get_transcript(video_url)
if transcript:
    print("Transcript:", transcript)
else:
    print("Transcript not found.")
