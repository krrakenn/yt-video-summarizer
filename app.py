import requests
import streamlit as st
from urllib.parse import urlparse, parse_qs
import time
import os
from selenium import webdriver
from time import sleep
import pandas as pd

SUMMARY_API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
QA_API_URL = "https://api-inference.huggingface.co/models/deepset/roberta-base-squad2"
summary_headers = {"Authorization": "Bearer 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"}
qa_headers = {"Authorization": "Bearer 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"}

def query(api_url, headers, payload):
    response = requests.post(api_url, headers=headers, json=payload)
    return response.json()

def chunk_text(text, max_length=512):
    words = text.split()
    for i in range(0, len(words), max_length):
        yield ' '.join(words[i:i + max_length])

def generate_summary(text):
    summaries = []
    total_chunks = len(list(chunk_text(text)))
    progress_bar = st.progress(0)
    progress_text = st.empty()
    start_time = time.time()

    for i, chunk in enumerate(chunk_text(text)):
        chunk_length = len(chunk.split())
        min_len, max_len = (1, 60) if chunk_length <= 150 else (70, 130) if chunk_length <= 300 else (130, 280)

        output = query(SUMMARY_API_URL, summary_headers, {
            "inputs": chunk,
            "parameters": {"min_length": min_len, "max_length": max_len}
        })
        summaries.append(output[0]['summary_text'])
        progress_bar.progress((i + 1) / total_chunks)
        progress_text.text(f"Progress: {int((i + 1) / total_chunks * 100)}%")

    progress_bar.empty()
    progress_text.empty()
    elapsed_time = time.time() - start_time
    return ' '.join(summaries), elapsed_time

def open_url_in_chrome(url, mode='headless'):
    if mode == 'headed':
        driver = webdriver.Chrome()
    elif mode == 'headless':
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        driver = webdriver.Chrome('./chromedriver.exe', options=options)
    driver.get(url)
    return driver

def accept_T_and_C(driver):
    driver.find_element_by_xpath("//paper-button[@aria-label='No thanks']").click()
    driver.switch_to.frame(driver.find_element_by_xpath("//iframe[contains(@src, 'consent.google.com')]"))
    sleep(1)
    driver.find_element_by_xpath('//*[@id="introAgreeButton"]/span/span').click()
    sleep(3)
    driver.refresh()

def get_transcript_from_selenium(driver, mode):
    driver.implicitly_wait(10)
    if mode == 'headed':
        try:
            print('Accepting Terms and Conditions')
            accept_T_and_C(driver)
        except:
            print("No T&Cs to accept.")
        driver.find_element_by_xpath("//button[@aria-label='More actions']").click()
        driver.find_element_by_xpath("//*[@id='items']/ytd-menu-service-item-renderer/tp-yt-paper-item").click()
        sleep(3)
    elif mode == 'headless':
        try:
            driver.find_elements_by_xpath("//button[@aria-label='More actions']")[1].click()
        except:
            sleep(3)
            driver.refresh()
            get_transcript_from_selenium(driver, mode)
        try:
            driver.find_element_by_xpath("//*[@id='items']/ytd-menu-service-item-renderer/tp-yt-paper-item").click()
        except:
            sleep(3)
            driver.refresh()
            get_transcript_from_selenium(driver, mode)
    transcript_element = driver.find_element_by_xpath("//*[@id='body']/ytd-transcript-segment-list-renderer")
    transcript = transcript_element.text
    return transcript

def transcript_to_df(transcript):
    transcript = transcript.split('\n')
    transcript_timestamps = transcript[::2]
    transcript_text = transcript[1::2]
    df = pd.DataFrame({'timestamp': transcript_timestamps, 'text': transcript_text})
    return df

def get_transcript(url, mode='headless'):
    driver = open_url_in_chrome(url, mode)
    transcript = get_transcript_from_selenium(driver, mode)
    driver.quit()
    return transcript

def extract_video_id(url):
    parsed_url = urlparse(url)
    if parsed_url.query:
        return parse_qs(parsed_url.query).get('v', [None])[0]
    return parsed_url.path.split('/')[-1] if '/' in parsed_url.path else None

# Streamlit Interface
st.markdown(
    """
    <h1 style="background: -webkit-linear-gradient(#a0eaff, #85d1e5); -webkit-background-clip: text; color: transparent;">
        TubeIntel: Summarize Video and Ask Questions about the Video
    </h1>
    """,
    unsafe_allow_html=True
)

video_url = st.text_input("YouTube Video URL")
choice = st.radio("Choose an action:", ('Generate Summary', 'Ask Questions'))

if video_url:
    transcript = get_transcript(video_url)
    if transcript:
        if choice == 'Generate Summary':
            st.write("Generating summary...")
            summary, elapsed_time = generate_summary(transcript)
            st.success("Summary generated successfully!")
            st.subheader("Summary")
            st.text_area("Video Summary", value=summary, height=300, max_chars=5000)
            st.write(f"Time taken to generate summary: {elapsed_time:.2f} seconds")
            st.download_button("Download Summary", data=summary, file_name=f"summary.txt", mime="text/plain")

        elif choice == 'Ask Questions':
            st.subheader("Ask Questions About the Video")
            question = st.text_input("Enter your question:")
            if st.button("Get Answer"):
                if question:
                    output = query(QA_API_URL, qa_headers, {
                        "inputs": {"question": question, "context": transcript}
                    })
                    answer = output.get("answer", "No answer found.")
                    confidence = output.get("score", 0) * 100  # Convert to percentage

                    confidence_color = "green" if confidence > 70 else "yellow" if confidence >= 50 else "red"
                    st.write(f"Answer: {answer}")
                    st.markdown(
                        f"<span style='color:{confidence_color}; font-weight:bold;'>Confidence: {confidence:.2f}%</span>",
                        unsafe_allow_html=True
                    )
                else:
                    st.write("Please enter a question.")
    else:
        st.error("Transcript extraction failed.")
else:
    st.write("Please enter a valid YouTube URL.")
