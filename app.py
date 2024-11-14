import requests
import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs
import time
import random
from bs4 import BeautifulSoup
import concurrent.futures

SUMMARY_API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
QA_API_URL = "https://api-inference.huggingface.co/models/deepset/roberta-base-squad2"
summary_headers = {"Authorization": "Bearer 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"}
qa_headers = {"Authorization": "Bearer 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"}

def fetch_free_proxies():
    """Fetch free proxies from multiple sources"""
    proxies = []
    
    # Source 1: free-proxy-list.net
    try:
        response = requests.get('https://free-proxy-list.net/')
        soup = BeautifulSoup(response.text, 'html.parser')
        proxy_table = soup.find('table')
        
        for row in proxy_table.find_all('tr')[1:]:  # Skip header row
            cols = row.find_all('td')
            if len(cols) >= 7:  # Ensure row has enough columns
                ip = cols[0].text.strip()
                port = cols[1].text.strip()
                https = cols[6].text.strip()
                if https == 'yes':  # Only use HTTPS proxies
                    proxies.append(f'http://{ip}:{port}')
    except Exception as e:
        st.warning(f"Failed to fetch proxies from source 1: {str(e)}")

    # Source 2: geonode.com free proxy list
    try:
        response = requests.get('https://proxylist.geonode.com/api/proxy-list?limit=100&page=1&sort_by=lastChecked&sort_type=desc&protocols=http%2Chttps')
        data = response.json()
        for proxy in data.get('data', []):
            if proxy.get('protocols') and 'https' in proxy['protocols']:
                ip = proxy.get('ip')
                port = proxy.get('port')
                if ip and port:
                    proxies.append(f'http://{ip}:{port}')
    except Exception as e:
        st.warning(f"Failed to fetch proxies from source 2: {str(e)}")

    return list(set(proxies))  # Remove duplicates

def test_proxy(proxy):
    """Test if a proxy is working"""
    try:
        response = requests.get(
            'https://www.google.com',
            proxies={'http': proxy, 'https': proxy},
            timeout=5
        )
        return proxy if response.status_code == 200 else None
    except:
        return None

def get_working_proxy():
    """Get a working proxy from the list"""
    if 'proxy_list' not in st.session_state or not st.session_state.proxy_list:
        st.session_state.proxy_list = fetch_free_proxies()
    
    # Test proxies in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        working_proxies = list(filter(None, executor.map(test_proxy, st.session_state.proxy_list)))
    
    if working_proxies:
        return random.choice(working_proxies)
    else:
        st.error("No working proxies found. Retrying with new proxy list...")
        st.session_state.proxy_list = fetch_free_proxies()
        return None

def query(api_url, headers, payload):
    max_retries = 3
    current_try = 0
    
    while current_try < max_retries:
        proxy = get_working_proxy()
        if not proxy:
            current_try += 1
            continue
            
        try:
            proxy_dict = {
                'http': proxy,
                'https': proxy
            }
            response = requests.post(
                api_url,
                headers=headers,
                json=payload,
                proxies=proxy_dict,
                timeout=10
            )
            return response.json()
        except Exception as e:
            current_try += 1
            st.warning(f"Proxy failed, trying another one... ({current_try}/{max_retries})")
    
    st.error("All proxy attempts failed. Please try again later.")
    return None

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
        
        if output is None:
            progress_bar.empty()
            progress_text.empty()
            return None, 0
            
        summaries.append(output[0]['summary_text'])
        progress_bar.progress((i + 1) / total_chunks)
        progress_text.text(f"Progress: {int((i + 1) / total_chunks * 100)}%")

    progress_bar.empty()
    progress_text.empty()
    elapsed_time = time.time() - start_time
    return ' '.join(summaries), elapsed_time

def extract_video_id(url):
    parsed_url = urlparse(url)
    if parsed_url.query:
        return parse_qs(parsed_url.query).get('v', [None])[0]
    return parsed_url.path.split('/')[-1] if '/' in parsed_url.path else None

def get_transcript(url):
    proxy = get_working_proxy()
    try:
        video_id = extract_video_id(url)
        if not video_id:
            return "Error: Could not extract video ID from URL", None
            
        if proxy:
            proxy_dict = {
                'http': proxy,
                'https': proxy
            }
            YouTubeTranscriptApi.http_client.proxies = proxy_dict
        
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        try:
            transcript = transcript_list.find_manually_created_transcript(['en'])
        except:
            transcript = transcript_list.find_generated_transcript(['en'])
            
        transcript_data = transcript.fetch()
        full_transcript = " ".join([entry['text'] for entry in transcript_data])
        return full_transcript, video_id
    except Exception as e:
        return f"Error: {str(e)}", None

# Streamlit Interface
st.markdown(
    """
    <h1 style="background: -webkit-linear-gradient(#a0eaff, #85d1e5); -webkit-background-clip: text; color: transparent;">
        TubeIntel: Summarize Video and Ask Questions about the Video
    </h1>
    """,
    unsafe_allow_html=True
)

# Proxy status indicator in sidebar
st.sidebar.title("Proxy Status")
if st.sidebar.button("Refresh Proxy List"):
    st.session_state.proxy_list = fetch_free_proxies()
    st.sidebar.success(f"Found {len(st.session_state.proxy_list)} proxies")

# Main interface
video_url = st.text_input("YouTube Video URL")
choice = st.radio("Choose an action:", ('Generate Summary', 'Ask Questions'))

if video_url:
    transcript, video_id = get_transcript(video_url)
    if video_id:
        if choice == 'Generate Summary':
            st.write("Generating summary...")
            result = generate_summary(transcript)
            if result:
                summary, elapsed_time = result
                st.success("Summary generated successfully!")
                st.subheader("Summary")
                st.text_area("Video Summary", value=summary, height=300, max_chars=5000)
                st.write(f"Time taken to generate summary: {elapsed_time:.2f} seconds")
                st.download_button("Download Summary", data=summary, file_name=f"summary_{video_id}.txt", mime="text/plain")

        elif choice == 'Ask Questions':
            st.subheader("Ask Questions About the Video")
            question = st.text_input("Enter your question:")

            if st.button("Get Answer"):
                if question:
                    output = query(QA_API_URL, qa_headers, {
                        "inputs": {"question": question, "context": transcript}
                    })
                    if output:
                        answer = output.get("answer", "No answer found.")
                        confidence = output.get("score", 0) * 100

                        confidence_color = "green" if confidence > 70 else "yellow" if confidence >= 50 else "red"
                        st.write(f"Answer: {answer}")
                        st.markdown(
                            f"<span style='color:{confidence_color}; font-weight:bold;'>Confidence: {confidence:.2f}%</span>",
                            unsafe_allow_html=True
                        )
                else:
                    st.write("Please enter a question.")
    else:
        st.error(transcript)
else:
    st.write("Please enter a valid YouTube URL.")
